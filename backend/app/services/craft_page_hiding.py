from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import Refused
from app.models import Craft, KnowledgePiece as PieceRow, MediaAsset, MediaJob, User

from . import audit
from .page_revalidation import craft_owners, refresh_pages

__all__ = [
    "MEDIA_HIDDEN_ACTION",
    "MEDIA_SHOWN_ACTION",
    "PIECE_HIDDEN_ACTION",
    "PIECE_SHOWN_ACTION",
    "SIMULATION",
    "set_page_media_hidden",
    "set_page_piece_hidden",
]

PIECE_HIDDEN_ACTION = "CRAFT_PAGE_PIECE_HIDDEN"
PIECE_SHOWN_ACTION = "CRAFT_PAGE_PIECE_SHOWN"
MEDIA_HIDDEN_ACTION = "CRAFT_PAGE_MEDIA_HIDDEN"
MEDIA_SHOWN_ACTION = "CRAFT_PAGE_MEDIA_SHOWN"
PIECE_TARGET = "KnowledgePiece"
MEDIA_TARGET = "MediaAsset"
PRIVATE = "PRIVATE"
SHARED = "CRAFT_SHARED"
SIMULATION = "simulation"
NAMED_CLUSTER_REASON = "named_cluster_sign_off"
NAMED_CLUSTER_REFUSAL = "A picture of a named cluster is shown again only after both professors sign it off."


async def set_page_piece_hidden(
    session: AsyncSession,
    craft: Craft,
    piece_id: uuid.UUID,
    *,
    hidden: bool,
    user: User,
    now: datetime,
    kind: str | None = None,
) -> bool | None:
    where = [PieceRow.id == piece_id, PieceRow.craftId == craft.id]
    if kind is not None:
        where.append(PieceRow.kind == kind)
    row = await session.scalar(select(PieceRow).where(*where).with_for_update())
    if row is None:
        return None
    changed = hidden != (row.hiddenAt is not None)
    if changed:
        row.hiddenAt = now if hidden else None
        row.hiddenById = user.id if hidden else None
        await audit.record(
            session,
            action=PIECE_HIDDEN_ACTION if hidden else PIECE_SHOWN_ACTION,
            actor=user,
            target_type=PIECE_TARGET,
            target_id=row.id,
            detail={"craft": craft.slug, "kind": row.kind},
        )
    await session.commit()
    if changed:
        await refresh_pages(await craft_owners(session, [craft.id]))
    return hidden


async def set_page_media_hidden(
    session: AsyncSession, craft: Craft, asset_id: uuid.UUID, *, hidden: bool, user: User
) -> bool | None:
    jobs = select(MediaJob.id).where(MediaJob.craftId == craft.id)
    row = await session.scalar(
        select(MediaAsset).where(MediaAsset.id == asset_id, MediaAsset.jobId.in_(jobs)).with_for_update()
    )
    if row is None:
        return None
    if not hidden and row.depictsNamedCluster and row.secondApprovedById is None:
        raise Refused(NAMED_CLUSTER_REASON, NAMED_CLUSTER_REFUSAL)
    wanted = PRIVATE if hidden else SHARED
    changed = row.visibility != wanted
    if changed:
        row.visibility = wanted
        await audit.record(
            session,
            action=MEDIA_HIDDEN_ACTION if hidden else MEDIA_SHOWN_ACTION,
            actor=user,
            target_type=MEDIA_TARGET,
            target_id=row.id,
            detail={"craft": craft.slug},
        )
    await session.commit()
    if changed:
        await refresh_pages(await craft_owners(session, [craft.id]))
    return hidden
