from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime

from pydantic import ValidationError
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError, InvalidInput
from app.core.roles import Capability, can
from app.models import StagedReview, StagedReviewItem, User
from app.research.page_revalidation import PageOwners
from app.research.review_queue import QueueDecision
from app.research.staged_reviews import (
    APPLIED,
    CONFIRMED,
    DISCARDED,
    OPEN,
    REFUSED,
    SKIPPED,
    ConfirmedItem,
    StagedConfirmation,
    StagedDecision,
    batch_status,
)

from . import audit
from .page_revalidation import merged_owners
from .review_queue_errors import DecisionConflict, NotYourQueue, UnknownItem
from .staged_review_apply import apply_decision, refusal_of

__all__ = ["STAGED_APPLIED", "STAGED_DISCARDED", "Confirmed", "confirm_batch", "discard_batch"]

STAGED_APPLIED = "review.staged_applied"
STAGED_DISCARDED = "review.staged_discarded"
NO_BATCH = "No staged batch has the id {id}."
NOT_OPEN = "This batch is {status}, so nothing in it can be confirmed or discarded."
NOT_IN_BATCH = "These items are not in this batch: {ids}."
NOT_AN_ADMIN = "Confirming staged decisions is for Admins and Master Admins."
OUTCOME_CHARS = 500


@dataclass
class Confirmed:
    batch: StagedReview
    owners: PageOwners = field(default_factory=PageOwners)
    decided: list[QueueDecision] = field(default_factory=list)


@dataclass(frozen=True)
class _Confirming:
    confirmed: Confirmed
    confirmer: User
    now: datetime


async def confirm_batch(
    session: AsyncSession, batch_id: uuid.UUID, chosen: StagedConfirmation, confirmer: User, *, now: datetime
) -> Confirmed:
    batch = await _open_batch(session, batch_id, confirmer, now=now)
    items = list(
        await session.scalars(
            select(StagedReviewItem)
            .where(StagedReviewItem.batchId == batch.id)
            .order_by(StagedReviewItem.position)
        )
    )
    picked = {choice.id: choice for choice in chosen.items}
    strangers = sorted(str(key) for key in picked.keys() - {item.id for item in items})
    if strangers:
        raise InvalidInput(NOT_IN_BATCH.format(ids=", ".join(strangers)))
    confirming = _Confirming(Confirmed(batch), confirmer, now)
    for item in items:
        choice = picked.get(item.id)
        if choice is None:
            item.state = SKIPPED
            continue
        await _confirm_item(session, item, choice, confirming)
    batch.status, batch.decidedById, batch.decidedAt = CONFIRMED, confirmer.id, now
    await session.flush()
    return confirming.confirmed


async def discard_batch(
    session: AsyncSession, batch_id: uuid.UUID, person: User, *, now: datetime
) -> StagedReview:
    batch = await _open_batch(session, batch_id, person, now=now)
    batch.status, batch.decidedById, batch.decidedAt = DISCARDED, person.id, now
    await session.execute(
        update(StagedReviewItem).where(StagedReviewItem.batchId == batch.id).values(state=SKIPPED)
    )
    await audit.record(
        session,
        action=STAGED_DISCARDED,
        actor=person,
        target_type="StagedReview",
        target_id=batch.id,
        detail={"client": batch.clientName},
    )
    await session.flush()
    return batch


async def _open_batch(
    session: AsyncSession, batch_id: uuid.UUID, person: User, *, now: datetime
) -> StagedReview:
    if not can(person, Capability.REVIEW_CONTRIBUTIONS):
        raise NotYourQueue(NOT_AN_ADMIN)
    batch = await session.get(StagedReview, batch_id, with_for_update=True)
    if batch is None:
        raise UnknownItem(NO_BATCH.format(id=batch_id))
    status = batch_status(batch.status, batch.expiresAt, now=now)
    if status != OPEN:
        raise DecisionConflict(NOT_OPEN.format(status=status.lower()))
    return batch


async def _confirm_item(
    session: AsyncSession, item: StagedReviewItem, choice: ConfirmedItem, run: _Confirming
) -> None:
    proposed = StagedDecision.model_validate(item.decision)
    savepoint = await session.begin_nested()
    try:
        final = proposed.changed_to(choice)
        applied = await apply_decision(session, final, run.confirmer, now=run.now)
    except (AppError, ValidationError) as refused:
        await savepoint.rollback()
        item.state, item.outcome = REFUSED, refusal_of(refused)[:OUTCOME_CHARS]
        return
    await savepoint.commit()
    changed = final != proposed
    item.state, item.outcome = APPLIED, applied.message
    item.applied = final.model_dump(mode="json", exclude_none=True) if changed else None
    confirmed = run.confirmed
    confirmed.owners = merged_owners(confirmed.owners, applied.owners)
    if applied.decided is not None:
        confirmed.decided.append(applied.decided)
    await _audited(session, confirmed.batch, final, run.confirmer, changed=changed)


async def _audited(
    session: AsyncSession, batch: StagedReview, final: StagedDecision, confirmer: User, *, changed: bool
) -> None:
    proposer = str(batch.proposerId) if batch.proposerId is not None else None
    await audit.record(
        session,
        action=STAGED_APPLIED,
        actor=confirmer,
        target_type=final.kind,
        target_id=final.id,
        detail={
            "batch": str(batch.id),
            "client": batch.clientName,
            "proposedBy": proposer,
            "action": final.action,
            "changed": changed,
        },
    )
