from __future__ import annotations

import uuid
from collections.abc import Iterable, Mapping
from datetime import date, datetime, timedelta
from typing import Any, Literal

from pydantic import Field

from app.core.logging import redact_secrets
from app.models.oauth import CLIENT_NAME_CHARS, MCP_REASON_CHARS, MCP_TOOL_OUTCOMES

from .base import ContractModel
from .evidence import without_personal_data

__all__ = [
    "CALLS_KEPT_DAYS",
    "CONNECTIONS_SHOWN",
    "DEFAULT_PERIOD_DAYS",
    "FAILED_CALLS_SHOWN",
    "FAILED_OUTCOMES",
    "MCP_ACTIVITY_SCHEMA_VERSION",
    "PERIOD_DAYS",
    "WITHHELD",
    "ActivityPoint",
    "ClientActivity",
    "ConnectionActivity",
    "FailedCall",
    "McpActivity",
    "Outcomes",
    "ToolActivity",
    "activity_series",
    "calls_made",
    "failure_reason",
    "outcome_fields",
    "sent_texts",
    "series_unit",
    "tally",
]

MCP_ACTIVITY_SCHEMA_VERSION = 1
CALLS_KEPT_DAYS = 180
PERIOD_DAYS = (7, 30, 180)
DEFAULT_PERIOD_DAYS = 30
WEEKLY_AFTER_DAYS = 31
WEEK_DAYS = 7
FAILED_CALLS_SHOWN = 50
CONNECTIONS_SHOWN = 200
SENT_MIN_CHARS = 3
WITHHELD = "…"
FAILED_OUTCOMES = ("TOOL_ERROR", "PROTOCOL_ERROR")

SeriesUnit = Literal["day", "week"]
Counts = dict[str, int]


class Outcomes(ContractModel):
    ok: int = Field(ge=0)
    tool_errors: int = Field(ge=0)
    protocol_errors: int = Field(ge=0)


class ActivityPoint(Outcomes):
    start: date


class ToolActivity(Outcomes):
    tool: str = Field(min_length=1)


class ClientActivity(Outcomes):
    client_name: str = Field(min_length=1, max_length=CLIENT_NAME_CHARS)
    connections: int = Field(ge=0)
    last_used_at: datetime | None


class ConnectionActivity(Outcomes):
    id: uuid.UUID
    client_name: str = Field(min_length=1, max_length=CLIENT_NAME_CHARS)
    account_name: str
    account_email: str
    scopes: list[str]
    connected_at: datetime
    last_used_at: datetime | None
    ended: bool


class FailedCall(ContractModel):
    called_at: datetime
    client_name: str = Field(min_length=1, max_length=CLIENT_NAME_CHARS)
    connection_id: uuid.UUID
    tool: str = Field(min_length=1)
    outcome: Literal[*FAILED_OUTCOMES]
    reason: str | None = Field(max_length=MCP_REASON_CHARS)


class McpActivity(ContractModel):
    schema_version: Literal[1] = MCP_ACTIVITY_SCHEMA_VERSION
    days: int
    first_day: date
    last_day: date
    unit: SeriesUnit
    client: str | None
    connection: uuid.UUID | None
    kept_days: int = CALLS_KEPT_DAYS
    series: list[ActivityPoint]
    tools: list[ToolActivity]
    clients: list[ClientActivity]
    connections: list[ConnectionActivity]
    failures: list[FailedCall]


def failure_reason(text: str, *, sent: Iterable[str]) -> str:
    shown = _one_line(text)
    withheld = {_one_line(part) for part in sent}
    for value in sorted((part for part in withheld if len(part) >= SENT_MIN_CHARS), key=len, reverse=True):
        shown = shown.replace(value, WITHHELD)
    shown = redact_secrets(without_personal_data(shown)) or WITHHELD
    if len(shown) <= MCP_REASON_CHARS:
        return shown
    return shown[: MCP_REASON_CHARS - len(WITHHELD)].rstrip() + WITHHELD


def sent_texts(value: Any) -> tuple[str, ...]:
    if isinstance(value, str):
        return (value,)
    if isinstance(value, Mapping):
        return tuple(text for item in value.values() for text in sent_texts(item))
    if isinstance(value, list | tuple):
        return tuple(text for item in value for text in sent_texts(item))
    return ()


def tally[K](rows: Iterable[tuple[K, str, int]]) -> dict[K, Counts]:
    totals: dict[K, Counts] = {}
    for key, outcome, calls in rows:
        counts = totals.setdefault(key, dict.fromkeys(MCP_TOOL_OUTCOMES, 0))
        counts[outcome] += calls
    return totals


def outcome_fields(counts: Mapping[str, int]) -> dict[str, int]:
    return {
        "ok": counts.get("OK", 0),
        "tool_errors": counts.get("TOOL_ERROR", 0),
        "protocol_errors": counts.get("PROTOCOL_ERROR", 0),
    }


def calls_made(outcomes: Outcomes) -> int:
    return outcomes.ok + outcomes.tool_errors + outcomes.protocol_errors


def series_unit(days: int) -> SeriesUnit:
    return "week" if days > WEEKLY_AFTER_DAYS else "day"


def activity_series(
    daily: Mapping[date, Mapping[str, int]], *, first_day: date, last_day: date, unit: SeriesUnit
) -> list[ActivityPoint]:
    step = WEEK_DAYS if unit == "week" else 1
    starts = [
        first_day + timedelta(days=offset) for offset in range(0, (last_day - first_day).days + 1, step)
    ]
    points: dict[date, Counts] = {start: dict.fromkeys(MCP_TOOL_OUTCOMES, 0) for start in starts}
    for day, counts in daily.items():
        if not first_day <= day <= last_day:
            continue
        start = first_day + timedelta(days=(day - first_day).days // step * step)
        for outcome, calls in counts.items():
            points[start][outcome] += calls
    return [ActivityPoint(start=start, **outcome_fields(points[start])) for start in starts]


def _one_line(text: str) -> str:
    return " ".join(text.split())
