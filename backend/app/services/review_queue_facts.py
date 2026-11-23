from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import exists, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clock import INDIA_TZ
from app.core.roles import ROLE_LABELS, role_value
from app.models import CandidateCheck, Claim, ReviewEvent, User
from app.research.retrieval import SHOWN_CLAIM_STATUSES
from app.research.review_queue import (
    APPROVE,
    FACTS,
    PAST_TENSE,
    RAISE,
    REJECT,
    RETRACT,
    QueueDecision,
    fact_move,
    fact_move_problem,
)
from app.research.review_switch import WAITING_STATUS
from app.research.write_back import WRITE_BACK_ORIGIN

from . import audit
from .candidate_writes import mark_sources_differ
from .claim_holds import is_held
from .review_queue_errors import DecisionConflict, OwnItem, UnknownItem
from .review_queue_refile import REFILED_FAMILY_NOTE, REFILED_NOTE, refile_fact, refile_family

__all__ = ["FactDecision", "decide_fact"]

USER_ACTOR = "USER"
MESSAGES = {
    APPROVE: "Approved: the fact is shown at its level.",
    REJECT: "Rejected: the fact is not shown, and the reason is kept with it.",
    RAISE: "Raised to reviewed: the fact is shown as reviewed.",
    RETRACT: "Retracted: the fact is no longer shown, and the reason is kept with it.",
}


@dataclass(frozen=True)
class FactDecision:
    action: str
    note: str | None
    craft: str | None = None
    family: str | None = None

    @property
    def refiled(self) -> bool:
        return self.craft is not None or self.family is not None

    @property
    def noted(self) -> str | None:
        if self.craft is not None:
            filed = REFILED_NOTE.format(craft=self.craft)
        elif self.family is not None:
            filed = REFILED_FAMILY_NOTE.format(family=self.family)
        else:
            return self.note
        return f"{self.note}; {filed}" if self.note else filed

    @property
    def filed_under(self) -> dict[str, str]:
        if self.craft is not None:
            return {"filedUnder": self.craft}
        return {"filedUnderFamily": self.family} if self.family is not None else {}


async def decide_fact(
    session: AsyncSession, claim_id: uuid.UUID, reviewer: User, decision: FactDecision, *, now: datetime
) -> QueueDecision:
    claim = await _gated_claim(session, claim_id, reviewer, own_allowed=decision.action == RETRACT)
    problem = fact_move_problem(decision.action, claim.status, claim.evidenceLevel, refiled=decision.refiled)
    if problem is not None:
        raise DecisionConflict(problem)
    await _refile(session, claim, decision)
    was_status, was_level = claim.status, claim.evidenceLevel
    move = fact_move(decision.action, refiled=decision.refiled)
    claim.status = move.to_status
    if move.to_level is not None:
        claim.evidenceLevel = move.to_level
        claim.levelReason = _reviewed_reason(reviewer, now)
    session.add(_event(claim, reviewer, decision.noted, was_status=was_status, was_level=was_level))
    await session.flush()
    differ = await _published(session, claim, was_status)
    await _record(session, reviewer, claim, decision, was_status)
    return QueueDecision(
        kind=FACTS,
        id=claim.id,
        status=claim.status,
        level=claim.evidenceLevel,
        sources_differ=claim.sourcesDiffer or bool(differ),
        message=MESSAGES[decision.action],
    )


async def _gated_claim(
    session: AsyncSession, claim_id: uuid.UUID, reviewer: User, *, own_allowed: bool
) -> Claim:
    claim = await session.get(Claim, claim_id, with_for_update=True)
    if claim is None or not await _decidable(session, claim):
        raise UnknownItem(f"No proposed or researched fact has the id {claim_id}.")
    if claim.createdById == reviewer.id and not own_allowed:
        raise OwnItem("A reviewer does not decide their own fact; they may only retract it.")
    return claim


async def _decidable(session: AsyncSession, claim: Claim) -> bool:
    if claim.origin == WRITE_BACK_ORIGIN:
        return True
    gated = await session.scalar(select(exists().where(CandidateCheck.claimId == claim.id)))
    return bool(gated) or await is_held(session, claim.id)


async def _refile(session: AsyncSession, claim: Claim, decision: FactDecision) -> None:
    if decision.craft is not None:
        await refile_fact(session, claim, decision.craft)
    elif decision.family is not None:
        await refile_family(session, claim, decision.family)


async def _published(session: AsyncSession, claim: Claim, was_status: str) -> list[uuid.UUID]:
    if was_status != WAITING_STATUS or claim.status not in SHOWN_CLAIM_STATUSES:
        return []
    return await mark_sources_differ(session, claim.id)


def _event(claim: Claim, reviewer: User, note: str | None, *, was_status: str, was_level: str) -> ReviewEvent:
    level_changed = claim.evidenceLevel != was_level
    return ReviewEvent(
        claimId=claim.id,
        actorId=reviewer.id,
        actorKind=USER_ACTOR,
        fromStatus=was_status,
        toStatus=claim.status,
        fromLevel=was_level if level_changed else None,
        toLevel=claim.evidenceLevel if level_changed else None,
        note=note,
    )


def _reviewed_reason(reviewer: User, now: datetime) -> str:
    role = role_value(reviewer)
    day = now.astimezone(INDIA_TZ).date().isoformat()
    return f"Reviewed against its quoted sources by a {ROLE_LABELS.get(role, role)} on {day}"


async def _record(
    session: AsyncSession, reviewer: User, claim: Claim, decision: FactDecision, was_status: str
) -> None:
    detail = {"from": was_status, "to": claim.status, "level": claim.evidenceLevel}
    await audit.record(
        session,
        action=f"review.fact_{PAST_TENSE[decision.action]}",
        actor=reviewer,
        target_type="Claim",
        target_id=claim.id,
        detail=detail | decision.filed_under,
    )
