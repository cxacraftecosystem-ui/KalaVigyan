from __future__ import annotations

import uuid
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import Refused
from app.models import Claim, Craft, ProcessStage, Source, StructureProposal as ProposalRow, User
from app.research.crafts import CraftRef
from app.research.review_queue import STRUCTURE, QueueDecision, StructureQueueItem
from app.research.review_queue_parts import FactSource, RelatedFact, SourceQuote
from app.research.review_queue_structure import StructureReview
from app.research.structure_proposals import (
    ALTERNATIVE,
    BOTANICAL_NAME,
    CONFLICT,
    GROUP_NAME,
    PENDING_STATUS,
    REACTION,
    STAGE_AFTER,
    STAGE_WHY,
    StructureCheck,
    parsed_item,
)

from .curated_index import CuratedPage
from .knowledge_view import craft_ref
from .review_queue_errors import DecisionConflict, OwnItem, UnknownItem
from .review_queue_select import Rendered, rows_by_id
from .structure_proposals_owner import StructureOwner, owner_page, proposal_owner
from .structure_proposals_page import OwnerPage, current_value, material_of, stage_of, target_problem
from .structure_proposals_review import approve_structure, reject_structure
from .structure_proposals_write import NO_PAGE, held_claims

__all__ = ["approve_structure_item", "reject_structure_item", "structure_items"]

MESSAGES = {
    "APPROVED": "Approved: written into the page and its dossier, with its fact cited.",
    "REJECTED": "Rejected: the page stays as it is, and the reason is kept with the proposal.",
}
NAME_APPROVED = (
    "Approved: the name joins the craft's list of names kept out of AI pictures, which readers never see."
)
UNGRADED = "ungraded"
SITE_RELATIVE = ""


@dataclass(frozen=True)
class _Subject:
    owner: StructureOwner
    page: OwnerPage | None
    held: frozenset[uuid.UUID] | None


@dataclass(frozen=True)
class _Known:
    claims: Mapping[uuid.UUID, str]
    stages: Mapping[uuid.UUID, str]
    grades: Mapping[str, str] = field(default_factory=dict)


async def structure_items(session: AsyncSession, ids: Sequence[uuid.UUID]) -> list[Rendered]:
    rows = list(await session.scalars(select(ProposalRow).where(ProposalRow.id.in_(list(ids)))))
    subjects = {row.id: subject for row in rows if (subject := await _subject(session, row)) is not None}
    crafts = await rows_by_id(session, Craft, [row.craftId for row in rows])
    known = await _known(session, rows, subjects)
    return [
        Rendered(
            StructureQueueItem(
                id=row.id,
                origin=row.origin,
                submitted_at=row.createdAt,
                craft=_craft(crafts.get(row.craftId) if row.craftId else None),
                structure=_review(row, subjects[row.id], known),
            ),
            row.proposerId,
        )
        for row in rows
        if row.id in subjects
    ]


async def approve_structure_item(
    session: AsyncSession, proposal_id: uuid.UUID, reviewer: User, *, note: str | None, now: datetime
) -> QueueDecision:
    row = await _pending(session, proposal_id, reviewer)
    try:
        await approve_structure(session, row, reviewer, note=note, now=now)
    except Refused as moved:
        raise DecisionConflict(moved.message) from moved
    message = NAME_APPROVED if row.kind == GROUP_NAME else MESSAGES[row.status]
    return QueueDecision(kind=STRUCTURE, id=row.id, status=row.status, message=message)


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


async def _subject(session: AsyncSession, row: ProposalRow) -> _Subject | None:
    owner = await proposal_owner(session, row)
    if owner is None:
        return None
    page = await owner_page(session, owner, lock=False)
    return _Subject(owner, page, await held_claims(session, owner))


def _craft(craft: Craft | None) -> CraftRef | None:
    return CraftRef.model_validate(craft_ref(craft)) if craft is not None else None


async def _known(
    session: AsyncSession, rows: Sequence[ProposalRow], subjects: Mapping[uuid.UUID, _Subject]
) -> _Known:
    pages = [subject.page for subject in subjects.values()]
    claim_ids = [
        claim for row in rows if row.id in subjects for claim in _named_claims(row, subjects[row.id].page)
    ]
    stage_ids = [stage.stage_id for page in pages if isinstance(page, CuratedPage) for stage in page.stages]
    claims = await _texts(session, Claim.id, Claim.text, claim_ids)
    stages = await _texts(session, ProcessStage.id, ProcessStage.name, stage_ids)
    source_ids = [
        uuid.UUID(source["sourceId"]) for row in rows for source in row.sources if source["sourceId"]
    ]
    grades = await _texts(session, Source.id, Source.reliability, source_ids)
    return _Known(claims, stages, {str(key): value for key, value in grades.items()})


async def _texts(
    session: AsyncSession, key: Any, value: Any, ids: Iterable[uuid.UUID]
) -> dict[uuid.UUID, str]:
    wanted = list(dict.fromkeys(ids))
    if not wanted:
        return {}
    rows = await session.execute(select(key, value).where(key.in_(wanted)))
    return {found: str(text) for found, text in rows.tuples().all()}


def _named_claims(row: ProposalRow, page: OwnerPage | None) -> list[uuid.UUID]:
    item = parsed_item(row.item)
    if item.kind == CONFLICT:
        return list(item.claim_ids)
    if not isinstance(page, CuratedPage) or item.kind != STAGE_WHY:
        return []
    stage = stage_of(page, item.stage_key)
    return [stage.why_claim_id] if stage is not None and stage.why_claim_id is not None else []


def _review(row: ProposalRow, subject: _Subject, known: _Known) -> StructureReview:
    item = parsed_item(row.item)
    owner, page = subject.owner, subject.page
    return StructureReview(
        kind=item.kind,
        subject=owner.subject,
        subject_name=owner.name,
        page_url=owner.page_url(SITE_RELATIVE),
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
        stale=_stale(item, subject),
    )


def _stale(item: Any, subject: _Subject) -> str | None:
    if item.kind == GROUP_NAME:
        return None
    if subject.page is None:
        return NO_PAGE
    return target_problem(subject.page, item, held=subject.held)


def _target(item: Any, page: OwnerPage | None, known: _Known) -> str | None:
    if page is None:
        return None
    if isinstance(page, CuratedPage) and item.kind in (STAGE_AFTER, STAGE_WHY, REACTION):
        stage = stage_of(page, getattr(item, "stage_key", None)) if getattr(item, "stage_key", None) else None
        if stage is None:
            return None
        name = known.stages.get(stage.stage_id)
        return f"Stage {item.stage_key}" + (f", {name}" if name else "")
    if item.kind == ALTERNATIVE:
        named = _material_line(page, item.material_key)
        return f"{named}, with {_material_line(page, item.alternative_key).lower()} as its alternative"
    if item.kind == BOTANICAL_NAME:
        return _material_line(page, item.material_key)
    return None


def _material_line(page: OwnerPage, key: str) -> str:
    material = material_of(page, key)
    return f"Material {key}" + (f", {material.name}" if material else "")


def _current(item: Any, page: OwnerPage | None, known: _Known) -> str | None:
    if page is None:
        return None
    if isinstance(page, CuratedPage) and item.kind == STAGE_WHY:
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
