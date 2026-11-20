from __future__ import annotations

import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ComponentProposal, Craft, User
from app.research.component_proposals import SUBJECT_LINK, ComponentProposalDraft, ProposedSubject
from app.research.crafts import QUESTION_MAX_CHARS, CraftRef
from app.research.review_queue import COMPONENTS, KIND_ORIGINS, ComponentItem, QueueDecision
from app.research.review_queue_components import ClosestComponent, ComponentReview, closest_components

from . import audit
from .component_library import library_components
from .component_proposals_register import register_component, registers
from .knowledge_view import craft_ref
from .review_queue_delivery import delivered_review
from .review_queue_errors import DecisionConflict, OwnItem, UnknownItem
from .review_queue_select import PENDING, Rendered, rows_by_id

__all__ = ["approve_component", "component_items", "reject_component"]

APPROVED = "APPROVED"
REJECTED = "REJECTED"
COMPONENT_ORIGIN = KIND_ORIGINS[COMPONENTS][0]
MESSAGES = {
    APPROVED: "Approved for a builder: it waits to be built and registered in the library.",
    REJECTED: "Rejected: it will not be built, and the reason is kept with the proposal.",
}
REGISTERED = "Approved and registered in the library: every page it applies to draws it from its spec."
LINKED = "Approved and linked: the registered component is keyed to its new subjects."


@dataclass(frozen=True)
class _Decision:
    status: str
    note: str | None
    action: str


async def component_items(session: AsyncSession, ids: Sequence[uuid.UUID]) -> list[Rendered]:
    rows = list(await session.scalars(select(ComponentProposal).where(ComponentProposal.id.in_(list(ids)))))
    crafts = await rows_by_id(session, Craft, [row.craftId for row in rows])
    rendered = []
    for row in rows:
        craft = crafts.get(row.craftId) if row.craftId is not None else None
        rendered.append(Rendered(await _item(session, row, craft), row.proposerId))
    return rendered


async def approve_component(
    session: AsyncSession, proposal_id: uuid.UUID, reviewer: User, *, note: str | None, now: datetime
) -> QueueDecision:
    return await _decided(session, proposal_id, reviewer, _Decision(APPROVED, note, "approved"), now=now)


async def reject_component(
    session: AsyncSession, proposal_id: uuid.UUID, reviewer: User, *, reason: str, now: datetime
) -> QueueDecision:
    return await _decided(session, proposal_id, reviewer, _Decision(REJECTED, reason, "rejected"), now=now)


async def _decided(
    session: AsyncSession, proposal_id: uuid.UUID, reviewer: User, decision: _Decision, *, now: datetime
) -> QueueDecision:
    row = await session.get(ComponentProposal, proposal_id, with_for_update=True)
    if row is None:
        raise UnknownItem(f"No component proposal has the id {proposal_id}.")
    if row.proposerId == reviewer.id:
        raise OwnItem("A reviewer does not decide their own proposal.")
    if row.status != PENDING:
        raise DecisionConflict(f"This proposal is {row.status.lower()} already. Reload the queue.")
    row.status, row.reviewedById, row.reviewedAt, row.reviewNote = (
        decision.status,
        reviewer.id,
        now,
        decision.note,
    )
    await session.flush()
    registered = decision.status == APPROVED and registers(row)
    if registered:
        await register_component(session, row)
    await audit.record(
        session,
        action=f"review.component_{decision.action}",
        actor=reviewer,
        target_type="ComponentProposal",
        target_id=row.id,
        detail={"from": PENDING, "to": decision.status},
    )
    return QueueDecision(kind=COMPONENTS, id=row.id, status=row.status, message=_message(row, registered))


def _message(row: ComponentProposal, registered: bool) -> str:
    if not registered:
        return MESSAGES[row.status]
    return LINKED if row.extension == SUBJECT_LINK else REGISTERED


async def _item(session: AsyncSession, row: ComponentProposal, craft: Craft | None) -> ComponentItem:
    draft = _draft(row, craft.slug if craft is not None else None)
    return ComponentItem(
        id=row.id,
        origin=COMPONENT_ORIGIN,
        submitted_at=row.createdAt,
        craft=CraftRef.model_validate(craft_ref(craft)) if craft is not None else None,
        component=ComponentReview(
            label=row.label,
            title=row.title,
            description=row.description,
            kind=row.kind,
            field=row.field,
            fields=list(row.fields),
            subjects=list(draft.subjects),
            considered_labels=list(row.consideredLabels),
            extends=row.extendsLabel,
            extension=row.extension,
            task_key=row.taskKey,
            closest=await _closest(session, draft),
            delivery=await delivered_review(session, row, draft.craft_slug),
        ),
    )


async def _closest(session: AsyncSession, draft: ComponentProposalDraft) -> list[ClosestComponent]:
    words = f"{draft.title} {draft.description}"[:QUESTION_MAX_CHARS]
    found = list((await library_components(session, query=words)).components)
    if draft.craft_slug is not None:
        found += (await library_components(session, slug=draft.craft_slug, kind=draft.kind)).components
    return closest_components(draft, found)


def _draft(row: ComponentProposal, craft_slug: str | None) -> ComponentProposalDraft:
    return ComponentProposalDraft.model_construct(
        label=row.label,
        title=row.title,
        description=row.description,
        kind=row.kind,
        field=row.field,
        fields=list(row.fields),
        craft_slug=craft_slug,
        subjects=[ProposedSubject.model_validate(subject) for subject in row.subjects],
        considered_labels=list(row.consideredLabels),
        extends=row.extendsLabel,
        extension=row.extension,
        task_key=row.taskKey,
    )
