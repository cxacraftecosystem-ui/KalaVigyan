from __future__ import annotations

import uuid
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clock import INDIA_TZ, INDIA_TZ_NAME
from app.models import QueuedProposal, UsageEvent, User
from app.research.contribution_queue import STREAM_REQUEST_PREFIX, stream_request_id
from app.research.cost_ledger import CostLedger, LedgerDay, LedgerRange, LedgerTotal

from .ai_providers import AiTask

__all__ = ["SETTLED_OUTCOMES", "cost_ledger", "stream_spend"]

SETTLED_OUTCOMES = ("OK", "RESERVED")
MONEY_DIGITS = 6


@dataclass
class _Tally:
    proposals: int = 0
    calls: int = 0
    judge_calls: int = 0
    embed_calls: int = 0
    failures: int = 0
    cost: Decimal = field(default_factory=Decimal)


async def stream_spend(session: AsyncSession, proposal_id: uuid.UUID) -> tuple[int, Decimal]:
    calls, cost = (
        await session.execute(
            select(func.count(UsageEvent.id), func.coalesce(func.sum(UsageEvent.costUsd), 0)).where(
                UsageEvent.requestId == stream_request_id(proposal_id)
            )
        )
    ).one()
    return int(calls), Decimal(cost)


async def cost_ledger(session: AsyncSession, span: LedgerRange) -> CostLedger:
    start, end = _bounds(span)
    tallies: dict[tuple[date, uuid.UUID | None], _Tally] = {}
    await _add_calls(session, tallies, start, end)
    await _add_proposals(session, tallies, start, end)
    users = await _users(session, {user_id for _, user_id in tallies if user_id is not None})
    days = [_day(day, user_id, tally, users) for (day, user_id), tally in sorted(tallies.items(), key=_order)]
    return CostLedger(
        day_from=span.day_from,
        day_to=span.day_to,
        time_zone=INDIA_TZ_NAME,
        days=days,
        accounts=_accounts(days),
        calls=sum(item.calls for item in days),
        cost_usd=_money(sum((tally.cost for tally in tallies.values()), Decimal(0))),
    )


def _bounds(span: LedgerRange) -> tuple[datetime, datetime]:
    start = datetime.combine(span.day_from, time.min, tzinfo=INDIA_TZ).astimezone(UTC)
    end = datetime.combine(span.day_to + timedelta(days=1), time.min, tzinfo=INDIA_TZ).astimezone(UTC)
    return start, end


def _local_day(column: Any) -> Any:
    return func.date(func.timezone(INDIA_TZ_NAME, column))


async def _add_calls(
    session: AsyncSession,
    tallies: dict[tuple[date, uuid.UUID | None], _Tally],
    start: datetime,
    end: datetime,
) -> None:
    day = _local_day(UsageEvent.createdAt).label("day")
    rows = await session.execute(
        select(
            day,
            UsageEvent.userId,
            func.count(UsageEvent.id),
            func.count(UsageEvent.id).filter(UsageEvent.task == AiTask.EVAL_JUDGE.value),
            func.count(UsageEvent.id).filter(UsageEvent.task == AiTask.EMBED.value),
            func.count(UsageEvent.id).filter(UsageEvent.outcome.not_in(SETTLED_OUTCOMES)),
            func.coalesce(func.sum(UsageEvent.costUsd), 0),
        )
        .where(
            UsageEvent.createdAt >= start,
            UsageEvent.createdAt < end,
            UsageEvent.requestId.like(f"{STREAM_REQUEST_PREFIX}%"),
        )
        .group_by(day, UsageEvent.userId)
    )
    for when, user_id, calls, judged, embedded, failed, cost in rows.all():
        tally = tallies.setdefault((when, user_id), _Tally())
        tally.calls, tally.judge_calls, tally.embed_calls = int(calls), int(judged), int(embedded)
        tally.failures, tally.cost = int(failed), Decimal(cost)


async def _add_proposals(
    session: AsyncSession,
    tallies: dict[tuple[date, uuid.UUID | None], _Tally],
    start: datetime,
    end: datetime,
) -> None:
    day = _local_day(QueuedProposal.finishedAt).label("day")
    rows = await session.execute(
        select(day, QueuedProposal.proposerId, func.count(QueuedProposal.id))
        .where(QueuedProposal.finishedAt >= start, QueuedProposal.finishedAt < end)
        .group_by(day, QueuedProposal.proposerId)
    )
    for when, user_id, count in rows.all():
        tallies.setdefault((when, user_id), _Tally()).proposals = int(count)


async def _users(session: AsyncSession, ids: set[uuid.UUID]) -> dict[uuid.UUID, User]:
    if not ids:
        return {}
    return {user.id: user for user in await session.scalars(select(User).where(User.id.in_(ids)))}


def _day(day: date, user_id: uuid.UUID | None, tally: _Tally, users: Mapping[uuid.UUID, User]) -> LedgerDay:
    user = users.get(user_id) if user_id is not None else None
    return LedgerDay(
        day=day,
        user_id=user_id,
        name=user.name if user is not None else None,
        role=str(user.role) if user is not None else None,
        proposals=tally.proposals,
        calls=tally.calls,
        judge_calls=tally.judge_calls,
        embed_calls=tally.embed_calls,
        failures=tally.failures,
        cost_usd=_money(tally.cost),
    )


def _accounts(days: list[LedgerDay]) -> list[LedgerTotal]:
    totals: dict[uuid.UUID | None, LedgerTotal] = {}
    for item in days:
        held = totals.get(item.user_id)
        totals[item.user_id] = LedgerTotal(
            user_id=item.user_id,
            name=item.name,
            proposals=item.proposals + (held.proposals if held else 0),
            calls=item.calls + (held.calls if held else 0),
            cost_usd=round(item.cost_usd + (held.cost_usd if held else 0.0), MONEY_DIGITS),
        )
    return sorted(totals.values(), key=lambda total: (-total.cost_usd, -total.calls, str(total.user_id)))


def _order(entry: tuple[tuple[date, uuid.UUID | None], _Tally]) -> tuple[date, float, str]:
    (day, user_id), tally = entry
    return day, -float(tally.cost), str(user_id)


def _money(value: Decimal) -> float:
    return round(float(value), MONEY_DIGITS)
