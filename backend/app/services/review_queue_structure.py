from __future__ import annotations

import uuid
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import Refused
from app.models import (
    Claim,
    Craft,
    CuratedCraft,
    ProcessStage,
    Source,
    StructureProposal as ProposalRow,
    User,
)
from app.research.crafts import CraftRef
from app.research.review_queue import STRUCTURE, QueueDecision, StructureQueueItem
from app.research.review_queue_parts import FactSource, RelatedFact, SourceQuote
from app.research.review_queue_structure import StructureReview
from app.research.structure_proposals import (
    BOTANICAL_NAME,
    CONFLICT,
    PENDING_STATUS,
    REACTION,
    STAGE_AFTER,
    STAGE_WHY,
    StructureCheck,
    StructureSubject,
    parsed_item,
)

from .curated_index import CuratedPage, stored_curated_page
from .knowledge_view import craft_ref
from .review_queue_errors import DecisionConflict, OwnItem, UnknownItem
from .review_queue_select import Rendered, rows_by_id
from .structure_proposals import craft_page_url
from .structure_proposals_page import current_value, material_of, stage_of, target_problem
from .structure_proposals_review import approve_structure, reject_structure
from .structure_proposals_write import NO_PAGE

__all__ = ["approve_structure_item", "reject_structure_item", "structure_items"]

MESSAGES = {
    "APPROVED": "Approved: written into the page and its dossier, with its fact cited.",
    "REJECTED": "Rejected: the page stays as it is, and the reason is kept with the proposal.",
}
UNGRADED = "ungraded"
SITE_RELATIVE = ""


@dataclass(frozen=True)
class _Known:
    pages: Mapping[uuid.UUID, CuratedPage | None]
    claims: Mapping[uuid.UUID, str]
    stages: Mapping[uuid.UUID, str]
    grades: Mapping[str, str] = field(default_factory=dict)


async def structure_items(session: AsyncSession, ids: Sequence[uuid.UUID]) -> list[Rendered]:
    rows = list(await session.scalars(select(ProposalRow).where(ProposalRow.id.in_(list(ids)))))
    crafts = await rows_by_id(session, Craft, [row.craftId for row in rows])
    known = await _known(session, rows)
    return [
        Rendered(
            StructureQueueItem(
                id=row.id,
                origin=row.origin,
                submitted_at=row.createdAt,
                craft=CraftRef.model_validate(craft_ref(crafts[row.craftId])),
                structure=_review(row, crafts[row.craftId], known),
            ),
            row.proposerId,
        )
        for row in rows
    ]


async def approve_structure_item(
    session: AsyncSession, proposal_id: uuid.UUID, reviewer: User, *, note: str | None, now: datetime
) -> QueueDecision:
    row = await _pending(session, proposal_id, reviewer)
    try:
        await approve_structure(session, row, reviewer, note=note, now=now)
    except Refused as moved:
        raise DecisionConflict(moved.message) from moved
    return QueueDecision(kind=STRUCTURE, id=row.id, status=row.status, message=MESSAGES[row.status])


async def reject_structure_item(
    session: AsyncSession, proposal_id: uuid.UUID, reviewer: User, *, reason: str, now: datetime
) -> QueueDecision:
    row = await _pending(session, proposal_id, reviewer)
    await reject_structure(session, row, reviewer, reason=reason, now=now)
    return QueueDecision(kind=STRUCTURE, id=row.id, status=row.status, message=MESSAGES[row.status])


async def _pending(session: AsyncSession, proposal_id: uuid.UUID, reviewer: User) -> ProposalRow:
    row = await session.get(ProposalRow, proposal_id, with_for_update=True)
    if row is None:
        raise UnknownItem(f"No structure proposal has the id {proposal_id}.")
    if row.proposerId == reviewer.id:
        raise OwnItem("A reviewer does not decide their own proposal.")
    if row.status != PENDING_STATUS:
        raise DecisionConflict(f"This proposal is {row.status.lower()} already. Reload the queue.")
    return row


async def _known(session: AsyncSession, rows: Sequence[ProposalRow]) -> _Known:
    craft_ids = list({row.craftId for row in rows})
    stored = (
        await session.execute(
            select(CuratedCraft.craftId, CuratedCraft.page).where(CuratedCraft.craftId.in_(craft_ids))
        )
    ).all()
    pages = {craft_id: stored_curated_page(craft_id, page) for craft_id, page in stored}
    claim_ids = [claim for row in rows for claim in _named_claims(row, pages.get(row.craftId))]
    stage_ids = [stage.stage_id for page in pages.values() if page is not None for stage in page.stages]
    claims = await _texts(session, Claim.id, Claim.text, claim_ids)
    stages = await _texts(session, ProcessStage.id, ProcessStage.name, stage_ids)
    source_ids = [
        uuid.UUID(source["sourceId"]) for row in rows for source in row.sources if source["sourceId"]
    ]
    grades = await _texts(session, Source.id, Source.reliability, source_ids)
    return _Known(pages, claims, stages, {str(key): value for key, value in grades.items()})


async def _texts(
    session: AsyncSession, key: Any, value: Any, ids: Iterable[uuid.UUID]
) -> dict[uuid.UUID, str]:
    wanted = list(dict.fromkeys(ids))
    if not wanted:
        return {}
    rows = await session.execute(select(key, value).where(key.in_(wanted)))
    return {found: str(text) for found, text in rows.tuples().all()}


def _named_claims(row: ProposalRow, page: CuratedPage | None) -> list[uuid.UUID]:
    item = parsed_item(row.item)
    if item.kind == CONFLICT:
        return list(item.claim_ids)
    stage = stage_of(page, item.stage_key) if page is not None and item.kind == STAGE_WHY else None
    return [stage.why_claim_id] if stage is not None and stage.why_claim_id is not None else []


def _review(row: ProposalRow, craft: Craft, known: _Known) -> StructureReview:
    item = parsed_item(row.item)
    page = known.pages.get(row.craftId)
    return StructureReview(
        kind=item.kind,
        subject=StructureSubject(slug=craft.slug),
        subject_name=craft.name,
        page_url=craft_page_url(SITE_RELATIVE, craft.slug),
        target=_target(item, page, known),
        current=_current(item, page, known),
        item=item,
        statement=row.statement,
        field=row.field,
        note=row.note,
        task_key=row.taskKey,
        sources=[_source(source, known) for source in row.sources],
        checks=[StructureCheck.model_validate(check) for check in row.checks],
        conflicting=[
            RelatedFact(id=claim_id, text=known.claims.get(claim_id, ""))
            for claim_id in (item.claim_ids if item.kind == CONFLICT else [])
        ],
        stale=NO_PAGE if page is None else target_problem(page, item),
    )


def _target(item: Any, page: CuratedPage | None, known: _Known) -> str | None:
    if page is None:
        return None
    if item.kind in (STAGE_AFTER, STAGE_WHY, REACTION) and getattr(item, "stage_key", None):
        stage = stage_of(page, item.stage_key)
        name = known.stages.get(stage.stage_id) if stage is not None else None
        return f"Stage {item.stage_key}" + (f", {name}" if name else "")
    if item.kind == BOTANICAL_NAME:
        material = material_of(page, item.material_key)
        return f"Material {item.material_key}" + (f", {material.name}" if material else "")
    return None


def _current(item: Any, page: CuratedPage | None, known: _Known) -> str | None:
    if page is None:
        return None
    if item.kind == STAGE_WHY:
        stage = stage_of(page, item.stage_key)
        why = stage.why_claim_id if stage is not None else None
        return known.claims.get(why) if why is not None else None
    return current_value(page, item)


def _source(stored: Mapping[str, Any], known: _Known) -> FactSource:
    return FactSource(
        title=str(stored["title"]),
        url=stored["url"],
        licence=stored.get("licence"),
        reliability=known.grades.get(str(stored.get("sourceId")), UNGRADED),
        quotes=[SourceQuote(text=quote["text"], locator=quote.get("locator")) for quote in stored["quotes"]],
    )
