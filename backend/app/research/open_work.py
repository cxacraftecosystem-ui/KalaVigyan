from __future__ import annotations

import re
import uuid
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from types import MappingProxyType
from typing import Literal, Self

from pydantic import Field, model_validator

from app.core.errors import InvalidInput
from app.core.roles import Capability
from app.models.enums import DISCIPLINES
from app.models.open_work import TASK_KEY_COLUMN_CHARS

from .base import ContractModel
from .crafts import SLUG_MAX_CHARS
from .image_contributions_tasks import PICTURE_TASK, is_picture_detail
from .vocabulary import Discipline

__all__ = [
    "COMPONENT_NEEDS",
    "COMPONENT_NEED_TITLES",
    "DELIVER_PAGE_PROMPT",
    "GIVE_PICTURE_PROMPT",
    "NO_ITEMS",
    "OPEN_WORK_SCHEMA_VERSION",
    "OWNER_ORDER",
    "PRIORITIES",
    "PROMPT_NAMES",
    "PROPOSE_COMPONENT_PROMPT",
    "RESEARCH_FIELD_PROMPT",
    "RESERVATIONS_HELD_MAX",
    "RESERVATION_TIME",
    "REVIEW_QUEUES",
    "REVIEW_QUEUE_LABELS",
    "SUBJECT_KINDS",
    "TASKS_LIMIT_DEFAULT",
    "TASKS_LIMIT_MAX",
    "TASK_ITEMS_MAX",
    "TASK_KEY_MAX_CHARS",
    "TASK_KINDS",
    "TASK_PROMPTS",
    "UNRESERVABLE_KINDS",
    "WRITE_SECTION_PROMPT",
    "CoverageTargets",
    "FieldStanding",
    "Hold",
    "Items",
    "OpenTask",
    "OpenWork",
    "Priority",
    "QueueStanding",
    "SubjectKind",
    "SubjectStanding",
    "TaskHold",
    "TaskKey",
    "TaskKind",
    "TaskSubject",
    "Viewer",
    "WorkFilters",
    "parse_task_key",
    "several_subjects",
    "task_key",
]

OPEN_WORK_SCHEMA_VERSION = 1
TASK_KINDS = (
    "MISSING_FIELD",
    "THIN_FIELD",
    "SECTION",
    "MISSING_COMPONENT",
    "PAGE_FORM",
    "PAGE_LAYOUT",
    "SECOND_SOURCE",
    "SOURCES_DIFFER",
    "DEAD_SOURCE",
    "UNARCHIVED_SOURCE",
    "RESOURCE_FACT",
    "CORROBORATE_FACT",
    "FIND_ANOTHER_SOURCE",
    "REVIEW",
    PICTURE_TASK,
)
UNRESERVABLE_KINDS = frozenset({"REVIEW"})
PRIORITIES = ("HIGH", "MEDIUM", "LOW")
SUBJECT_KINDS = ("craft", "family", "category")
REVIEW_QUEUES: Mapping[str, Capability] = MappingProxyType(
    {
        "FACTS": Capability.MARK_CLAIM_LEVEL,
        "TESTIMONY": Capability.REVIEW_TESTIMONY,
        "IMAGES": Capability.REVIEW_CONTRIBUTIONS,
        "COMPONENTS": Capability.REVIEW_CONTRIBUTIONS,
        "LAYOUTS": Capability.REVIEW_CONTRIBUTIONS,
        "STRUCTURE": Capability.MARK_CLAIM_LEVEL,
    }
)
REVIEW_QUEUE_LABELS: Mapping[str, str] = MappingProxyType(
    {
        "FACTS": "proposed facts",
        "TESTIMONY": "items of artisans' testimony",
        "IMAGES": "contributed pictures",
        "COMPONENTS": "component proposals",
        "LAYOUTS": "layout proposals",
        "STRUCTURE": "structure proposals",
    }
)
COMPONENT_NEEDS: Mapping[str, tuple[str, ...]] = MappingProxyType(
    {
        "what-if": ("what_if", "experiment_lab"),
        "molecules": ("molecule_3d",),
        "map": (
            "map_layer",
            "region_story",
            "timeline_map",
            "supply_map",
            "map_sequence",
            "general_map_layer",
        ),
        "reaction-player": (
            "reaction_player",
            "indigo_vat",
            "mordant_bath",
            "lost_wax",
            "firing",
            "dip_player",
        ),
        "pictures": ("images", "picture_plate", "specimen_plate"),
    }
)
COMPONENT_NEED_TITLES: Mapping[str, str] = MappingProxyType(
    {
        "what-if": "What-if explorer",
        "molecules": "3D molecule",
        "map": "map",
        "reaction-player": "reaction player",
        "pictures": "picture plate",
    }
)
OWNER_ORDER = (
    "Bidriware",
    "Blue-Pottery-Of-Jaipur",
    "Kutch-Bandhani",
    "Machilipatnam-Kalamkari",
    "Madhubani-Paintings",
    "Orissa-Pattachitra",
    "Bastar-Dhokra",
    "Channapatna-Toys-Dolls",
)
RESEARCH_FIELD_PROMPT = "research_field"
WRITE_SECTION_PROMPT = "write_section"
PROPOSE_COMPONENT_PROMPT = "propose_component"
DELIVER_PAGE_PROMPT = "deliver_page"
GIVE_PICTURE_PROMPT = "give_picture"
PROMPT_NAMES = (
    RESEARCH_FIELD_PROMPT,
    WRITE_SECTION_PROMPT,
    PROPOSE_COMPONENT_PROMPT,
    DELIVER_PAGE_PROMPT,
    GIVE_PICTURE_PROMPT,
)
TASK_PROMPTS: Mapping[str, str] = MappingProxyType(
    {
        "MISSING_FIELD": RESEARCH_FIELD_PROMPT,
        "THIN_FIELD": RESEARCH_FIELD_PROMPT,
        "SECOND_SOURCE": RESEARCH_FIELD_PROMPT,
        "SOURCES_DIFFER": RESEARCH_FIELD_PROMPT,
        "DEAD_SOURCE": RESEARCH_FIELD_PROMPT,
        "UNARCHIVED_SOURCE": RESEARCH_FIELD_PROMPT,
        "SECTION": WRITE_SECTION_PROMPT,
        "MISSING_COMPONENT": PROPOSE_COMPONENT_PROMPT,
        "MISSING_PICTURE": GIVE_PICTURE_PROMPT,
    }
)
TASKS_LIMIT_DEFAULT = 50
TASKS_LIMIT_MAX = 200
TASK_ITEMS_MAX = 20
TASK_KEY_MAX_CHARS = TASK_KEY_COLUMN_CHARS
RESERVATION_TIME = timedelta(hours=2)
RESERVATIONS_HELD_MAX = 5
KEY_SEPARATOR = ":"
SLUG_PATTERN = re.compile(r"^[A-Za-z0-9-]+$")

TaskKind = Literal[*TASK_KINDS]
Priority = Literal[*PRIORITIES]
SubjectKind = Literal[*SUBJECT_KINDS]


class TaskSubject(ContractModel):
    kind: SubjectKind
    slug: str = Field(min_length=1, max_length=SLUG_MAX_CHARS)
    name: str
    page_url: str


class OpenTask(ContractModel):
    key: str = Field(min_length=1, max_length=TASK_KEY_MAX_CHARS)
    kind: TaskKind
    priority: Priority
    subject: TaskSubject | None
    field: Discipline | None = None
    need: str | None = None
    needed: str
    acceptance: str
    count: int = Field(ge=0)
    fact_ids: list[uuid.UUID] = Field(default_factory=list, max_length=TASK_ITEMS_MAX)
    source_ids: list[str] = Field(default_factory=list, max_length=TASK_ITEMS_MAX)
    prompt: str | None = None
    reserved_until: datetime | None = None


class WorkFilters(ContractModel):
    craft_slug: str | None = Field(default=None, min_length=1, max_length=SLUG_MAX_CHARS)
    family_slug: str | None = Field(default=None, min_length=1, max_length=SLUG_MAX_CHARS)
    category_slug: str | None = Field(default=None, min_length=1, max_length=SLUG_MAX_CHARS)
    field: Discipline | None = None
    kind: TaskKind | None = None
    priority: Priority | None = None
    limit: int = Field(default=TASKS_LIMIT_DEFAULT, ge=1, le=TASKS_LIMIT_MAX)

    @model_validator(mode="after")
    def _one_subject(self) -> Self:
        refusal = several_subjects(self.craft_slug, self.family_slug, self.category_slug)
        if refusal is not None:
            raise ValueError(refusal)
        return self

    def subject_filter(self) -> tuple[str, str] | None:
        named = zip(SUBJECT_KINDS, (self.craft_slug, self.family_slug, self.category_slug), strict=True)
        return next(((kind, slug) for kind, slug in named if slug is not None), None)


class OpenWork(ContractModel):
    schema_version: Literal[1] = OPEN_WORK_SCHEMA_VERSION
    filters: WorkFilters
    total: int = Field(ge=0)
    reservation_minutes: int = Field(ge=1)
    tasks: list[OpenTask]


class TaskHold(ContractModel):
    schema_version: Literal[1] = OPEN_WORK_SCHEMA_VERSION
    task_key: str = Field(min_length=1, max_length=TASK_KEY_MAX_CHARS)
    held: bool
    reserved_until: datetime | None
    task: OpenTask | None = None


@dataclass(frozen=True)
class Items:
    count: int = 0
    ids: tuple[str, ...] = ()

    @classmethod
    def of(cls, ids: Iterable[str]) -> Items:
        listed = tuple(ids)
        return cls(count=len(listed), ids=listed[:TASK_ITEMS_MAX])


NO_ITEMS = Items()


@dataclass(frozen=True)
class CoverageTargets:
    core_fields: tuple[str, ...]
    facts_min: int
    section_sentences_min: int
    quote_chars_min: int
    quote_chars_max: int
    components: bool


@dataclass(frozen=True)
class FieldStanding:
    facts: int = 0
    section_sentences: int = 0
    one_source: Items = NO_ITEMS
    differing: Items = NO_ITEMS


@dataclass(frozen=True)
class SubjectStanding:
    subject: TaskSubject
    targets: CoverageTargets
    fields: Mapping[str | None, FieldStanding] = field(default_factory=dict)
    component_kinds: frozenset[str] = frozenset()
    new_form: bool = False
    layout: bool = False
    dead_sources: Items = NO_ITEMS
    unarchived_sources: Items = NO_ITEMS
    gi: bool = False
    curated: bool = False
    demand: int = 0
    healing: tuple[OpenTask, ...] = ()


@dataclass(frozen=True)
class QueueStanding:
    count: int
    oldest: datetime | None


@dataclass(frozen=True)
class Viewer:
    user_id: uuid.UUID | None = None
    review_role: str | None = None


@dataclass(frozen=True)
class Hold:
    user_id: uuid.UUID
    expires_at: datetime


@dataclass(frozen=True)
class TaskKey:
    kind: str
    subject_kind: str | None = None
    slug: str | None = None
    detail: str | None = None

    def text(self) -> str:
        parts = [self.kind, self.subject_kind, self.slug, self.detail]
        return KEY_SEPARATOR.join(part for part in parts if part is not None)


def several_subjects(*slugs: str | None) -> str | None:
    if sum(slug is not None for slug in slugs) > 1:
        return "filter by one of craft, family or category, not several"
    return None


def task_key(kind: str, subject: TaskSubject | None, detail: str | None = None) -> str:
    if subject is None:
        return TaskKey(kind, detail=detail).text()
    return TaskKey(kind, subject.kind, subject.slug, detail).text()


def parse_task_key(key: str) -> TaskKey:
    parts = key.split(KEY_SEPARATOR)
    if len(key) > TASK_KEY_MAX_CHARS or parts[0] not in TASK_KINDS:
        raise InvalidInput(f"{key} is not a task key; list_open_work gives the keys")
    if parts[0] == "REVIEW":
        if len(parts) != 2 or parts[1] not in REVIEW_QUEUES:
            raise InvalidInput(f"{key} names no review queue")
        return TaskKey(parts[0], detail=parts[1])
    if len(parts) not in (3, 4) or parts[1] not in SUBJECT_KINDS or not SLUG_PATTERN.match(parts[2]):
        raise InvalidInput(f"{key} is not a task key; list_open_work gives the keys")
    detail = parts[3] if len(parts) == 4 else None
    if (
        detail is not None
        and detail not in DISCIPLINES
        and detail not in COMPONENT_NEEDS
        and not is_picture_detail(detail)
    ):
        raise InvalidInput(f"{key} names neither a field nor a component need")
    return TaskKey(parts[0], parts[1], parts[2], detail)
