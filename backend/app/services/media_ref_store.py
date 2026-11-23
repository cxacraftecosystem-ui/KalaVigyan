from __future__ import annotations

import hashlib
import logging
import uuid
from collections.abc import Sequence
from dataclasses import dataclass

from pydantic import ValidationError
from sqlalchemy import Select, and_, not_, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.errors import InvalidInput
from app.data.craft_master_loader import ID_NAMESPACE
from app.models import FieldImage, MediaRef as MediaRefRow, MediaRefClaim, Source
from app.research.image_relevance import ChosenImage, ClaimText
from app.research.images import ImageCandidate, media_ref_of
from app.research.media_refs import MediaRef
from app.research.retrieval import EVERY_CHUNK_ACLS

from . import knowledge_view
from .field_photo_scope import shown_field_photos

__all__ = [
    "INLINE_DISPLAY",
    "TEXT_RELEVANCE",
    "SqlMediaStore",
    "StoredPicture",
    "field_media",
    "media_ref_id",
    "media_ref_values",
    "media_url_key",
    "stored_media_ref",
    "stored_media_refs",
    "stored_pictures",
    "unshown_field_media",
]

logger = logging.getLogger(__name__)

TEXT_RELEVANCE = "TEXT"
INLINE_DISPLAY = "INLINE"
KEY_SEPARATOR = "\x1f"


def media_url_key(provider: str, page_url: str, image_url: str) -> str:
    joined = KEY_SEPARATOR.join((provider, page_url, image_url))
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()


def media_ref_id(url_key: str) -> uuid.UUID:
    return uuid.uuid5(ID_NAMESPACE, f"media-ref:{url_key}")


def stored_media_ref(row: MediaRefRow) -> MediaRef:
    return MediaRef(
        id=row.id,
        display=row.display,
        provider=row.provider,
        page_url=row.pageUrl,
        image_url=row.imageUrl,
        width=row.width,
        height=row.height,
        title=row.title,
        alt=row.alt,
        author=row.author,
        site=row.site,
        credit=row.credit,
        licence=row.licence,
        licence_url=row.licenceUrl,
        source_id=str(row.sourceId) if row.sourceId else None,
        retrieved_at=row.retrievedAt,
    )


def field_media() -> Select[tuple[uuid.UUID | None]]:
    return select(FieldImage.mediaRefId).where(FieldImage.mediaRefId.is_not(None))


def unshown_field_media() -> Select[tuple[uuid.UUID | None]]:
    return select(FieldImage.mediaRefId).where(
        FieldImage.mediaRefId.is_not(None), not_(and_(*shown_field_photos()))
    )


@dataclass(frozen=True)
class StoredPicture:
    media: MediaRef
    claim_id: uuid.UUID
    relevance: str


async def stored_pictures(session: AsyncSession, claim_ids: Sequence[uuid.UUID]) -> list[StoredPicture]:
    order = {claim_id: n for n, claim_id in enumerate(dict.fromkeys(claim_ids))}
    if not order:
        return []
    rows = await session.execute(
        select(MediaRefRow, MediaRefClaim.claimId, MediaRefClaim.relevance)
        .join(MediaRefClaim, MediaRefClaim.mediaRefId == MediaRefRow.id)
        .where(
            MediaRefClaim.claimId.in_(list(order)),
            MediaRefRow.display == INLINE_DISPLAY,
            MediaRefRow.id.not_in(unshown_field_media()),
        )
        .order_by(MediaRefRow.retrievedAt, MediaRefRow.id)
    )
    found: list[StoredPicture] = []
    for row, claim_id, relevance in rows.tuples().all():
        try:
            found.append(StoredPicture(stored_media_ref(row), claim_id, relevance))
        except ValidationError as refused:
            logger.error("stored media %s is off its contract and is not shown: %s", row.id, refused)
    return sorted(found, key=lambda picture: order[picture.claim_id])


class SqlMediaStore:
    def __init__(self, sessions: async_sessionmaker[AsyncSession]) -> None:
        self._sessions = sessions

    async def claim_texts(self, claim_ids: Sequence[uuid.UUID]) -> list[ClaimText]:
        async with self._sessions() as session:
            views, _ = await knowledge_view.claims_by_id(session, claim_ids, acls=EVERY_CHUNK_ACLS)
        return [
            ClaimText(claim_id=claim_id, text=views[claim_id].text)
            for claim_id in claim_ids
            if claim_id in views
        ]

    async def keep(self, chosen: Sequence[ChosenImage]) -> list[MediaRef]:
        async with self._sessions() as session:
            kept = [await _kept(session, image) for image in chosen]
            await session.commit()
        return kept


async def _kept(session: AsyncSession, image: ChosenImage) -> MediaRef:
    candidate = image.candidate
    url_key = media_url_key(candidate.provider, candidate.page_url, candidate.image_url)
    source_id = await _page_source(session, candidate)
    fresh = media_ref_of(candidate, media_id=media_ref_id(url_key), source_id=source_id)
    await session.execute(
        insert(MediaRefRow).values(media_ref_values(fresh, url_key)).on_conflict_do_nothing()
    )
    row = await session.scalar(select(MediaRefRow).where(MediaRefRow.urlKey == url_key))
    if row is None:
        raise InvalidInput(f"The media {url_key} could not be stored")
    links = [
        {"mediaRefId": row.id, "claimId": claim_id, "relevance": TEXT_RELEVANCE}
        for claim_id in image.illustration.claim_ids
    ]
    await session.execute(insert(MediaRefClaim).values(links).on_conflict_do_nothing())
    return stored_media_ref(row)


async def _page_source(session: AsyncSession, candidate: ImageCandidate) -> str | None:
    found = await session.scalar(
        select(Source.id)
        .where(Source.url == candidate.page_url)
        .order_by(Source.createdAt, Source.id)
        .limit(1)
    )
    return str(found) if found else None


def media_ref_values(ref: MediaRef, url_key: str) -> dict[str, object]:
    return {
        "id": ref.id,
        "urlKey": url_key,
        "display": ref.display,
        "provider": ref.provider,
        "pageUrl": ref.page_url,
        "imageUrl": ref.image_url,
        "width": ref.width,
        "height": ref.height,
        "title": ref.title,
        "alt": ref.alt,
        "author": ref.author,
        "site": ref.site,
        "credit": ref.credit,
        "licence": ref.licence,
        "licenceUrl": ref.licence_url,
        "sourceId": uuid.UUID(ref.source_id) if ref.source_id else None,
        "retrievedAt": ref.retrieved_at,
    }


async def stored_media_refs(
    session: AsyncSession, media_ids: Sequence[uuid.UUID]
) -> dict[uuid.UUID, MediaRef]:
    if not media_ids:
        return {}
    rows = await session.scalars(select(MediaRefRow).where(MediaRefRow.id.in_(list(media_ids))))
    return {row.id: stored_media_ref(row) for row in rows}
