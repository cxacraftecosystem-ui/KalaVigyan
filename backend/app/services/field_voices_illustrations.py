from __future__ import annotations

import uuid
from collections.abc import Collection, Sequence
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Craft, FieldImage, FieldImageCraft, MediaRefClaim
from app.research.image_relevance import ClaimText, illustrated_claims
from app.research.retrieval import EVERY_CHUNK_ACLS
from app.research.vocabulary import FACT_LEVELS

from .knowledge_view import claims_for, order_claims
from .media_ref_store import TEXT_RELEVANCE

__all__ = [
    "ILLUSTRATED_MODE",
    "UNMATCHED_GROUPS",
    "illustrated_by_photo",
    "link_photo_claims",
    "photo_described",
    "relink_photo_claims",
]

ILLUSTRATED_MODE = "HYBRID"
UNMATCHED_GROUPS = frozenset({"PERSON", "SESSION", "WORKSHOP"})


def photo_described(caption: str | None, groups: Sequence[tuple[str, str]]) -> str:
    labels = [label for kind, label in groups if kind not in UNMATCHED_GROUPS]
    return "\n".join(part for part in (caption, *labels) if part)


async def link_photo_claims(
    session: AsyncSession, media_id: uuid.UUID, *, described: str, craft_ids: Collection[uuid.UUID]
) -> tuple[uuid.UUID, ...]:
    await session.execute(delete(MediaRefClaim).where(MediaRefClaim.mediaRefId == media_id))
    chosen = await illustrated_by_photo(session, described, craft_ids)
    if chosen:
        links = [{"mediaRefId": media_id, "claimId": claim, "relevance": TEXT_RELEVANCE} for claim in chosen]
        await session.execute(insert(MediaRefClaim).values(links).on_conflict_do_nothing())
    return chosen


async def illustrated_by_photo(
    session: AsyncSession, described: str, craft_ids: Collection[uuid.UUID]
) -> tuple[uuid.UUID, ...]:
    if not craft_ids or not described:
        return ()
    crafts = list(
        await session.scalars(select(Craft).where(Craft.id.in_(list(craft_ids))).order_by(Craft.slug))
    )
    claims: list[ClaimText] = []
    for craft in crafts:
        views, _ = await claims_for(session, craft, mode=ILLUSTRATED_MODE, acls=EVERY_CHUNK_ACLS)
        claims += [ClaimText(view.id, view.text) for view in order_claims(views) if view.level in FACT_LEVELS]
    found = illustrated_claims(described, claims, leave_out=" ".join(craft.name for craft in crafts))
    return found.claim_ids if found is not None else ()


async def relink_photo_claims(session: AsyncSession, image: FieldImage) -> tuple[uuid.UUID, ...]:
    if image.mediaRefId is None:
        return ()
    crafts = await session.scalars(select(FieldImageCraft.craftId).where(FieldImageCraft.imageId == image.id))
    described = photo_described(image.caption, _stored_groups(image.context))
    return await link_photo_claims(session, image.mediaRefId, described=described, craft_ids=list(crafts))


def _stored_groups(context: Any) -> list[tuple[str, str]]:
    groups = context.get("groups", []) if isinstance(context, dict) else []
    return [(str(group.get("kind")), str(group.get("label") or "")) for group in groups]
