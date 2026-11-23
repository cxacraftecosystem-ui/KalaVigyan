from __future__ import annotations

import uuid
from collections.abc import Iterable
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import StagedReview, StagedReviewItem, User
from app.research.staged_reviews import (
    BATCHES_SHOWN,
    OPEN,
    StagedBatchList,
    StagedBatchView,
    StagedDecision,
    StagedItemView,
    batch_status,
)

__all__ = ["batch_view", "open_batches"]


async def open_batches(session: AsyncSession, *, now: datetime) -> StagedBatchList:
    batches = await session.scalars(
        select(StagedReview)
        .where(StagedReview.status == OPEN, StagedReview.expiresAt > now)
        .order_by(StagedReview.createdAt.desc())
        .limit(BATCHES_SHOWN)
    )
    return StagedBatchList(batches=[await batch_view(session, batch, now=now) for batch in batches.all()])


async def batch_view(
    session: AsyncSession, batch: StagedReview, *, now: datetime, refresh: str | None = None
) -> StagedBatchView:
    items = await session.scalars(
        select(StagedReviewItem)
        .where(StagedReviewItem.batchId == batch.id)
        .order_by(StagedReviewItem.position)
    )
    names = await _names(session, (batch.proposerId, batch.decidedById))
    return StagedBatchView(
        id=batch.id,
        status=batch_status(batch.status, batch.expiresAt, now=now),
        client_name=batch.clientName,
        proposed_by=names.get(batch.proposerId) if batch.proposerId else None,
        created_at=batch.createdAt,
        expires_at=batch.expiresAt,
        decided_by=names.get(batch.decidedById) if batch.decidedById else None,
        decided_at=batch.decidedAt,
        refresh=refresh,
        items=[_item_view(item) for item in items.all()],
    )


def _item_view(item: StagedReviewItem) -> StagedItemView:
    return StagedItemView(
        id=item.id,
        position=item.position,
        label=item.label,
        decision=StagedDecision.model_validate(item.decision),
        state=item.state,
        applied=None if item.applied is None else StagedDecision.model_validate(item.applied),
        outcome=item.outcome,
    )


async def _names(session: AsyncSession, ids: Iterable[uuid.UUID | None]) -> dict[uuid.UUID, str]:
    wanted = [key for key in ids if key is not None]
    if not wanted:
        return {}
    rows = await session.execute(select(User.id, User.name).where(User.id.in_(wanted)))
    return dict(rows.tuples().all())
