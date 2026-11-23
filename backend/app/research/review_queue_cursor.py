from __future__ import annotations

import re
import uuid
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from app.core.errors import InvalidInput

__all__ = ["CURSOR_MAX_CHARS", "QueueEntry", "QueueKey", "cursor_text", "newest_first", "parsed_cursor"]

CURSOR_MAX_CHARS = 60
EPOCH = datetime(1970, 1, 1, tzinfo=UTC)
MICROSECOND = timedelta(microseconds=1)
CURSOR_PATTERN = re.compile(r"^(\d{1,19})~([0-9a-f]{32})$")


@dataclass(frozen=True, order=True)
class QueueKey:
    created_at: datetime
    item_id: uuid.UUID


@dataclass(frozen=True)
class QueueEntry:
    key: QueueKey
    kind: str


def cursor_text(key: QueueKey) -> str:
    return f"{(key.created_at - EPOCH) // MICROSECOND}~{key.item_id.hex}"


def parsed_cursor(text: str) -> QueueKey:
    found = CURSOR_PATTERN.match(text)
    if found is None:
        raise InvalidInput("Unknown cursor.")
    return QueueKey(EPOCH + int(found.group(1)) * MICROSECOND, uuid.UUID(hex=found.group(2)))


def newest_first(groups: Iterable[Sequence[QueueEntry]], limit: int) -> tuple[list[QueueEntry], str | None]:
    merged = sorted((entry for group in groups for entry in group), key=lambda entry: entry.key, reverse=True)
    kept = merged[:limit]
    following = cursor_text(kept[-1].key) if len(merged) > limit else None
    return kept, following
