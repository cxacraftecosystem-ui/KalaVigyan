from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta

from sqlalchemy import ColumnElement, Date, cast, exists, func, literal_column

from app.core.clock import INDIA_TZ, INDIA_TZ_NAME
from app.models import McpToolCall, McpToolCallDay

__all__ = ["DayWindow", "call_day", "counted", "day_start", "india_day"]

ZONE = literal_column(f"'{INDIA_TZ_NAME}'")


@dataclass(frozen=True)
class DayWindow:
    first: date
    last: date

    def holds_call(self) -> list[ColumnElement[bool]]:
        return [
            McpToolCall.calledAt >= day_start(self.first),
            McpToolCall.calledAt < day_start(self.last + timedelta(days=1)),
        ]


def call_day() -> ColumnElement[date]:
    return cast(func.timezone(ZONE, McpToolCall.calledAt), Date)


def counted(day: ColumnElement[date]) -> ColumnElement[bool]:
    return exists().where(McpToolCallDay.day == day)


def india_day(moment: datetime) -> date:
    return moment.astimezone(INDIA_TZ).date()


def day_start(day: date) -> datetime:
    return datetime.combine(day, time.min, tzinfo=INDIA_TZ)
