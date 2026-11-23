from __future__ import annotations

import json
import uuid
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime
from types import MappingProxyType
from typing import Any

from app.research.mcp_activity import DEFAULT_PERIOD_DAYS

__all__ = [
    "COVERAGE",
    "CURSOR_PATTERN",
    "CUT_KEY",
    "EVALUATIONS",
    "FILING",
    "FILTERS",
    "HIDDEN_FACTS",
    "LIMIT_DEFAULT",
    "LIMIT_MAX",
    "MCP_ACTIVITY",
    "REPLY_BYTES_MAX",
    "REPORTS",
    "REPORT_FILTERS",
    "ROW_LIST_MAX",
    "SOURCES",
    "SPEND",
    "TEXT_MAX",
    "ReportAsk",
    "ReportPage",
    "bounded_row",
    "fitting",
    "page_rows",
    "paged",
]

COVERAGE, HIDDEN_FACTS, FILING, SOURCES, MCP_ACTIVITY, SPEND, EVALUATIONS = REPORTS = (
    "coverage",
    "hidden_facts",
    "filing",
    "sources",
    "mcp_activity",
    "spend",
    "evaluations",
)
CRAFT, SINCE, ANSWER_ID, DAYS = FILTERS = ("craft_slug", "since", "answer_id", "days")
REPORT_FILTERS: Mapping[str, frozenset[str]] = MappingProxyType(
    {
        COVERAGE: frozenset({CRAFT}),
        HIDDEN_FACTS: frozenset({CRAFT}),
        FILING: frozenset({SINCE, ANSWER_ID}),
        SOURCES: frozenset(),
        MCP_ACTIVITY: frozenset({DAYS}),
        SPEND: frozenset({DAYS}),
        EVALUATIONS: frozenset(),
    }
)
LIMIT_DEFAULT = 25
LIMIT_MAX = 50
CURSOR_PATTERN = r"^[0-9]{1,6}$"
ROW_LIST_MAX = 20
TEXT_MAX = 300
REPLY_BYTES_MAX = 48 * 1024
CUT_KEY = "cut"
CUT_MARK = "…"
LISTS_CUT = (
    " Lists longer than {most} are cut to their first {most}; an item's cut gives each one's full length."
)
PAGE_CUT = " This page stops at {shown} rows to keep the reply small; next_cursor goes on from there."


@dataclass(frozen=True)
class ReportAsk:
    now: datetime
    craft: str | None = None
    since: date | None = None
    answer_id: uuid.UUID | None = None
    days: int = DEFAULT_PERIOD_DAYS
    offset: int = 0
    limit: int = LIMIT_DEFAULT


@dataclass(frozen=True)
class ReportPage:
    items: list[dict[str, Any]]
    total: int
    next_cursor: str | None
    message: str


def page_rows(rows: Sequence[Mapping[str, Any]], ask: ReportAsk, message: str) -> ReportPage:
    window = rows[ask.offset : ask.offset + ask.limit]
    return paged(window, ask, total=len(rows), message=message)


def paged(window: Sequence[Mapping[str, Any]], ask: ReportAsk, *, total: int, message: str) -> ReportPage:
    bounded = [bounded_row(row) for row in window[: ask.limit]]
    shown = bounded[: fitting(bounded)]
    following = ask.offset + len(shown)
    said = message
    if any(CUT_KEY in item for item in shown):
        said += LISTS_CUT.format(most=ROW_LIST_MAX)
    if len(shown) < len(bounded):
        said += PAGE_CUT.format(shown=len(shown))
    return ReportPage(shown, total, str(following) if following < total else None, said)


def bounded_row(row: Mapping[str, Any]) -> dict[str, Any]:
    cut = {
        key: len(value) for key, value in row.items() if isinstance(value, list) and len(value) > ROW_LIST_MAX
    }
    kept = {key: _bounded(value) for key, value in row.items()}
    if cut:
        kept[CUT_KEY] = cut
    return kept


def fitting(items: Sequence[Mapping[str, Any]], bytes_max: int = REPLY_BYTES_MAX) -> int:
    used = 0
    for count, item in enumerate(items):
        used += len(json.dumps(item, ensure_ascii=False, separators=(",", ":")).encode("utf-8")) + 1
        if used > bytes_max:
            return max(count, 1)
    return len(items)


def _bounded(value: Any) -> Any:
    if isinstance(value, str) and len(value) > TEXT_MAX:
        return value[: TEXT_MAX - len(CUT_MARK)] + CUT_MARK
    if isinstance(value, list):
        return [_bounded(item) for item in value[:ROW_LIST_MAX]]
    if isinstance(value, Mapping):
        return {key: _bounded(item) for key, item in value.items()}
    return value
