from __future__ import annotations

import uuid
from typing import Literal

from pydantic import Field

from app.models.admin_work import STAGED_ACTION_VALUES, STAGED_KIND_VALUES
from app.models.enums import SOURCE_KINDS
from app.research.crafts import SLUG_MAX_CHARS
from app.research.review_queue import CURSOR_MAX_CHARS, REASON_MAX_CHARS
from app.research.review_switch import PROPOSAL_ORIGINS
from app.research.staged_reviews import (
    AUTHORS_MAX,
    DECISIONS_PER_CALL_MAX,
    MCP_QUEUE_KINDS,
    STAGED_REASON_MIN_CHARS,
)

from .mcp_tool_base import Arguments

__all__ = ["OpenItem", "ReviewQueueArguments", "SourceFixArguments", "StageArguments", "StagedChoice"]

LIST_MAX = 25

QueueKindName = Literal[*MCP_QUEUE_KINDS]


class OpenItem(Arguments):
    kind: QueueKindName
    id: uuid.UUID


class ReviewQueueArguments(Arguments):
    kinds: list[QueueKindName] | None = Field(default=None, max_length=len(MCP_QUEUE_KINDS))
    craft_slug: str | None = Field(default=None, min_length=1, max_length=SLUG_MAX_CHARS)
    origin: Literal[*PROPOSAL_ORIGINS] | None = None
    cursor: str | None = Field(default=None, min_length=1, max_length=CURSOR_MAX_CHARS)
    limit: int = Field(default=10, ge=1, le=LIST_MAX)
    open: OpenItem | None = Field(default=None, description="One item to read whole, as its card shows it")


class SourceFixArguments(Arguments):
    title: str | None = Field(default=None, min_length=1, max_length=500)
    authors: list[str] | None = Field(default=None, max_length=AUTHORS_MAX)
    year: int | None = None
    container_title: str | None = Field(default=None, min_length=1, max_length=300, description="The journal")
    kind: Literal[*SOURCE_KINDS] | None = None


class StagedChoice(Arguments):
    kind: Literal[*STAGED_KIND_VALUES]
    id: uuid.UUID = Field(description="The queue item, or the source (SOURCES) or fact (SOURCES_DIFFER)")
    action: Literal[*STAGED_ACTION_VALUES]
    reason: str = Field(min_length=STAGED_REASON_MIN_CHARS, max_length=REASON_MAX_CHARS)
    craft_slug: str | None = Field(default=None, min_length=1, max_length=SLUG_MAX_CHARS)
    family_slug: str | None = Field(default=None, min_length=1, max_length=SLUG_MAX_CHARS)
    source: SourceFixArguments | None = None


class StageArguments(Arguments):
    decisions: list[StagedChoice] = Field(min_length=1, max_length=DECISIONS_PER_CALL_MAX)
