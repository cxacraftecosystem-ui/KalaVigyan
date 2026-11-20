from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import ColumnElement, and_, distinct, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Answer, CandidateCheck, Claim, ClaimSource, Concept, Craft
from app.research.write_back import FOUND_BY, WRITE_BACK_ORIGIN

__all__ = [
    "LATEST_SHOWN",
    "LIVE_TIERS",
    "REPORT_DAYS_DEFAULT",
    "ReportWindow",
    "report_window",
    "write_back_report",
]

REPORT_DAYS_DEFAULT = 14
LATEST_SHOWN = 10
CRAFTS_SHOWN = 10
LIVE_TIERS = ("T3", "T4")
TEXT_SHOWN_CHARS = 160
CONCEPT_SUBJECT = "CONCEPT"


@dataclass(frozen=True)
class ReportWindow:
    start: datetime
    end: datetime

    def holds(self, column: Any) -> ColumnElement[bool]:
        return and_(column >= self.start, column < self.end)

    def as_dict(self) -> dict[str, str]:
        return {"from": self.start.isoformat(), "to": self.end.isoformat()}


def report_window(now: datetime, days: int) -> ReportWindow:
    if days < 1:
        raise ValueError(f"a report covers at least one day, not {days}")
    return ReportWindow(start=now - timedelta(days=days), end=now)


async def write_back_report(session: AsyncSession, *, now: datetime, days: int) -> dict[str, Any]:
    window = report_window(now, days)
    return {
        "ok": True,
        "window": {**window.as_dict(), "days": days},
        "answers": await _answers(session, window),
        "claims": await _claims(session, window),
        "citations": await _citations(session, window),
        "gates": await _gates(session, window),
        "crafts": await _crafts(session, window),
        "latest": await _latest(session, window),
    }


async def _answers(session: AsyncSession, window: ReportWindow) -> dict[str, Any]:
    asked = window.holds(Answer.createdAt)
    live = and_(asked, Answer.tiersUsed.overlap(list(LIVE_TIERS)))
    modes = await session.execute(select(Answer.mode, func.count()).where(asked).group_by(Answer.mode))
    return {
        "total": await _count(session, Answer.id, asked),
        "withLiveResearch": await _count(session, Answer.id, live),
        "byMode": {str(mode): int(count) for mode, count in modes.all()},
    }


async def _claims(session: AsyncSession, window: ReportWindow) -> dict[str, Any]:
    written = _written(window)
    return {
        "written": await _count(session, Claim.id, written),
        "byStatus": await _grouped(session, Claim.status, written),
        "byLevel": await _grouped(session, Claim.evidenceLevel, written),
        "gated": await _count(session, distinct(CandidateCheck.claimId), _gated(window)),
    }


async def _citations(session: AsyncSession, window: ReportWindow) -> dict[str, Any]:
    added = and_(window.holds(ClaimSource.createdAt), ClaimSource.foundBy.in_(FOUND_BY))
    return {
        "added": await _count(session, ClaimSource.id, added),
        "byFoundBy": await _grouped(session, ClaimSource.foundBy, added),
        "byQuoteCheck": await _grouped(session, ClaimSource.quoteCheck, added),
        "answers": await _count(session, distinct(ClaimSource.answerId), added),
    }


async def _gates(session: AsyncSession, window: ReportWindow) -> dict[str, dict[str, int]]:
    rows = await session.execute(
        select(CandidateCheck.gate, CandidateCheck.passed, func.count())
        .where(_gated(window))
        .group_by(CandidateCheck.gate, CandidateCheck.passed)
    )
    found: dict[str, dict[str, int]] = {}
    for gate, passed, count in rows.all():
        found.setdefault(str(gate), {"passed": 0, "refused": 0})["passed" if passed else "refused"] = int(
            count
        )
    return found


async def _crafts(session: AsyncSession, window: ReportWindow) -> list[dict[str, Any]]:
    counted = func.count(Claim.id)
    rows = await session.execute(
        select(Craft.slug, counted)
        .join(Concept, Concept.craftId == Craft.id)
        .join(Claim, and_(Claim.subjectType == CONCEPT_SUBJECT, Claim.subjectId == Concept.id))
        .where(_written(window))
        .group_by(Craft.slug)
        .order_by(counted.desc(), Craft.slug)
        .limit(CRAFTS_SHOWN)
    )
    return [{"craft": slug, "written": int(count)} for slug, count in rows.all()]


async def _latest(session: AsyncSession, window: ReportWindow) -> list[dict[str, Any]]:
    rows = await session.execute(
        select(Claim.id, Claim.createdAt, Claim.status, Claim.evidenceLevel, Claim.text)
        .where(_written(window))
        .order_by(Claim.createdAt.desc(), Claim.id)
        .limit(LATEST_SHOWN)
    )
    return [_latest_row(row) for row in rows.all()]


def _latest_row(row: Sequence[Any]) -> dict[str, Any]:
    claim_id, created_at, status, level, text = row
    return {
        "claimId": str(claim_id),
        "createdAt": created_at.isoformat(),
        "status": str(status),
        "level": str(level),
        "text": str(text)[:TEXT_SHOWN_CHARS],
    }


def _written(window: ReportWindow) -> ColumnElement[bool]:
    return and_(Claim.origin == WRITE_BACK_ORIGIN, window.holds(Claim.createdAt))


def _gated(window: ReportWindow) -> ColumnElement[bool]:
    return and_(
        CandidateCheck.claimId == Claim.id,
        Claim.origin == WRITE_BACK_ORIGIN,
        window.holds(CandidateCheck.checkedAt),
    )


async def _count(session: AsyncSession, counted: Any, condition: ColumnElement[bool]) -> int:
    found = await session.scalar(select(func.count(counted)).where(condition))
    return int(found or 0)


async def _grouped(session: AsyncSession, column: Any, condition: ColumnElement[bool]) -> dict[str, int]:
    rows = await session.execute(select(column, func.count()).where(condition).group_by(column))
    return {str(value): int(count) for value, count in rows.all()}
