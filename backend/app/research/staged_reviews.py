from __future__ import annotations

import uuid
from collections.abc import Mapping
from datetime import datetime, timedelta
from types import MappingProxyType
from typing import Annotated, Literal, Self

from pydantic import Field, model_validator

from app.models.admin_work import BATCH_STATUSES, ITEM_STATES, STAGED_ACTION_VALUES, STAGED_KIND_VALUES
from app.models.enums import SOURCE_KINDS
from app.models.knowledge import CONTAINER_TITLE_CHARS

from .base import ContractModel
from .crafts import SLUG_MAX_CHARS
from .review_queue import APPROVE, FACTS, KIND_ACTIONS, ONE_HOME, REASON_MAX_CHARS

__all__ = [
    "APPLIED",
    "AUTHORS_MAX",
    "BATCHES_SHOWN",
    "BATCH_DAYS",
    "CLEAR",
    "CONFIRMED",
    "CORRECT",
    "DECISIONS_PER_CALL_MAX",
    "DISCARDED",
    "EXPIRED",
    "MCP_QUEUE_KINDS",
    "OPEN",
    "REFUSED",
    "SKIPPED",
    "SOURCES",
    "SOURCES_DIFFER",
    "STAGED",
    "STAGED_ITEMS_PER_DAY_MAX",
    "STAGED_KIND_ACTIONS",
    "STAGED_REASON_MIN_CHARS",
    "STAGED_SCHEMA_VERSION",
    "ConfirmedItem",
    "SourceFix",
    "StagedBatchList",
    "StagedBatchView",
    "StagedConfirmation",
    "StagedDecision",
    "StagedItemView",
    "batch_expiry",
    "batch_status",
    "day_allowance_problem",
]

STAGED_SCHEMA_VERSION = 1
DECISIONS_PER_CALL_MAX = 20
STAGED_ITEMS_PER_DAY_MAX = 100
STAGED_REASON_MIN_CHARS = 12
BATCH_DAYS = 3
BATCHES_SHOWN = 20
AUTHORS_MAX = 30
AUTHOR_MAX_CHARS = 200
TITLE_MAX_CHARS = 500
YEAR_MIN, YEAR_MAX = 1000, 2100
OPEN, CONFIRMED, DISCARDED = BATCH_STATUSES
EXPIRED = "EXPIRED"
STAGED, APPLIED, REFUSED, SKIPPED = ITEM_STATES
MCP_QUEUE_KINDS: tuple[str, ...] = STAGED_KIND_VALUES[:-2]
SOURCES, SOURCES_DIFFER = STAGED_KIND_VALUES[-2:]
CORRECT, CLEAR = STAGED_ACTION_VALUES[-2:]
STAGED_KIND_ACTIONS: Mapping[str, tuple[str, ...]] = MappingProxyType(
    {
        **{kind: KIND_ACTIONS[kind] for kind in MCP_QUEUE_KINDS},
        SOURCES: (CORRECT,),
        SOURCES_DIFFER: (CLEAR,),
    }
)
NOT_FOR_KIND = "A {kind} item is {actions}, not {action}."
REFILE_ONLY = "Only an approved fact is filed under a craft or a family's science."
SOURCE_ONLY = "Only a source correction carries a source's corrected fields."
SOURCE_NEEDED = "A source correction names at least one corrected field."
OVER_DAY = (
    "Staging {asked} more would pass the {most} items an Admin may stage in a day; {left} are left until "
    "midnight India time."
)

StagedKind = Literal[*STAGED_KIND_VALUES]
StagedAction = Literal[*STAGED_ACTION_VALUES]
StagedReason = Annotated[str, Field(min_length=STAGED_REASON_MIN_CHARS, max_length=REASON_MAX_CHARS)]
Slug = Annotated[str, Field(min_length=1, max_length=SLUG_MAX_CHARS)]
Author = Annotated[str, Field(min_length=1, max_length=AUTHOR_MAX_CHARS)]
BatchStatus = Literal[*BATCH_STATUSES, "EXPIRED"]
ItemState = Literal[*ITEM_STATES]


class SourceFix(ContractModel):
    title: str | None = Field(default=None, min_length=1, max_length=TITLE_MAX_CHARS)
    authors: list[Author] | None = Field(default=None, max_length=AUTHORS_MAX)
    year: int | None = Field(default=None, ge=YEAR_MIN, le=YEAR_MAX)
    container_title: str | None = Field(default=None, min_length=1, max_length=CONTAINER_TITLE_CHARS)
    kind: Literal[*SOURCE_KINDS] | None = None

    @model_validator(mode="after")
    def _names_a_field(self) -> Self:
        if not self.model_dump(exclude_none=True):
            raise ValueError(SOURCE_NEEDED)
        return self


class _Choice(ContractModel):
    action: StagedAction
    reason: StagedReason
    craft: Slug | None = None
    family: Slug | None = None
    source: SourceFix | None = None


class StagedDecision(_Choice):
    kind: StagedKind
    id: uuid.UUID

    @model_validator(mode="after")
    def _fits_its_kind(self) -> Self:
        allowed = STAGED_KIND_ACTIONS[self.kind]
        if self.action not in allowed:
            raise ValueError(
                NOT_FOR_KIND.format(kind=self.kind, actions=" or ".join(allowed), action=self.action)
            )
        if self.craft is not None and self.family is not None:
            raise ValueError(ONE_HOME)
        if (self.craft or self.family) is not None and (self.kind, self.action) != (FACTS, APPROVE):
            raise ValueError(REFILE_ONLY)
        if (self.source is not None) != (self.kind == SOURCES):
            raise ValueError(SOURCE_NEEDED if self.kind == SOURCES else SOURCE_ONLY)
        return self

    def changed_to(self, choice: ConfirmedItem) -> StagedDecision:
        fields = choice.model_dump(exclude={"id"})
        return StagedDecision.model_validate({**fields, "kind": self.kind, "id": self.id})


class ConfirmedItem(_Choice):
    id: uuid.UUID


class StagedConfirmation(ContractModel):
    items: list[ConfirmedItem] = Field(min_length=1, max_length=DECISIONS_PER_CALL_MAX)


class StagedItemView(ContractModel):
    id: uuid.UUID
    position: int = Field(ge=0)
    label: str
    decision: StagedDecision
    state: ItemState
    applied: StagedDecision | None = None
    outcome: str | None = None


class StagedBatchView(ContractModel):
    id: uuid.UUID
    status: BatchStatus
    client_name: str
    proposed_by: str | None
    created_at: datetime
    expires_at: datetime
    decided_by: str | None = None
    decided_at: datetime | None = None
    refresh: str | None = None
    items: list[StagedItemView]


class StagedBatchList(ContractModel):
    schema_version: Literal[1] = STAGED_SCHEMA_VERSION
    batches: list[StagedBatchView] = Field(max_length=BATCHES_SHOWN)


def batch_status(stored: str, expires_at: datetime, *, now: datetime) -> str:
    return EXPIRED if stored == OPEN and expires_at <= now else stored


def batch_expiry(created_at: datetime) -> datetime:
    return created_at + timedelta(days=BATCH_DAYS)


def day_allowance_problem(today: int, asked: int, *, most: int = STAGED_ITEMS_PER_DAY_MAX) -> str | None:
    if asked == 0 or today + asked <= most:
        return None
    return OVER_DAY.format(asked=asked, most=most, left=max(most - today, 0))
