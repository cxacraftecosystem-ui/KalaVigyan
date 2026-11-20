from __future__ import annotations

import uuid
from collections.abc import Sequence
from typing import Literal, Self

from pydantic import Field, model_validator

from .base import ContractModel
from .chapter_keys import CHAPTER_KEYS
from .crafts import SLUG_MAX_CHARS
from .monograph_document import SUBJECT_KINDS
from .page_layout import LAYOUT_ENTRIES_MAX, PageLayoutEntry, check_entries
from .review_queue_delivery import PlacedDelivery

__all__ = [
    "CHANGE_KINDS",
    "LAYOUT_NOTE_MAX_CHARS",
    "LAYOUT_OUTCOMES",
    "LAYOUT_PROPOSAL_SCHEMA_VERSION",
    "STORED",
    "WRITTEN",
    "LayoutChange",
    "LayoutProposalDraft",
    "LayoutProposalResult",
    "LayoutReview",
    "LayoutSubject",
    "layout_changes",
]

LAYOUT_PROPOSAL_SCHEMA_VERSION = 1
LAYOUT_NOTE_MAX_CHARS = 500
STORED, WRITTEN = "STORED", "WRITTEN"
LAYOUT_OUTCOMES = (STORED, WRITTEN)
ADDED, CHANGED, REMOVED = "ADDED", "CHANGED", "REMOVED"
CHANGE_KINDS = (ADDED, CHANGED, REMOVED)
SLUG_PATTERN = r"^[A-Za-z0-9-]+$"

SubjectKind = Literal[*SUBJECT_KINDS]


class LayoutSubject(ContractModel):
    kind: SubjectKind
    slug: str = Field(min_length=1, max_length=SLUG_MAX_CHARS, pattern=SLUG_PATTERN)


class LayoutProposalDraft(ContractModel):
    schema_version: Literal[1] = LAYOUT_PROPOSAL_SCHEMA_VERSION
    subject: LayoutSubject
    base_version: int = Field(ge=0)
    entries: list[PageLayoutEntry] = Field(max_length=LAYOUT_ENTRIES_MAX)
    note: str | None = Field(default=None, min_length=1, max_length=LAYOUT_NOTE_MAX_CHARS)

    @model_validator(mode="after")
    def _entries_follow_the_rules(self) -> Self:
        check_entries(self.entries)
        return self


class LayoutProposalResult(ContractModel):
    schema_version: Literal[1] = LAYOUT_PROPOSAL_SCHEMA_VERSION
    outcome: Literal[*LAYOUT_OUTCOMES]
    proposal_id: uuid.UUID
    status: str
    subject: LayoutSubject
    base_version: int
    version: int | None = None
    page_url: str
    message: str


class LayoutChange(ContractModel):
    ref: str
    change: Literal[*CHANGE_KINDS]
    before: PageLayoutEntry | None
    after: PageLayoutEntry | None


class LayoutReview(ContractModel):
    subject: LayoutSubject
    subject_name: str
    page_url: str
    base_version: int
    current_version: int
    stale: bool
    note: str | None
    entry_count: int = Field(ge=0)
    changes: list[LayoutChange]
    placed: list[PlacedDelivery] = Field(default_factory=list)


def layout_changes(
    current: Sequence[PageLayoutEntry], proposed: Sequence[PageLayoutEntry]
) -> list[LayoutChange]:
    before = {entry.ref: entry for entry in current}
    after = {entry.ref: entry for entry in proposed}
    changes = [
        LayoutChange(
            ref=ref, change=ADDED if ref not in before else CHANGED, before=before.get(ref), after=entry
        )
        for ref, entry in after.items()
        if before.get(ref) != entry
    ]
    changes += [
        LayoutChange(ref=ref, change=REMOVED, before=entry, after=None)
        for ref, entry in before.items()
        if ref not in after
    ]
    return sorted(changes, key=_place)


def _place(change: LayoutChange) -> tuple[int, str, int, str]:
    entry = change.after if change.after is not None else change.before
    if entry is None:
        raise ValueError(f"a layout change of {change.ref} names neither place")
    chapter = CHAPTER_KEYS.index(entry.chapter) if entry.chapter in CHAPTER_KEYS else len(CHAPTER_KEYS)
    return chapter, entry.chapter, entry.order, change.ref
