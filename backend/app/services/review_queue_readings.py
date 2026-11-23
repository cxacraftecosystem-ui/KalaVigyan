from __future__ import annotations

import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    Claim,
    ClaimSource,
    ConditionReading,
    Craft,
    Process,
    ProcessCondition,
    ProcessStage,
    Reaction,
    User,
)
from app.models.science import live_process
from app.research.crafts import CraftRef
from app.research.open_work import QueueStanding
from app.research.review_queue import READINGS, QueueDecision, QueueEntry, QueueKey, ReadingQueueItem
from app.research.review_queue_readings import ReadingReview, reading_origin
from app.science.reading_checks import ReadingCheck, enveloped, reading_check
from app.science.units import Bounds

from . import audit
from .knowledge_view import craft_ref
from .review_queue_errors import DecisionConflict, OwnItem, UnknownItem
from .review_queue_fact_views import fact_sources
from .review_queue_select import Rendered, rows_by_id

__all__ = [
    "MESSAGES",
    "ReadingScope",
    "decide_reading",
    "outside_readings",
    "reading_count",
    "reading_craft",
    "reading_entries",
    "reading_items",
    "reading_standing",
]

MESSAGES = {
    "APPROVED": "Approved: the reading stands as its source states it, shown outside its stage's usual range.",
    "REJECTED": "Rejected: the reading leaves the page, and the reason is kept with it.",
}
TARGET = "ConditionReading"
OWN_READING = "A reviewer does not decide a reading of a fact they wrote."


@dataclass(frozen=True)
class ReadingScope:
    viewer_id: uuid.UUID | None = None
    craft_id: uuid.UUID | None = None
    origin: str | None = None
    ids: tuple[uuid.UUID, ...] | None = None


@dataclass(frozen=True)
class OutsideReading:
    row: ConditionReading
    condition: str
    quantity: str
    stage: str
    stage_type: str
    craft_id: uuid.UUID
    claim_id: uuid.UUID
    statement: str
    origin: str
    writer_id: uuid.UUID | None
    check: ReadingCheck

    @property
    def key(self) -> QueueKey:
        return QueueKey(self.row.createdAt, self.row.id)


async def outside_readings(session: AsyncSession, scope: ReadingScope) -> list[OutsideReading]:
    rows = (await session.execute(_readings(scope))).all()
    found = [_outside(row) for row in rows]
    kept = [reading for reading in found if reading.check.outside]
    if scope.origin is not None:
        kept = [reading for reading in kept if reading.origin == scope.origin]
    return sorted(kept, key=lambda reading: reading.key, reverse=True)


async def reading_entries(
    session: AsyncSession, scope: ReadingScope, *, before: QueueKey | None, limit: int
) -> list[QueueEntry]:
    found = await outside_readings(session, scope)
    keys = [reading.key for reading in found if before is None or reading.key < before]
    return [QueueEntry(key, READINGS) for key in keys[:limit]]


async def reading_count(session: AsyncSession, scope: ReadingScope) -> int:
    return len(await outside_readings(session, scope))


async def reading_standing(session: AsyncSession) -> QueueStanding:
    found = await outside_readings(session, ReadingScope())
    return QueueStanding(count=len(found), oldest=min((r.row.createdAt for r in found), default=None))


async def reading_items(session: AsyncSession, ids: Sequence[uuid.UUID]) -> list[Rendered]:
    found = await outside_readings(session, ReadingScope(ids=tuple(ids)))
    crafts = await rows_by_id(session, Craft, [reading.craft_id for reading in found])
    sources = await fact_sources(session, [reading.claim_id for reading in found])
    return [
        Rendered(
            ReadingQueueItem(
                id=reading.row.id,
                origin=reading.origin,
                submitted_at=reading.row.createdAt,
                craft=CraftRef.model_validate(craft_ref(crafts[reading.craft_id])),
                reading=_review(reading, sources.get(reading.claim_id, [])),
            ),
            reading.writer_id,
        )
        for reading in found
        if reading.craft_id in crafts
    ]


async def decide_reading(
    session: AsyncSession,
    reading_id: uuid.UUID,
    reviewer: User,
    decision: tuple[str, str | None],
    *,
    now: datetime,
) -> QueueDecision:
    status, note = decision
    row = await session.get(ConditionReading, reading_id, with_for_update=True)
    if row is None:
        raise UnknownItem(f"No reading has the id {reading_id}.")
    if row.reviewStatus is not None:
        raise DecisionConflict(f"This reading is {row.reviewStatus.lower()} already. Reload the queue.")
    writer = await session.scalar(
        select(Claim.createdById)
        .join(ClaimSource, ClaimSource.claimId == Claim.id)
        .where(ClaimSource.id == row.claimSourceId)
    )
    if writer is not None and writer == reviewer.id:
        raise OwnItem(OWN_READING)
    row.reviewStatus, row.reviewedById, row.reviewedAt, row.reviewNote = status, reviewer.id, now, note
    await audit.record(
        session,
        action=f"review.reading_{status.lower()}",
        actor=reviewer,
        target_type=TARGET,
        target_id=row.id,
        detail={"from": None, "to": status, "stated": row.stated},
    )
    await session.flush()
    return QueueDecision(kind=READINGS, id=row.id, status=status, message=MESSAGES[status])


def reading_craft(reading_id: uuid.UUID) -> Select[Any]:
    return (
        select(Process.craftId)
        .select_from(ConditionReading)
        .join(ProcessCondition, ProcessCondition.id == ConditionReading.conditionId)
        .outerjoin(Reaction, Reaction.id == ProcessCondition.reactionId)
        .join(ProcessStage, ProcessStage.id == func.coalesce(ProcessCondition.stageId, Reaction.stageId))
        .join(Process, Process.id == ProcessStage.processId)
        .where(ConditionReading.id == reading_id)
    )


def _readings(scope: ReadingScope) -> Select[Any]:
    stage_types = sorted({stage_type for stage_type, _ in enveloped()})
    statement = (
        select(
            ConditionReading,
            ProcessCondition.label,
            ProcessCondition.quantity,
            ProcessStage.name,
            ProcessStage.stageType,
            Process.craftId,
            Claim.id,
            Claim.text,
            Claim.origin,
            Claim.createdById,
            ClaimSource.foundBy,
        )
        .join(ProcessCondition, ProcessCondition.id == ConditionReading.conditionId)
        .outerjoin(Reaction, Reaction.id == ProcessCondition.reactionId)
        .join(ProcessStage, ProcessStage.id == func.coalesce(ProcessCondition.stageId, Reaction.stageId))
        .join(Process, Process.id == ProcessStage.processId)
        .join(ClaimSource, ClaimSource.id == ConditionReading.claimSourceId)
        .join(Claim, Claim.id == ClaimSource.claimId)
        .where(
            ConditionReading.reviewStatus.is_(None), live_process(), ProcessStage.stageType.in_(stage_types)
        )
    )
    if scope.viewer_id is not None:
        statement = statement.where(Claim.createdById.is_distinct_from(scope.viewer_id))
    if scope.craft_id is not None:
        statement = statement.where(Process.craftId == scope.craft_id)
    if scope.ids is not None:
        statement = statement.where(ConditionReading.id.in_(list(scope.ids)))
    return statement


def _outside(found: Any) -> OutsideReading:
    row, condition, quantity, stage, stage_type, craft_id, claim_id, text, origin, writer, found_by = found
    stated = Bounds(_number(row.statedMin), _number(row.statedMax))
    return OutsideReading(
        row=row,
        condition=condition,
        quantity=quantity,
        stage=stage,
        stage_type=str(stage_type),
        craft_id=craft_id,
        claim_id=claim_id,
        statement=text,
        origin=reading_origin(str(origin), [found_by]),
        writer_id=writer,
        check=reading_check(str(stage_type), quantity, stated, row.statedUnit),
    )


def _review(reading: OutsideReading, sources: list[Any]) -> ReadingReview:
    envelope = reading.check.envelope
    return ReadingReview(
        stated=reading.row.stated,
        quantity=reading.quantity,
        unit=reading.check.unit,
        min=reading.check.bounds.low,
        max=reading.check.bounds.high,
        envelope_min=envelope.min,
        envelope_max=envelope.max,
        condition=reading.condition,
        stage=reading.stage,
        stage_type=reading.stage_type,
        claim_id=reading.claim_id,
        statement=reading.statement,
        sources=sources,
    )


def _number(value: Decimal | None) -> float | None:
    return None if value is None else float(value)
