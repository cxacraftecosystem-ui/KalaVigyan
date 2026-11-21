from __future__ import annotations

import hashlib
import logging
import time
import uuid
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from itertools import batched

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import release_connection
from app.core.errors import AppError, spend_refusal
from app.data.craft_master_loader import ACTIVE
from app.models import AdminDistrict, AdminState, Craft, CraftAlias, CraftLocation, CraftSpelling
from app.research.crafts import CraftQuery, CraftResolution
from app.research.embedding import TextEmbedder, checked_vectors
from app.retrieval.deadline import Deadline
from app.retrieval.stamps import current_embedding_model, made_by_current_model, needs_vector
from app.services.craft_index import AliasRecord, CraftIndex, CraftRecord, SpellingRecord, build_index
from app.services.craft_matching import (
    SEMANTIC_TOP_K,
    SemanticHit,
    lexical_match,
    resolution_from,
    slug_resolution,
)

__all__ = [
    "DESCRIPTOR_BATCH",
    "INDEX_TTL_SECONDS",
    "CraftIndexStore",
    "DatabaseCraftResolver",
    "descriptor_hash",
    "descriptor_text",
    "fill_descriptor_embeddings",
    "load_index",
]

logger = logging.getLogger(__name__)

INDEX_TTL_SECONDS = 300.0
DESCRIPTOR_BATCH = 50
DESCRIPTOR_SEPARATOR = "; "


class CraftIndexStore:
    def __init__(
        self, *, ttl_seconds: float = INDEX_TTL_SECONDS, clock: Callable[[], float] = time.monotonic
    ) -> None:
        self._ttl = ttl_seconds
        self._clock = clock
        self._index: CraftIndex | None = None
        self._loaded_at = 0.0

    async def get(self, session: AsyncSession) -> CraftIndex:
        now = self._clock()
        if self._index is None or now - self._loaded_at >= self._ttl:
            self._index = await load_index(session)
            self._loaded_at = now
        return self._index

    def invalidate(self) -> None:
        self._index = None


class DatabaseCraftResolver:
    def __init__(self, session: AsyncSession, *, store: CraftIndexStore, embed: TextEmbedder) -> None:
        self._session = session
        self._store = store
        self._embed = embed

    async def resolve(self, query: CraftQuery) -> CraftResolution:
        index = await self._store.get(self._session)
        if query.craft_slug:
            return slug_resolution(index, query.craft_slug, query.text)
        match = lexical_match(index, query.text)
        lexical = resolution_from(index, match)
        if lexical.status == "RESOLVED" or not index.embedded:
            return lexical
        try:
            hits = await self._semantic(query.text)
        except AppError as error:
            if spend_refusal(error):
                raise
            logger.warning("finding crafts by meaning failed, so the name match stands: %s", error)
            return lexical
        return resolution_from(index, match, hits)

    async def _semantic(self, text: str) -> list[SemanticHit]:
        await release_connection(self._session)
        (vector,) = checked_vectors(await self._embed([text]), expected=1)
        distance = Craft.descriptorEmbedding.cosine_distance(vector)
        rows = (
            await self._session.execute(
                select(Craft.id, distance.label("distance"))
                .where(
                    Craft.status == ACTIVE,
                    Craft.isCatchAll.is_(False),
                    Craft.descriptorEmbedding.is_not(None),
                    made_by_current_model(Craft.embeddingModel),
                )
                .order_by(distance, Craft.slug)
                .limit(SEMANTIC_TOP_K)
            )
        ).all()
        return [SemanticHit(craft_id, 1.0 - float(gap)) for craft_id, gap in rows]


def descriptor_text(name: str, names: Sequence[str]) -> str:
    seen: dict[str, str] = {}
    for value in (name, *names):
        label = (value or "").strip()
        if label and label.casefold() not in seen:
            seen[label.casefold()] = label
    return DESCRIPTOR_SEPARATOR.join(seen.values())


def descriptor_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class _Descriptor:
    craft_id: uuid.UUID
    text: str
    digest: str


async def fill_descriptor_embeddings(
    session: AsyncSession,
    embed: TextEmbedder,
    *,
    batch_size: int = DESCRIPTOR_BATCH,
    deadline: Deadline | None = None,
) -> int:
    filled = 0
    for chunk in batched(await _stale_descriptors(session), batch_size, strict=False):
        if deadline is not None and deadline.passed():
            break
        await release_connection(session)
        vectors = checked_vectors(await embed([item.text for item in chunk]), expected=len(chunk))
        for item, vector in zip(chunk, vectors, strict=True):
            await session.execute(
                update(Craft)
                .where(Craft.id == item.craft_id)
                .values(
                    descriptorEmbedding=vector,
                    descriptorHash=item.digest,
                    embeddingModel=current_embedding_model(),
                )
            )
        await session.commit()
        filled += len(chunk)
    return filled


async def _stale_descriptors(session: AsyncSession) -> list[_Descriptor]:
    unstamped = needs_vector(Craft.descriptorEmbedding, Craft.embeddingModel).label("unstamped")
    rows = (
        await session.execute(
            select(Craft.id, Craft.name, Craft.localName, Craft.descriptorHash, unstamped)
            .where(Craft.status == ACTIVE, Craft.isCatchAll.is_(False))
            .order_by(Craft.slug)
        )
    ).all()
    names = await _alias_names(session, [row.id for row in rows])
    stale: list[_Descriptor] = []
    for row in rows:
        text = descriptor_text(row.name, [row.localName or "", *names.get(row.id, [])])
        digest = descriptor_hash(text)
        if row.unstamped or row.descriptorHash != digest:
            stale.append(_Descriptor(row.id, text, digest))
    return stale


async def load_index(session: AsyncSession) -> CraftIndex:
    places = await _craft_places(session)
    crafts = [
        CraftRecord(
            id=row.id,
            slug=row.slug,
            name=row.name,
            status=row.status,
            is_catch_all=row.isCatchAll,
            merged_into=row.mergedIntoId,
            craft_code=row.craftCode,
            local_name=row.localName,
            places=(*row.stateOfPractice, *row.stateOfOrigin, *places.get(row.id, ())),
        )
        for row in (await session.execute(select(*_CRAFT_COLUMNS))).all()
    ]
    aliases = [
        AliasRecord(craft_id, alias)
        for craft_id, alias in (
            await session.execute(
                select(CraftAlias.craftId, CraftAlias.alias).where(CraftAlias.status == ACTIVE)
            )
        ).all()
    ]
    spellings = [
        SpellingRecord(code, label)
        for code, label in (await session.execute(select(CraftSpelling.craftCode, CraftSpelling.label))).all()
    ]
    embedded = await session.scalar(
        select(func.count(Craft.id)).where(Craft.status == ACTIVE, Craft.descriptorEmbedding.is_not(None))
    )
    return build_index(crafts, aliases, spellings, embedded=int(embedded or 0))


_CRAFT_COLUMNS = (
    Craft.id,
    Craft.slug,
    Craft.name,
    Craft.localName,
    Craft.status,
    Craft.isCatchAll,
    Craft.mergedIntoId,
    Craft.craftCode,
    Craft.stateOfPractice,
    Craft.stateOfOrigin,
)


async def _craft_places(session: AsyncSession) -> dict[uuid.UUID, list[str]]:
    rows = (
        await session.execute(
            select(CraftLocation.craftId, CraftLocation.placeLabel, AdminDistrict.name, AdminState.name)
            .outerjoin(AdminDistrict, AdminDistrict.lgd == CraftLocation.districtLgd)
            .outerjoin(AdminState, AdminState.lgd == CraftLocation.stateLgd)
        )
    ).all()
    found: dict[uuid.UUID, list[str]] = {}
    for craft_id, *labels in rows:
        found.setdefault(craft_id, []).extend(label for label in labels if label)
    return found


async def _alias_names(session: AsyncSession, craft_ids: Sequence[uuid.UUID]) -> dict[uuid.UUID, list[str]]:
    if not craft_ids:
        return {}
    rows = (
        await session.execute(
            select(CraftAlias.craftId, CraftAlias.alias)
            .where(CraftAlias.craftId.in_(craft_ids), CraftAlias.status == ACTIVE)
            .order_by(CraftAlias.craftId, CraftAlias.alias)
        )
    ).all()
    found: dict[uuid.UUID, list[str]] = {}
    for craft_id, alias in rows:
        found.setdefault(craft_id, []).append(alias)
    return found
