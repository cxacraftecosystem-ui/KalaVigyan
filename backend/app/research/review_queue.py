from __future__ import annotations

import re
import uuid
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from types import MappingProxyType
from typing import Annotated, Any, Literal

from pydantic import Field

from app.core.errors import InvalidInput
from app.core.roles import Capability, can

from .base import ContractModel
from .crafts import SLUG_MAX_CHARS, CraftRef
from .image_contributions import REVIEW_NOTE_MAX_CHARS as PICTURE_NOTE_MAX_CHARS, ImageContributionView
from .layout_proposals import LayoutReview
from .open_work import REVIEW_QUEUES
from .review_queue_components import ComponentReview
from .review_queue_parts import FactSource, GateCheck, RelatedFact, SourceQuote
from .review_queue_structure import StructureReview
from .review_switch import (
    AGENT,
    APPROVED_STATUS,
    CONTRIBUTION,
    LIVE_UNREVIEWED_STATUS,
    PROPOSAL_ORIGINS,
    REFUSED_STATUS,
    RESEARCH,
    WAITING_STATUS,
)
from .testimony import REVIEW_NOTE_MAX as TESTIMONY_NOTE_MAX_CHARS, TESTIMONY_REJECT_REASONS
from .vocabulary import LABEL_LEVELS, Discipline, EvidenceLevel
from .write_back import WRITE_BACK_ORIGIN

__all__ = [
    "ACTIONS",
    "APPROVE",
    "COMPONENTS",
    "CURSOR_MAX_CHARS",
    "FACTS",
    "FACT_MOVES",
    "IMAGES",
    "KIND_ACTIONS",
    "KIND_ORIGINS",
    "LAYOUTS",
    "PAGE_DEFAULT",
    "PAGE_MAX",
    "PAST_TENSE",
    "PENDING_FACT_STATUSES",
    "QUEUE_KINDS",
    "RAISE",
    "REASON_MAX_CHARS",
    "REASON_MIN_CHARS",
    "REJECT",
    "RETRACT",
    "REVIEWED_LEVEL",
    "REVIEW_ORIGINS",
    "REVIEW_QUEUE_SCHEMA_VERSION",
    "STRUCTURE",
    "TESTIMONY",
    "TESTIMONY_ORIGIN",
    "ComponentItem",
    "FactConcept",
    "FactItem",
    "FactLevelRaise",
    "FactMove",
    "FactRetraction",
    "FactReview",
    "FactSource",
    "GateCheck",
    "LayoutItem",
    "PictureItem",
    "Proposer",
    "QueueApproval",
    "QueueDecision",
    "QueueEntry",
    "QueueItem",
    "QueueKey",
    "QueueKind",
    "QueueRejection",
    "RelatedFact",
    "ReviewFilters",
    "ReviewOrigin",
    "ReviewQueuePage",
    "SourceQuote",
    "StructureQueueItem",
    "TestimonyItem",
    "cursor_text",
    "decision_capability",
    "fact_move_problem",
    "fact_origin",
    "newest_first",
    "parsed_cursor",
    "reviewed_kinds",
    "sees_proposer",
    "selected_kinds",
]

REVIEW_QUEUE_SCHEMA_VERSION = 1
QUEUE_KINDS: tuple[str, ...] = tuple(REVIEW_QUEUES)
FACTS, TESTIMONY, IMAGES, COMPONENTS, LAYOUTS, STRUCTURE = QUEUE_KINDS
TESTIMONY_ORIGIN = "TESTIMONY"
REVIEW_ORIGINS: tuple[str, ...] = (*PROPOSAL_ORIGINS, TESTIMONY_ORIGIN)
KIND_ORIGINS: Mapping[str, tuple[str, ...]] = MappingProxyType(
    {
        FACTS: PROPOSAL_ORIGINS,
        TESTIMONY: (TESTIMONY_ORIGIN,),
        IMAGES: (CONTRIBUTION,),
        COMPONENTS: (AGENT,),
        LAYOUTS: (CONTRIBUTION, AGENT),
        STRUCTURE: (CONTRIBUTION, AGENT),
    }
)
APPROVE, REJECT, RAISE, RETRACT = "approve", "reject", "raise", "retract"
ACTIONS = (APPROVE, REJECT, RAISE, RETRACT)
KIND_ACTIONS: Mapping[str, tuple[str, ...]] = MappingProxyType(
    {kind: ACTIONS if kind == FACTS else (APPROVE, REJECT) for kind in QUEUE_KINDS}
)
PAST_TENSE = MappingProxyType(
    {APPROVE: "approved", REJECT: "rejected", RAISE: "raised", RETRACT: "retracted"}
)
PENDING_FACT_STATUSES = (WAITING_STATUS, LIVE_UNREVIEWED_STATUS)
RETRACTED_STATUS = "RETRACTED"
RAISABLE_LEVEL = LABEL_LEVELS["QUOTED"]
REVIEWED_LEVEL: EvidenceLevel = "REVIEWED"
PAGE_DEFAULT = 25
PAGE_MAX = 50
REASON_MIN_CHARS = 3
REASON_MAX_CHARS = min(PICTURE_NOTE_MAX_CHARS, TESTIMONY_NOTE_MAX_CHARS)
CURSOR_MAX_CHARS = 60
EPOCH = datetime(1970, 1, 1, tzinfo=UTC)
MICROSECOND = timedelta(microseconds=1)
CURSOR_PATTERN = re.compile(r"^(\d{1,19})~([0-9a-f]{32})$")

QueueKind = Literal[*QUEUE_KINDS]
ReviewOrigin = Literal[*REVIEW_ORIGINS]
TestimonyReason = Literal[*TESTIMONY_REJECT_REASONS]
Reason = Annotated[str, Field(min_length=REASON_MIN_CHARS, max_length=REASON_MAX_CHARS)]
Note = Annotated[str, Field(min_length=1, max_length=REASON_MAX_CHARS)]


@dataclass(frozen=True, order=True)
class QueueKey:
    created_at: datetime
    item_id: uuid.UUID


@dataclass(frozen=True)
class QueueEntry:
    key: QueueKey
    kind: str


@dataclass(frozen=True)
class FactMove:
    from_statuses: tuple[str, ...]
    to_status: str
    to_level: str | None = None


FACT_MOVES: Mapping[str, FactMove] = MappingProxyType(
    {
        APPROVE: FactMove(PENDING_FACT_STATUSES, APPROVED_STATUS),
        REJECT: FactMove(PENDING_FACT_STATUSES, REFUSED_STATUS),
        RAISE: FactMove((*PENDING_FACT_STATUSES, APPROVED_STATUS), APPROVED_STATUS, REVIEWED_LEVEL),
        RETRACT: FactMove((LIVE_UNREVIEWED_STATUS, APPROVED_STATUS), RETRACTED_STATUS),
    }
)


def reviewed_kinds(user: Any) -> tuple[str, ...]:
    return tuple(kind for kind in QUEUE_KINDS if can(user, REVIEW_QUEUES[kind]))


def sees_proposer(user: Any) -> bool:
    return can(user, Capability.REVIEW_CONTRIBUTIONS)


def selected_kinds(viewer_kinds: Iterable[str], *, kind: str | None, origin: str | None) -> tuple[str, ...]:
    return tuple(
        each
        for each in viewer_kinds
        if (kind is None or each == kind) and (origin is None or origin in KIND_ORIGINS[each])
    )


def decision_capability(kind: str, action: str) -> Capability:
    if action not in KIND_ACTIONS[kind]:
        raise InvalidInput(f"A {kind.lower()} item cannot be {PAST_TENSE[action]}; only a fact can.")
    if action == RETRACT:
        return Capability.RETRACT_CLAIM
    return REVIEW_QUEUES[kind]


def fact_move_problem(action: str, status: str, level: str) -> str | None:
    move = FACT_MOVES[action]
    if status not in move.from_statuses:
        return f"A fact that is {status.lower()} cannot be {PAST_TENSE[action]}."
    if move.to_level is not None and level != RAISABLE_LEVEL:
        return f"Only a quoted fact at {RAISABLE_LEVEL.lower()} can be raised; this one is {level.lower()}."
    return None


def fact_origin(claim_origin: str, found_by: Iterable[str | None]) -> str:
    if claim_origin == WRITE_BACK_ORIGIN:
        return RESEARCH
    return AGENT if AGENT in set(found_by) else CONTRIBUTION


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


class ReviewFilters(ContractModel):
    kind: QueueKind | None = None
    craft_slug: str | None = Field(default=None, min_length=1, max_length=SLUG_MAX_CHARS)
    origin: ReviewOrigin | None = None
    cursor: str | None = Field(default=None, min_length=1, max_length=CURSOR_MAX_CHARS)
    limit: int = Field(default=PAGE_DEFAULT, ge=1, le=PAGE_MAX)


class Proposer(ContractModel):
    name: str
    role: str


class FactConcept(ContractModel):
    name: str
    type: str


class FactReview(ContractModel):
    statement: str
    field: Discipline | None
    fields: list[Discipline]
    status: str
    level: EvidenceLevel
    sources_differ: bool
    concept: FactConcept | None
    sources: list[FactSource]
    gates: list[GateCheck]


class _QueueItem(ContractModel):
    id: uuid.UUID
    origin: ReviewOrigin
    submitted_at: datetime
    craft: CraftRef | None
    proposer: Proposer | None = None


class FactItem(_QueueItem):
    kind: Literal["FACTS"] = "FACTS"
    fact: FactReview


class TestimonyItem(_QueueItem):
    kind: Literal["TESTIMONY"] = "TESTIMONY"
    testimony: dict[str, Any]


class PictureItem(_QueueItem):
    kind: Literal["IMAGES"] = "IMAGES"
    picture: ImageContributionView


class ComponentItem(_QueueItem):
    kind: Literal["COMPONENTS"] = "COMPONENTS"
    component: ComponentReview


class LayoutItem(_QueueItem):
    kind: Literal["LAYOUTS"] = "LAYOUTS"
    layout: LayoutReview


class StructureQueueItem(_QueueItem):
    kind: Literal["STRUCTURE"] = "STRUCTURE"
    structure: StructureReview


QueueItem = Annotated[
    FactItem | TestimonyItem | PictureItem | ComponentItem | LayoutItem | StructureQueueItem,
    Field(discriminator="kind"),
]


class ReviewQueuePage(ContractModel):
    schema_version: Literal[1] = REVIEW_QUEUE_SCHEMA_VERSION
    kinds: list[QueueKind]
    counts: dict[str, int]
    total: int = Field(ge=0)
    items: list[QueueItem]
    next_cursor: str | None


class QueueApproval(ContractModel):
    note: Note | None = None
    version: int | None = Field(default=None, ge=1)
    english_checked: bool = False


class QueueRejection(ContractModel):
    reason: Reason
    version: int | None = Field(default=None, ge=1)
    testimony_reason: TestimonyReason | None = None


class FactLevelRaise(ContractModel):
    note: Note | None = None


class FactRetraction(ContractModel):
    reason: Reason


class QueueDecision(ContractModel):
    schema_version: Literal[1] = REVIEW_QUEUE_SCHEMA_VERSION
    kind: QueueKind
    id: uuid.UUID
    status: str
    level: EvidenceLevel | None = None
    sources_differ: bool | None = None
    message: str
