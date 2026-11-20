from __future__ import annotations

import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, time

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import SuppliedSource
from app.research.evidence import EvidenceItem, SourceDocument
from app.research.supplied_sources import (
    PASSAGE_SEPARATOR,
    READY,
    SUPPLIED_TEXT_MAX_CHARS,
    SourceAccess,
    SourceIdentity,
    cite_key,
    supplied_note,
)
from app.sources.adapter import build_document

from .live_source_store import source_for

__all__ = [
    "SUPPLIED_ADAPTER",
    "SUPPLIED_KEY",
    "SuppliedRead",
    "keep_supplied",
    "supplied_read",
    "supplied_rows",
]

SUPPLIED_ADAPTER = "supplied"
SUPPLIED_KEY = "supplied"
SUPPLIED_TIER = "T4"
FULL_TEXT = "FULL_TEXT"


@dataclass(frozen=True)
class SuppliedRead:
    document: SourceDocument
    note: str


async def supplied_rows(session: AsyncSession, proposer_id: uuid.UUID, url: str) -> list[SuppliedSource]:
    return list(
        await session.scalars(
            select(SuppliedSource)
            .where(
                SuppliedSource.userId == proposer_id,
                SuppliedSource.citeUrl == cite_key(url),
                SuppliedSource.state == READY,
            )
            .order_by(SuppliedSource.createdAt, SuppliedSource.id)
        )
    )


async def supplied_read(
    session: AsyncSession, url: str, proposer_id: uuid.UUID | None
) -> SuppliedRead | None:
    if proposer_id is None:
        return None
    rows = await supplied_rows(session, proposer_id, url)
    if not rows:
        return None
    newest = rows[-1]
    text = PASSAGE_SEPARATOR.join(row.text or "" for row in rows)[:SUPPLIED_TEXT_MAX_CHARS]
    access = SourceAccess(how=newest.accessKind, accessed_on=newest.accessedOn, note=newest.accessNote)
    return SuppliedRead(
        document=build_document(_item(newest), text, FULL_TEXT), note=supplied_note(newest.id, access)
    )


async def keep_supplied(session: AsyncSession, document: SourceDocument) -> uuid.UUID:
    source = await source_for(session, document.item, None)
    ids = _supplied_ids(document.item)
    if ids:
        await session.execute(
            update(SuppliedSource)
            .where(SuppliedSource.id.in_(ids), ~SuppliedSource.sourceIds.any(source.id))
            .values(sourceIds=func.array_append(SuppliedSource.sourceIds, source.id))
        )
    return source.id


def _item(row: SuppliedSource) -> EvidenceItem:
    identity = SourceIdentity.model_validate(row.identity)
    confirmed = row.confirmation or {}
    return EvidenceItem(
        id=f"{SUPPLIED_ADAPTER}:{row.id}",
        adapter=SUPPLIED_ADAPTER,
        tier=SUPPLIED_TIER,
        source_type=identity.kind,
        url=row.citeUrl,
        title=row.title,
        authors=list(confirmed.get("authors") or identity.authors),
        published=str(identity.year or confirmed.get("year") or "") or None,
        retrieved_at=datetime.combine(row.accessedOn, time(), tzinfo=UTC),
        licence=row.licence,
        doi=row.doi,
        publisher=identity.publisher,
        trust=row.grade,
        external_ids={SUPPLIED_KEY: str(row.id), "sha256": row.textSha256 or ""},
    )


def _supplied_ids(item: EvidenceItem) -> Sequence[uuid.UUID]:
    found = item.external_ids.get(SUPPLIED_KEY)
    return [uuid.UUID(found)] if found else []
