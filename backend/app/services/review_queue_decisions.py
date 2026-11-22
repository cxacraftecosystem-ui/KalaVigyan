from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable, Iterator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
from types import MappingProxyType

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import InvalidInput
from app.core.roles import can
from app.models import ImageContribution, User
from app.research.open_work import REVIEW_QUEUE_LABELS
from app.research.review_queue import (
    APPROVE,
    COMPONENTS,
    FACTS,
    IMAGES,
    LAYOUTS,
    RAISE,
    REJECT,
    RETRACT,
    STRUCTURE,
    TESTIMONY,
    FactLevelRaise,
    FactRetraction,
    QueueApproval,
    QueueDecision,
    QueueRejection,
    decision_capability,
)

from . import audit, image_contributions as images, testimony_writes
from .review_queue_components import approve_component, reject_component
from .review_queue_errors import DecisionConflict, NotYourQueue, OwnItem, UnknownItem
from .review_queue_facts import FactDecision, decide_fact
from .review_queue_layouts import approve_layout, reject_layout
from .review_queue_refile import refiling_problem
from .review_queue_structure import approve_structure_item, reject_structure_item
from .testimony_store import MoveRefused, OwnContribution, StaleContribution, UnknownContribution

__all__ = ["ItemRef", "approve_item", "raise_fact", "reject_item", "retract_fact"]

OTHER_REASON = "OTHER"
VERSION_NEEDED = "A testimony decision names the version it was read at."
STALE_TESTIMONY = "Someone changed this testimony since it was read. Reload it."
MOVED_TESTIMONY = "This testimony cannot be decided that way now. Reload it."
OWN_ITEM = "A reviewer does not decide their own contribution."
MESSAGES = {
    (TESTIMONY, "APPROVED"): "Approved: the words are shown as the artisan's own account.",
    (TESTIMONY, "REJECTED"): "Rejected: the words are not shown, and the reason is kept.",
    (IMAGES, "APPROVED"): "Approved: the picture is shared on the craft.",
    (IMAGES, "REJECTED"): "Rejected: the picture stays private, and the reason is kept.",
}

Decide = Callable[..., Awaitable[QueueDecision]]


@dataclass(frozen=True)
class ItemRef:
    kind: str
    item_id: uuid.UUID


async def approve_item(
    session: AsyncSession, ref: ItemRef, reviewer: User, decision: QueueApproval, *, now: datetime
) -> QueueDecision:
    _allowed(reviewer, ref.kind, APPROVE)
    problem = refiling_problem(ref.kind, decision.craft)
    if problem is not None:
        raise InvalidInput(problem)
    return await _APPROVERS[ref.kind](session, ref.item_id, reviewer, decision, now=now)


async def reject_item(
    session: AsyncSession, ref: ItemRef, reviewer: User, decision: QueueRejection, *, now: datetime
) -> QueueDecision:
    _allowed(reviewer, ref.kind, REJECT)
    return await _REJECTERS[ref.kind](session, ref.item_id, reviewer, decision, now=now)


async def raise_fact(
    session: AsyncSession, claim_id: uuid.UUID, reviewer: User, decision: FactLevelRaise, *, now: datetime
) -> QueueDecision:
    _allowed(reviewer, FACTS, RAISE)
    return await decide_fact(session, claim_id, reviewer, FactDecision(RAISE, decision.note), now=now)


async def retract_fact(
    session: AsyncSession, claim_id: uuid.UUID, reviewer: User, decision: FactRetraction, *, now: datetime
) -> QueueDecision:
    _allowed(reviewer, FACTS, RETRACT)
    return await decide_fact(session, claim_id, reviewer, FactDecision(RETRACT, decision.reason), now=now)


def _allowed(reviewer: User, kind: str, action: str) -> None:
    if not can(reviewer, decision_capability(kind, action)):
        raise NotYourQueue(f"Your account does not review {REVIEW_QUEUE_LABELS[kind]}.")


async def _approve_fact(
    session: AsyncSession, item_id: uuid.UUID, reviewer: User, decision: QueueApproval, *, now: datetime
) -> QueueDecision:
    approval = FactDecision(APPROVE, decision.note, craft=decision.craft)
    return await decide_fact(session, item_id, reviewer, approval, now=now)


async def _reject_fact(
    session: AsyncSession, item_id: uuid.UUID, reviewer: User, decision: QueueRejection, *, now: datetime
) -> QueueDecision:
    return await decide_fact(session, item_id, reviewer, FactDecision(REJECT, decision.reason), now=now)


async def _approve_component(
    session: AsyncSession, item_id: uuid.UUID, reviewer: User, decision: QueueApproval, *, now: datetime
) -> QueueDecision:
    return await approve_component(session, item_id, reviewer, note=decision.note, now=now)


async def _reject_component(
    session: AsyncSession, item_id: uuid.UUID, reviewer: User, decision: QueueRejection, *, now: datetime
) -> QueueDecision:
    return await reject_component(session, item_id, reviewer, reason=decision.reason, now=now)


async def _approve_layout(
    session: AsyncSession, item_id: uuid.UUID, reviewer: User, decision: QueueApproval, *, now: datetime
) -> QueueDecision:
    return await approve_layout(session, item_id, reviewer, note=decision.note, now=now)


async def _reject_layout(
    session: AsyncSession, item_id: uuid.UUID, reviewer: User, decision: QueueRejection, *, now: datetime
) -> QueueDecision:
    return await reject_layout(session, item_id, reviewer, reason=decision.reason, now=now)


async def _approve_structure(
    session: AsyncSession, item_id: uuid.UUID, reviewer: User, decision: QueueApproval, *, now: datetime
) -> QueueDecision:
    return await approve_structure_item(session, item_id, reviewer, note=decision.note, now=now)


async def _reject_structure(
    session: AsyncSession, item_id: uuid.UUID, reviewer: User, decision: QueueRejection, *, now: datetime
) -> QueueDecision:
    return await reject_structure_item(session, item_id, reviewer, reason=decision.reason, now=now)


async def _approve_testimony(
    session: AsyncSession, item_id: uuid.UUID, reviewer: User, decision: QueueApproval, *, now: datetime
) -> QueueDecision:
    version = _version(decision.version)
    with _testimony_refusals():
        row = await testimony_writes.approve(
            session,
            item_id,
            reviewer,
            version=version,
            english_checked=decision.english_checked,
            corroborating_ids=[],
            now=now,
        )
    return QueueDecision(
        kind=TESTIMONY, id=row.id, status=row.status, message=MESSAGES[(TESTIMONY, row.status)]
    )


async def _reject_testimony(
    session: AsyncSession, item_id: uuid.UUID, reviewer: User, decision: QueueRejection, *, now: datetime
) -> QueueDecision:
    version = _version(decision.version)
    with _testimony_refusals():
        row = await testimony_writes.reject(
            session,
            item_id,
            reviewer,
            version=version,
            reason=decision.testimony_reason or OTHER_REASON,
            note=decision.reason,
            now=now,
        )
    return QueueDecision(
        kind=TESTIMONY, id=row.id, status=row.status, message=MESSAGES[(TESTIMONY, row.status)]
    )


async def _approve_picture(
    session: AsyncSession, item_id: uuid.UUID, reviewer: User, decision: QueueApproval, *, now: datetime
) -> QueueDecision:
    await _refuse_own_picture(session, item_id, reviewer)
    with _picture_refusals():
        row = await images.approve(session, item_id, reviewer, decision.note, now=now)
    return await _picture_decided(session, reviewer, row)


async def _reject_picture(
    session: AsyncSession, item_id: uuid.UUID, reviewer: User, decision: QueueRejection, *, now: datetime
) -> QueueDecision:
    await _refuse_own_picture(session, item_id, reviewer)
    with _picture_refusals():
        row = await images.reject(session, item_id, reviewer, decision.reason, now=now)
    return await _picture_decided(session, reviewer, row)


async def _refuse_own_picture(session: AsyncSession, item_id: uuid.UUID, reviewer: User) -> None:
    contributor = await session.scalar(
        select(ImageContribution.contributorId).where(ImageContribution.id == item_id)
    )
    if contributor is not None and contributor == reviewer.id:
        raise OwnItem(OWN_ITEM)


async def _picture_decided(session: AsyncSession, reviewer: User, row: ImageContribution) -> QueueDecision:
    await audit.record(
        session,
        action=f"review.image_{row.status.lower()}",
        actor=reviewer,
        target_type="ImageContribution",
        target_id=row.id,
        detail={"from": "PENDING", "to": row.status},
    )
    return QueueDecision(kind=IMAGES, id=row.id, status=row.status, message=MESSAGES[(IMAGES, row.status)])


def _version(version: int | None) -> int:
    if version is None:
        raise InvalidInput(VERSION_NEEDED)
    return version


@contextmanager
def _testimony_refusals() -> Iterator[None]:
    try:
        yield
    except UnknownContribution as missing:
        raise UnknownItem(str(missing)) from missing
    except OwnContribution as own:
        raise OwnItem(OWN_ITEM) from own
    except StaleContribution as stale:
        raise DecisionConflict(STALE_TESTIMONY) from stale
    except MoveRefused as moved:
        raise DecisionConflict(MOVED_TESTIMONY) from moved


@contextmanager
def _picture_refusals() -> Iterator[None]:
    try:
        yield
    except images.UnknownImage as missing:
        raise UnknownItem(f"No contributed picture has the id {missing}.") from missing
    except images.ContributionRefused as refused:
        raise DecisionConflict(refused.detail) from refused


_APPROVERS: Mapping[str, Decide] = MappingProxyType(
    {
        FACTS: _approve_fact,
        TESTIMONY: _approve_testimony,
        IMAGES: _approve_picture,
        COMPONENTS: _approve_component,
        LAYOUTS: _approve_layout,
        STRUCTURE: _approve_structure,
    }
)
_REJECTERS: Mapping[str, Decide] = MappingProxyType(
    {
        FACTS: _reject_fact,
        TESTIMONY: _reject_testimony,
        IMAGES: _reject_picture,
        COMPONENTS: _reject_component,
        LAYOUTS: _reject_layout,
        STRUCTURE: _reject_structure,
    }
)
