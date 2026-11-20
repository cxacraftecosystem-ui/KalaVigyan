from __future__ import annotations

import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import InvalidInput, Refused
from app.models import Craft, CraftCategory, LayoutProposal, User
from app.research.crafts import CraftRef
from app.research.layout_proposals import LayoutReview, LayoutSubject, layout_changes
from app.research.page_layout import PageLayoutEntry
from app.research.review_queue import LAYOUTS, LayoutItem, QueueDecision

from . import audit
from .knowledge_view import craft_ref
from .open_work_subjects import WorkSubject, subject_by_key
from .page_layout_proposals import APPROVED, PENDING, REJECTED, current_version, proposal_subject
from .page_layouts import layout_of, store_layout, subject_path
from .review_queue_delivery import placed_deliveries
from .review_queue_errors import DecisionConflict, OwnItem, UnknownItem
from .review_queue_select import Rendered, rows_by_id

__all__ = ["approve_layout", "layout_items", "reject_layout"]

CATEGORY_SUBJECT = "category"
STALE_REVIEW = (
    "The page's layout is at version {current} now, not the version {base} this was built on. Reject it, "
    "and the proposer can build on version {current}."
)
MESSAGES = {
    APPROVED: "Approved: written as version {version} of the page's layout.",
    REJECTED: "Rejected: the page's layout stays as it is, and the reason is kept with the proposal.",
}


@dataclass(frozen=True)
class _Decision:
    status: str
    note: str | None
    action: str


async def layout_items(session: AsyncSession, ids: Sequence[uuid.UUID]) -> list[Rendered]:
    rows = list(await session.scalars(select(LayoutProposal).where(LayoutProposal.id.in_(list(ids)))))
    crafts = await rows_by_id(session, Craft, [row.craftId for row in rows])
    categories = await rows_by_id(session, CraftCategory, [row.categoryId for row in rows])
    rendered = []
    for row in rows:
        craft = crafts.get(row.craftId) if row.craftId is not None else None
        owner = craft if craft is not None else categories[row.categoryId]
        rendered.append(Rendered(await _item(session, row, craft, owner), row.proposerId))
    return rendered


async def approve_layout(
    session: AsyncSession, proposal_id: uuid.UUID, reviewer: User, *, note: str | None, now: datetime
) -> QueueDecision:
    row = await _pending(session, proposal_id, reviewer)
    subject = await _subject(session, row)
    current = await current_version(session, subject)
    if current != row.baseVersion:
        raise DecisionConflict(STALE_REVIEW.format(current=current, base=row.baseVersion))
    try:
        written = await store_layout(session, subject, _entries(row), actor=reviewer)
    except Refused as raced:
        raise DecisionConflict(raced.message) from raced
    row.layoutVersion = written.version
    return await _decided(session, row, reviewer, _Decision(APPROVED, note, "approved"), now=now)


async def reject_layout(
    session: AsyncSession, proposal_id: uuid.UUID, reviewer: User, *, reason: str, now: datetime
) -> QueueDecision:
    row = await _pending(session, proposal_id, reviewer)
    return await _decided(session, row, reviewer, _Decision(REJECTED, reason, "rejected"), now=now)


async def _pending(session: AsyncSession, proposal_id: uuid.UUID, reviewer: User) -> LayoutProposal:
    row = await session.get(LayoutProposal, proposal_id, with_for_update=True)
    if row is None:
        raise UnknownItem(f"No layout proposal has the id {proposal_id}.")
    if row.proposerId == reviewer.id:
        raise OwnItem("A reviewer does not decide their own proposal.")
    if row.status != PENDING:
        raise DecisionConflict(f"This proposal is {row.status.lower()} already. Reload the queue.")
    return row


async def _subject(session: AsyncSession, row: LayoutProposal) -> WorkSubject:
    try:
        return await proposal_subject(session, row)
    except (InvalidInput, Refused) as gone:
        raise DecisionConflict(f"The page of this proposal cannot take a layout now: {gone}") from gone


async def _decided(
    session: AsyncSession, row: LayoutProposal, reviewer: User, decision: _Decision, *, now: datetime
) -> QueueDecision:
    row.status, row.reviewedById, row.reviewedAt, row.reviewNote = (
        decision.status,
        reviewer.id,
        now,
        decision.note,
    )
    await session.flush()
    await audit.record(
        session,
        action=f"review.layout_{decision.action}",
        actor=reviewer,
        target_type="LayoutProposal",
        target_id=row.id,
        detail={"from": PENDING, "to": decision.status, "version": row.layoutVersion},
    )
    message = MESSAGES[row.status].format(version=row.layoutVersion)
    return QueueDecision(kind=LAYOUTS, id=row.id, status=row.status, message=message)


async def _item(
    session: AsyncSession, row: LayoutProposal, craft: Craft | None, owner: Craft | CraftCategory
) -> LayoutItem:
    return LayoutItem(
        id=row.id,
        origin=row.origin,
        submitted_at=row.createdAt,
        craft=CraftRef.model_validate(craft_ref(craft)) if craft is not None else None,
        layout=await _review(session, row, await _shown_subject(session, row, owner)),
    )


async def _shown_subject(
    session: AsyncSession, row: LayoutProposal, owner: Craft | CraftCategory
) -> WorkSubject:
    try:
        return await subject_by_key(session, row.subjectKind, owner.slug)
    except InvalidInput:
        return WorkSubject(id=owner.id, kind=row.subjectKind, slug=owner.slug, name=owner.name, gi=False)


async def _review(session: AsyncSession, row: LayoutProposal, subject: WorkSubject) -> LayoutReview:
    current = await layout_of(session, subject)
    proposed = _entries(row)
    version = 0 if current is None else current.version
    return LayoutReview(
        subject=LayoutSubject(kind=subject.kind, slug=subject.slug),
        subject_name=subject.name,
        page_url=subject_path(subject),
        base_version=row.baseVersion,
        current_version=version,
        stale=version != row.baseVersion,
        note=row.note,
        entry_count=len(proposed),
        changes=layout_changes([] if current is None else current.entries, proposed),
        placed=await placed_deliveries(
            session,
            row.proposerId,
            [entry.ref for entry in proposed],
            None if subject.kind == CATEGORY_SUBJECT else subject.slug,
        ),
    )


def _entries(row: LayoutProposal) -> list[PageLayoutEntry]:
    return [PageLayoutEntry.model_validate(entry) for entry in row.entries]
