from __future__ import annotations

import uuid
from collections.abc import Iterable, Mapping
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any

__all__ = [
    "Row",
    "day_of",
    "ids_of",
    "number_of",
    "published_ids",
    "stamp_of",
    "text_of",
]

Row = dict[str, Any]

STAMP_FORMAT = "%Y-%m-%dT%H:%M:%SZ"


def stamp_of(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.astimezone(UTC).strftime(STAMP_FORMAT)


def day_of(value: datetime | date | None) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.astimezone(UTC).date().isoformat()
    return value.isoformat()


def number_of(value: Decimal | float | int | None) -> int | float | None:
    if value is None:
        return None
    exact = Decimal(value) if not isinstance(value, Decimal) else value
    if exact == exact.to_integral_value():
        return int(exact)
    return float(exact)


def text_of(value: Any) -> str | None:
    if value is None:
        return None
    shown = str(value).strip()
    return shown or None


def ids_of(values: Iterable[Any]) -> list[str]:
    return [str(value) for value in values]


def published_ids(
    values: Iterable[uuid.UUID | str | None], published: Mapping[str, Any] | set[str]
) -> list[str]:
    kept: list[str] = []
    for value in values:
        if value is None:
            continue
        key = str(value)
        if key in published and key not in kept:
            kept.append(key)
    return kept
