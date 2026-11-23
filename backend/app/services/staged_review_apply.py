from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.core.roles import Capability, can
from app.models import User
from app.research.page_revalidation import PageOwners
from app.research.review_queue import (
    APPROVE,
    RAISE,
    REJECT,
    FactLevelRaise,
    FactRetraction,
    QueueApproval,
    QueueDecision,
    QueueRejection,
)
from app.research.staged_reviews import SOURCES, SOURCES_DIFFER, StagedDecision

from . import review_queue_decisions as decisions
from .page_revalidation import merged_owners
from .review_queue_errors import NotYourQueue
from .review_queue_refile import filed_owners
from .review_queue_refresh import decision_owners
from .source_corrections import clear_sources_differ, correct_source

__all__ = ["Applied", "apply_decision", "dry_run", "refusal_of"]

CORRECTED = "Corrected: the source's record now says this, and every page citing it follows."
CLEARED = "Cleared: the fact is no longer marked as one whose sources differ."
NOT_AN_ADMIN = "Correcting sources and clearing a differ mark are for Admins and Master Admins."


@dataclass(frozen=True)
class Applied:
    message: str
    owners: PageOwners
    decided: QueueDecision | None = None


async def apply_decision(
    session: AsyncSession, decision: StagedDecision, reviewer: User, *, now: datetime
) -> Applied:
    if decision.kind in (SOURCES, SOURCES_DIFFER):
        return await _corrected(session, decision, reviewer)
    ref = decisions.ItemRef(decision.kind, decision.id)
    moved_from = await filed_owners(session, decision.kind, decision.id, decision.craft or decision.family)
    decided = await _decided(session, ref, decision, reviewer, now=now)
    owners = merged_owners(moved_from, await decision_owners(session, decided))
    return Applied(decided.message, owners, decided)


async def dry_run(
    session: AsyncSession, decision: StagedDecision, reviewer: User, *, now: datetime
) -> str | None:
    savepoint = await session.begin_nested()
    try:
        await apply_decision(session, decision, reviewer, now=now)
    except (AppError, ValidationError) as refused:
        await savepoint.rollback()
        return refusal_of(refused)
    await savepoint.rollback()
    return None


def refusal_of(refused: AppError | ValidationError) -> str:
    if isinstance(refused, ValidationError):
        return "; ".join(str(problem["msg"]) for problem in refused.errors())
    return str(refused) or type(refused).__name__


async def _decided(
    session: AsyncSession, ref: decisions.ItemRef, decision: StagedDecision, reviewer: User, *, now: datetime
) -> QueueDecision:
    if decision.action == APPROVE:
        approval = QueueApproval(note=decision.reason, craft=decision.craft, family=decision.family)
        return await decisions.approve_item(session, ref, reviewer, approval, now=now)
    if decision.action == REJECT:
        rejection = QueueRejection(reason=decision.reason)
        return await decisions.reject_item(session, ref, reviewer, rejection, now=now)
    if decision.action == RAISE:
        return await decisions.raise_fact(
            session, ref.item_id, reviewer, FactLevelRaise(note=decision.reason), now=now
        )
    retraction = FactRetraction(reason=decision.reason)
    return await decisions.retract_fact(session, ref.item_id, reviewer, retraction, now=now)


async def _corrected(session: AsyncSession, decision: StagedDecision, reviewer: User) -> Applied:
    if not can(reviewer, Capability.REVIEW_CONTRIBUTIONS):
        raise NotYourQueue(NOT_AN_ADMIN)
    if decision.kind == SOURCES and decision.source is not None:
        owners = await correct_source(session, decision.id, decision.source, actor=reviewer)
        return Applied(CORRECTED, owners)
    owners = await clear_sources_differ(session, decision.id, actor=reviewer, reason=decision.reason)
    return Applied(CLEARED, owners)
