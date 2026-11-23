from __future__ import annotations

import uuid
from collections.abc import Sequence
from datetime import datetime

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import CandidateCheck, Claim
from app.research.candidate_gates import DUPLICATE_GATE, GATES, GateOutcome

__all__ = ["checks_of", "mark_sources_differ", "record_checks"]


async def record_checks(
    session: AsyncSession, claim_id: uuid.UUID, outcomes: Sequence[GateOutcome], *, checked_at: datetime
) -> None:
    session.add_all(
        [
            CandidateCheck(
                claimId=claim_id,
                gate=outcome.gate,
                passed=outcome.passed,
                reasons=list(outcome.reasons),
                relatedClaimIds=list(outcome.related),
                model=outcome.model,
                checkedAt=checked_at,
            )
            for outcome in outcomes
        ]
    )
    await session.flush()


async def checks_of(session: AsyncSession, claim_id: uuid.UUID) -> list[CandidateCheck]:
    rows = await session.scalars(select(CandidateCheck).where(CandidateCheck.claimId == claim_id))
    return sorted(rows, key=lambda row: GATES.index(row.gate))


async def mark_sources_differ(
    session: AsyncSession, claim_id: uuid.UUID, *, about: str | None = None
) -> list[uuid.UUID]:
    check = await session.scalar(
        select(CandidateCheck).where(
            CandidateCheck.claimId == claim_id,
            CandidateCheck.gate == DUPLICATE_GATE,
            CandidateCheck.passed.is_(True),
        )
    )
    differ = list(check.relatedClaimIds) if check is not None else []
    if not differ:
        return []
    named = {"differsOn": func.coalesce(Claim.differsOn, about.strip())} if about and about.strip() else {}
    await session.execute(
        update(Claim).where(Claim.id.in_([claim_id, *differ])).values(sourcesDiffer=True, **named)
    )
    return differ
