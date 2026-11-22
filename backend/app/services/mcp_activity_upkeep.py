from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any

from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import McpToolCall, McpToolCallDay
from app.research.mcp_activity import CALLS_KEPT_DAYS

from .mcp_activity_days import DayWindow, call_day, counted, day_start, india_day

__all__ = [
    "CALLS_PRUNED_PER_NIGHT",
    "DAYS_COUNTED_PER_NIGHT",
    "McpActivityReport",
    "days_to_count",
    "keep_mcp_activity",
    "mcp_activity_plan",
]

DAYS_COUNTED_PER_NIGHT = 31
CALLS_PRUNED_PER_NIGHT = 20_000
CALLS_KEPT = timedelta(days=CALLS_KEPT_DAYS)
COUNTED_COLUMNS = ("day", "clientName", "tool", "outcome", "calls")


@dataclass
class McpActivityReport:
    days_counted: int = 0
    calls_counted: int = 0
    calls_pruned: int = 0

    def as_dict(self) -> dict[str, Any]:
        return {
            "daysCounted": self.days_counted,
            "callsCounted": self.calls_counted,
            "callsPruned": self.calls_pruned,
        }


async def keep_mcp_activity(session: AsyncSession, *, now: datetime) -> McpActivityReport:
    days = await days_to_count(session, now=now)
    report = McpActivityReport(days_counted=len(days), calls_counted=await _count(session, days))
    report.calls_pruned = await _prune(session, now=now)
    await session.commit()
    return report


async def days_to_count(session: AsyncSession, *, now: datetime) -> list[date]:
    day = call_day()
    found = await session.scalars(
        select(day)
        .distinct()
        .where(McpToolCall.calledAt < day_start(india_day(now)), ~counted(day))
        .order_by(day)
        .limit(DAYS_COUNTED_PER_NIGHT)
    )
    return list(found)


async def mcp_activity_plan(session: AsyncSession, *, now: datetime) -> dict[str, int]:
    prunable = await session.scalar(select(func.count()).where(*_prunable(now)))
    return {
        "mcpDaysToCount": len(await days_to_count(session, now=now)),
        "mcpCallsToPrune": min(int(prunable or 0), CALLS_PRUNED_PER_NIGHT),
    }


async def _count(session: AsyncSession, days: list[date]) -> int:
    if not days:
        return 0
    day = call_day()
    grouped = (
        select(day, McpToolCall.clientName, McpToolCall.tool, McpToolCall.outcome, func.count())
        .where(*DayWindow(days[0], days[-1]).holds_call(), day.in_(days))
        .group_by(day, McpToolCall.clientName, McpToolCall.tool, McpToolCall.outcome)
    )
    written = await session.scalars(
        insert(McpToolCallDay)
        .from_select(COUNTED_COLUMNS, grouped)
        .on_conflict_do_nothing()
        .returning(McpToolCallDay.calls)
    )
    return sum(written)


async def _prune(session: AsyncSession, *, now: datetime) -> int:
    oldest = (
        select(McpToolCall.id)
        .where(*_prunable(now))
        .order_by(McpToolCall.calledAt, McpToolCall.id)
        .limit(CALLS_PRUNED_PER_NIGHT)
    )
    removed = await session.scalars(
        delete(McpToolCall).where(McpToolCall.id.in_(oldest.scalar_subquery())).returning(McpToolCall.id)
    )
    return len(removed.all())


def _prunable(now: datetime) -> list[Any]:
    return [McpToolCall.calledAt < now - CALLS_KEPT, counted(call_day())]
