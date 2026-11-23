from __future__ import annotations

import uuid
from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import exists, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import InvalidInput
from app.models import Claim, Concept, Craft, Process, ProcessStage, StageReview, User
from app.research.crafts import CraftRef
from app.research.retrieval import SHOWN_CLAIM_STATUSES
from app.research.review_queue import STAGES, QueueApproval, QueueDecision, QueueRejection, StageQueueItem
from app.research.review_queue_stages import (
    CHOOSE_PROCESS,
    PLACED_STATUS,
    REJECTED_STAGE_STATUS,
    STAGE_CONCEPT_TYPE,
    STAGE_FACTS_MAX,
    ProcessStep,
    StageFact,
    StagePlacing,
    StageProcess,
    stage_place,
)
from app.research.review_switch import RESEARCH

from . import audit
from .claim_writer import LIVE_CONCEPT_ORIGIN
from .curation_writes import update_rows
from .knowledge_view import craft_ref
from .review_queue_errors import DecisionConflict, UnknownItem
from .review_queue_fact_views import fact_sources
from .review_queue_select import Rendered, placeable_process, rows_by_id

__all__ = ["approve_stage_item", "reject_stage_item", "stage_items"]

CONCEPT_SUBJECT = "CONCEPT"
MESSAGES = {
    PLACED_STATUS: "Placed: the stage is written into the craft's process where you chose.",
    REJECTED_STAGE_STATUS: "Rejected: the process stays as it is, and the reason is kept with the stage.",
}
DECIDED = "This stage is decided already. Reload the queue."
NOT_PLACEABLE = "That process does not take new stages for this craft. Reload the queue."


async def stage_items(session: AsyncSession, ids: Sequence[uuid.UUID]) -> list[Rendered]:
    concepts = list(await session.scalars(select(Concept).where(Concept.id.in_(list(ids)))))
    crafts = await rows_by_id(session, Craft, [concept.craftId for concept in concepts])
    processes = await _processes(session, list(crafts))
    facts = await _facts(session, [concept.id for concept in concepts])
    return [
        Rendered(
            StageQueueItem(
                id=concept.id,
                origin=RESEARCH,
                submitted_at=concept.createdAt,
                craft=CraftRef.model_validate(craft_ref(crafts[concept.craftId])),
                stage=StagePlacing(
                    name=concept.name,
                    description=concept.description,
                    processes=processes[concept.craftId],
                    facts=facts.get(concept.id, []),
                ),
            ),
            None,
        )
        for concept in concepts
        if concept.craftId in crafts and processes.get(concept.craftId)
    ]


async def approve_stage_item(
    session: AsyncSession, concept_id: uuid.UUID, reviewer: User, decision: QueueApproval, *, now: datetime
) -> QueueDecision:
    concept = await _waiting(session, concept_id)
    if decision.process_id is None:
        raise InvalidInput(CHOOSE_PROCESS)
    steps = await _steps(session, concept, decision.process_id)
    place = stage_place(steps, decision.after_stage_id)
    moved = [{"id": stage_id, "ordinal": ordinal} for stage_id, ordinal in place.moved]
    await update_rows(session, ProcessStage, [{**row, "ordinal": -row["ordinal"]} for row in moved])
    await update_rows(session, ProcessStage, moved)
    stage = ProcessStage(
        processId=decision.process_id, ordinal=place.ordinal, conceptId=concept.id, name=concept.name
    )
    session.add(stage)
    await session.flush()
    return await _decided(session, concept, reviewer, _Review(PLACED_STATUS, decision.note, stage.id, now))


async def reject_stage_item(
    session: AsyncSession, concept_id: uuid.UUID, reviewer: User, decision: QueueRejection, *, now: datetime
) -> QueueDecision:
    concept = await _waiting(session, concept_id)
    review = _Review(REJECTED_STAGE_STATUS, decision.stated(), None, now)
    return await _decided(session, concept, reviewer, review)


@dataclass(frozen=True)
class _Review:
    status: str
    note: str | None
    stage_id: uuid.UUID | None
    now: datetime


async def _decided(session: AsyncSession, concept: Concept, reviewer: User, review: _Review) -> QueueDecision:
    session.add(
        StageReview(
            conceptId=concept.id,
            status=review.status,
            note=review.note,
            reviewerId=reviewer.id,
            processStageId=review.stage_id,
            createdAt=review.now,
        )
    )
    await audit.record(
        session,
        action=f"review.stage_{review.status.lower()}",
        actor=reviewer,
        target_type="Concept",
        target_id=concept.id,
        detail={"to": review.status, "processStageId": str(review.stage_id) if review.stage_id else None},
    )
    await session.flush()
    return QueueDecision(kind=STAGES, id=concept.id, status=review.status, message=MESSAGES[review.status])


async def _waiting(session: AsyncSession, concept_id: uuid.UUID) -> Concept:
    concept = await session.get(Concept, concept_id, with_for_update=True)
    if concept is None or not _answer_found(concept):
        raise UnknownItem(f"No process stage answers found has the id {concept_id}.")
    placed = exists().where(ProcessStage.conceptId == concept.id)
    reviewed = exists().where(StageReview.conceptId == concept.id)
    if await session.scalar(select(placed | reviewed)):
        raise DecisionConflict(DECIDED)
    return concept


def _answer_found(concept: Concept) -> bool:
    kept = concept.type == STAGE_CONCEPT_TYPE and concept.originRef == LIVE_CONCEPT_ORIGIN
    return kept and concept.craftId is not None


async def _steps(session: AsyncSession, concept: Concept, process_id: uuid.UUID) -> list[ProcessStep]:
    process = await session.scalar(
        select(Process.id)
        .where(Process.id == process_id, Process.craftId == concept.craftId, placeable_process())
        .with_for_update()
    )
    if process is None:
        raise DecisionConflict(NOT_PLACEABLE)
    rows = await session.execute(
        select(ProcessStage.id, ProcessStage.ordinal, ProcessStage.name).where(
            ProcessStage.processId == process
        )
    )
    return [ProcessStep(id=stage_id, ordinal=ordinal, name=name) for stage_id, ordinal, name in rows.all()]


async def _processes(
    session: AsyncSession, craft_ids: list[uuid.UUID]
) -> dict[uuid.UUID, list[StageProcess]]:
    if not craft_ids:
        return {}
    rows = await session.execute(
        select(
            Process.craftId,
            Process.id,
            Process.name,
            ProcessStage.id,
            ProcessStage.ordinal,
            ProcessStage.name,
        )
        .join(ProcessStage, ProcessStage.processId == Process.id)
        .where(Process.craftId.in_(craft_ids), placeable_process())
        .order_by(Process.name, Process.id, ProcessStage.ordinal)
    )
    named: dict[uuid.UUID, tuple[uuid.UUID, str]] = {}
    steps: dict[uuid.UUID, list[ProcessStep]] = defaultdict(list)
    for craft_id, process_id, process_name, stage_id, ordinal, stage_name in rows.tuples().all():
        named[process_id] = (craft_id, process_name)
        steps[process_id].append(ProcessStep(id=stage_id, ordinal=ordinal, name=stage_name))
    found: dict[uuid.UUID, list[StageProcess]] = defaultdict(list)
    for process_id, (craft_id, name) in named.items():
        found[craft_id].append(StageProcess(id=process_id, name=name, stages=steps[process_id]))
    return found


async def _facts(session: AsyncSession, concept_ids: list[uuid.UUID]) -> dict[uuid.UUID, list[StageFact]]:
    if not concept_ids:
        return {}
    rows = await session.execute(
        select(Claim.subjectId, Claim.id, Claim.text)
        .where(
            Claim.subjectType == CONCEPT_SUBJECT,
            Claim.subjectId.in_(concept_ids),
            Claim.status.in_(SHOWN_CLAIM_STATUSES),
        )
        .order_by(Claim.subjectId, Claim.createdAt, Claim.id)
    )
    kept: dict[uuid.UUID, list[tuple[uuid.UUID, str]]] = defaultdict(list)
    for concept_id, claim_id, text in rows.tuples().all():
        if len(kept[concept_id]) < STAGE_FACTS_MAX:
            kept[concept_id].append((claim_id, text))
    sources = await fact_sources(session, [claim for told in kept.values() for claim, _ in told])
    return {
        concept_id: [StageFact(id=claim, text=text, sources=sources.get(claim, [])) for claim, text in told]
        for concept_id, told in kept.items()
    }
