from __future__ import annotations

import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any

from sqlalchemy import ColumnElement, Executable, Select, func, select, union_all
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import McpToolCall, McpToolCallDay
from app.research.mcp_activity import (
    McpActivity,
    ToolActivity,
    activity_series,
    calls_made,
    outcome_fields,
    series_unit,
    tally,
)

from .mcp_activity_connections import client_activity, connection_activity, failed_calls
from .mcp_activity_days import DayWindow, call_day, counted, india_day

__all__ = ["ActivityAsk", "read_activity"]

CallRow = tuple[date, str, str, str, int]


@dataclass(frozen=True)
class ActivityAsk:
    days: int
    client: str | None = None
    connection: uuid.UUID | None = None


async def read_activity(session: AsyncSession, ask: ActivityAsk, *, now: datetime) -> McpActivity:
    window = DayWindow(india_day(now) - timedelta(days=ask.days - 1), india_day(now))
    every_client = await _rows(session, union_all(_counted_rows(window), _uncounted_rows(window)))
    shown = await _shown_rows(session, window, ask, every_client)
    unit = series_unit(ask.days)
    daily = tally((day, outcome, calls) for day, _client, _tool, outcome, calls in shown)
    by_client = tally((client, outcome, calls) for _day, client, _tool, outcome, calls in every_client)
    return McpActivity(
        days=ask.days,
        first_day=window.first,
        last_day=window.last,
        unit=unit,
        client=ask.client,
        connection=ask.connection,
        series=activity_series(daily, first_day=window.first, last_day=window.last, unit=unit),
        tools=_tools(shown),
        clients=await client_activity(session, by_client, now=now),
        connections=await connection_activity(session, window, now=now),
        failures=await failed_calls(session, window, client=ask.client, connection=ask.connection),
    )


async def _shown_rows(
    session: AsyncSession, window: DayWindow, ask: ActivityAsk, every_client: list[CallRow]
) -> list[CallRow]:
    if ask.connection is not None:
        return await _rows(session, _call_rows(window, McpToolCall.grantId == ask.connection))
    if ask.client is not None:
        return [row for row in every_client if row[1] == ask.client]
    return every_client


def _counted_rows(window: DayWindow) -> Select[Any]:
    return select(
        McpToolCallDay.day,
        McpToolCallDay.clientName,
        McpToolCallDay.tool,
        McpToolCallDay.outcome,
        McpToolCallDay.calls,
    ).where(McpToolCallDay.day >= window.first, McpToolCallDay.day <= window.last)


def _uncounted_rows(window: DayWindow) -> Select[Any]:
    return _call_rows(window, ~counted(call_day()))


def _call_rows(window: DayWindow, *scope: ColumnElement[bool]) -> Select[Any]:
    day = call_day()
    return (
        select(day, McpToolCall.clientName, McpToolCall.tool, McpToolCall.outcome, func.count())
        .where(*window.holds_call(), *scope)
        .group_by(day, McpToolCall.clientName, McpToolCall.tool, McpToolCall.outcome)
    )


async def _rows(session: AsyncSession, query: Executable) -> list[CallRow]:
    found = await session.execute(query)
    return [(day, client, tool, outcome, int(calls)) for day, client, tool, outcome, calls in found.all()]


def _tools(rows: Sequence[CallRow]) -> list[ToolActivity]:
    counts = tally((tool, outcome, calls) for _day, _client, tool, outcome, calls in rows)
    tools = [ToolActivity(tool=tool, **outcome_fields(found)) for tool, found in counts.items()]
    return sorted(tools, key=lambda tool: (-calls_made(tool), tool.tool))
