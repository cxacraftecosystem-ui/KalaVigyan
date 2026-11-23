from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import Date, Subquery, cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clock import INDIA_TZ_NAME
from app.models import UsageEvent
from app.providers.budget import usd

from .mcp_activity_days import day_start, india_day

__all__ = ["UNSETTLED_OUTCOME", "SpendPage", "SpendRow", "spend_by_day_and_task"]

UNSETTLED_OUTCOME = "RESERVED"


@dataclass(frozen=True)
class SpendRow:
    day: date
    task: str
    calls: int
    cost_usd: Decimal

    def as_dict(self) -> dict[str, Any]:
        return {
            "day": self.day.isoformat(),
            "task": self.task,
            "calls": self.calls,
            "costUsd": float(self.cost_usd),
        }


@dataclass(frozen=True)
class SpendPage:
    first_day: date
    last_day: date
    rows: list[SpendRow]
    total: int
    cost_usd: Decimal


async def spend_by_day_and_task(
    session: AsyncSession, *, days: int, now: datetime, offset: int, limit: int
) -> SpendPage:
    last = india_day(now)
    first = last - timedelta(days=days - 1)
    grouped = _by_day_and_task(_settled_calls(first, last))
    totals = select(func.count(), func.coalesce(func.sum(grouped.c.cost), 0)).select_from(grouped)
    total, cost = (await session.execute(totals)).one()
    found = await session.execute(
        select(grouped.c.day, grouped.c.task, grouped.c.calls, grouped.c.cost)
        .order_by(grouped.c.day.desc(), grouped.c.cost.desc(), grouped.c.task)
        .offset(offset)
        .limit(limit)
    )
    rows = [
        SpendRow(day, str(task), int(calls), usd(spent)) for day, task, calls, spent in found.tuples().all()
    ]
    return SpendPage(first_day=first, last_day=last, rows=rows, total=int(total), cost_usd=usd(cost))


def _settled_calls(first: date, last: date) -> Subquery:
    day = cast(func.timezone(INDIA_TZ_NAME, UsageEvent.createdAt), Date).label("day")
    return (
        select(day, UsageEvent.task.label("task"), UsageEvent.costUsd.label("cost"))
        .where(
            UsageEvent.createdAt >= day_start(first),
            UsageEvent.createdAt < day_start(last + timedelta(days=1)),
            UsageEvent.outcome != UNSETTLED_OUTCOME,
        )
        .subquery()
    )


def _by_day_and_task(calls: Subquery) -> Subquery:
    cost = func.coalesce(func.sum(calls.c.cost), 0).label("cost")
    return (
        select(calls.c.day, calls.c.task, func.count().label("calls"), cost)
        .group_by(calls.c.day, calls.c.task)
        .subquery()
    )
