from __future__ import annotations

import re
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from types import MappingProxyType
from typing import Literal, Self

from pydantic import Field, model_validator

from app.core.errors import InvalidInput

from .base import ContractModel
from .chapter_keys import CHAPTER_KEYS
from .craft_parts import Focal
from .monograph_document import SUBJECT_KINDS
from .monograph_page import COMPONENT_LABEL_PATTERN, LayoutEntry

__all__ = [
    "CAPTION_MAX_CHARS",
    "COMPONENT_ROLES",
    "HERO_CHAPTER",
    "LAYOUT_ENTRIES_MAX",
    "LAYOUT_ROLES",
    "LAYOUT_SIZES",
    "PAGE_LAYOUT_SCHEMA_VERSION",
    "PICTURE_ROLES",
    "UNIT_ROLES",
    "LayoutReply",
    "LayoutWrite",
    "PageLayout",
    "PageLayoutEntry",
    "arranged_layout",
    "is_component_ref",
    "is_picture_ref",
    "picture_label",
]

PAGE_LAYOUT_SCHEMA_VERSION = 1
LAYOUT_ROLES = ("HERO", "OPENER", "PLATE", "FIGURE", "SIDEBAR", "PULL_QUOTE", "BODY")
LAYOUT_SIZES = ("MARGIN", "COLUMN", "WIDE", "BLEED")
LAYOUT_ENTRIES_MAX = 4000
CAPTION_MAX_CHARS = 300
REF_MAX_CHARS = 200
CHAPTER_PATTERN = r"^[a-z][a-z0-9-]{0,39}$"
UNIT_REF_PATTERN = re.compile(r"^[A-Za-z0-9._-]+$")
LABEL_PATTERN = re.compile(COMPONENT_LABEL_PATTERN)
LABEL_SEPARATOR = "/"
ONCE_PER_PAGE = frozenset({"HERO"})
ONCE_PER_CHAPTER = frozenset({"OPENER"})
COMPONENT_ROLES = frozenset({"HERO", "OPENER", "PLATE", "FIGURE"})
UNIT_ROLES = frozenset({"PULL_QUOTE"})
HERO_CHAPTER = CHAPTER_KEYS[0]
PICTURE_SEGMENT = "pictures"
PICTURE_ROLES: Mapping[str, str] = MappingProxyType(
    {
        "MASTHEAD": "HERO",
        "OPENER": "OPENER",
        "PLATE": "PLATE",
        "MATERIAL": "PLATE",
        "RECORD": "FIGURE",
        "STAGE": "FIGURE",
    }
)

LayoutRole = Literal[*LAYOUT_ROLES]
LayoutSize = Literal[*LAYOUT_SIZES]
SubjectKind = Literal[*SUBJECT_KINDS]


def is_component_ref(ref: str) -> bool:
    return LABEL_SEPARATOR in ref


def is_picture_ref(ref: str) -> bool:
    return ref.split(LABEL_SEPARATOR)[1:2] == [PICTURE_SEGMENT]


def picture_label(slug: str, key: str) -> str:
    label = f"{slug.lower()}{LABEL_SEPARATOR}{PICTURE_SEGMENT}{LABEL_SEPARATOR}{key.lower()}"
    if not LABEL_PATTERN.fullmatch(label):
        raise InvalidInput(f"The picture {key} of {slug} gives no component label: {label!r}")
    return label


class PageLayoutEntry(ContractModel):
    ref: str = Field(min_length=1, max_length=REF_MAX_CHARS)
    chapter: str = Field(pattern=CHAPTER_PATTERN)
    order: int = Field(ge=1)
    role: LayoutRole
    crop: Focal | None = None
    size: LayoutSize | None = None
    caption: str | None = Field(default=None, min_length=1, max_length=CAPTION_MAX_CHARS)

    @model_validator(mode="after")
    def _a_unit_or_a_component(self) -> Self:
        component = is_component_ref(self.ref)
        pattern = LABEL_PATTERN if component else UNIT_REF_PATTERN
        if not pattern.fullmatch(self.ref):
            raise ValueError(f"{self.ref!r} is neither a unit id nor a component label")
        if component and self.role in UNIT_ROLES:
            raise ValueError(f"{self.ref} is a component; a {self.role} is a text unit")
        if not component and self.role in COMPONENT_ROLES:
            raise ValueError(f"{self.ref} is a text unit; a {self.role} is a component")
        if not component and (self.crop is not None or self.caption is not None):
            raise ValueError(f"{self.ref} is a text unit: only a component takes a crop or a caption")
        return self


def check_entries(entries: Sequence[PageLayoutEntry]) -> None:
    repeated = sorted(ref for ref, count in Counter(e.ref for e in entries).items() if count > 1)
    if repeated:
        raise ValueError(f"a layout places each unit or component once: {repeated}")
    slots = Counter((e.chapter, e.order) for e in entries)
    taken = sorted(f"{chapter} {order}" for (chapter, order), count in slots.items() if count > 1)
    if taken:
        raise ValueError(f"two entries share a place in their chapter: {taken}")
    heroes = [e.ref for e in entries if e.role in ONCE_PER_PAGE]
    if len(heroes) > 1:
        raise ValueError(f"a page has one HERO: {heroes}")
    openers = Counter(e.chapter for e in entries if e.role in ONCE_PER_CHAPTER)
    crowded = sorted(chapter for chapter, count in openers.items() if count > 1)
    if crowded:
        raise ValueError(f"a chapter has one OPENER: {crowded}")


class LayoutWrite(ContractModel):
    base_version: int = Field(ge=0)
    entries: list[PageLayoutEntry] = Field(max_length=LAYOUT_ENTRIES_MAX)

    @model_validator(mode="after")
    def _entries_follow_the_rules(self) -> Self:
        check_entries(self.entries)
        return self


class PageLayout(ContractModel):
    schema_version: Literal[1] = PAGE_LAYOUT_SCHEMA_VERSION
    subject_kind: SubjectKind
    subject_slug: str = Field(min_length=1, max_length=REF_MAX_CHARS, pattern=r"^[A-Za-z0-9-]+$")
    version: int = Field(ge=1)
    entries: list[PageLayoutEntry] = Field(max_length=LAYOUT_ENTRIES_MAX)

    @model_validator(mode="after")
    def _entries_follow_the_rules(self) -> Self:
        check_entries(self.entries)
        return self

    def entry(self, ref: str) -> PageLayoutEntry | None:
        return next((e for e in self.entries if e.ref == ref), None)


class LayoutReply(ContractModel):
    schema_version: Literal[1] = PAGE_LAYOUT_SCHEMA_VERSION
    subject_kind: SubjectKind
    subject_slug: str
    layout: PageLayout | None
    page_url: str


@dataclass(frozen=True)
class _Block:
    head: LayoutEntry
    within: tuple[LayoutEntry, ...]


def arranged_layout(
    default: Sequence[LayoutEntry], layout: PageLayout | None, chapters: Sequence[str] = CHAPTER_KEYS
) -> list[LayoutEntry]:
    blocks = _blocks(default)
    named = {e.ref: e for e in layout.entries} if layout is not None else {}
    placed: dict[str, list[tuple[tuple[int, int], _Block]]] = {}
    for position, block in enumerate(blocks):
        entry = named.get(block.head.ref)
        chapter = entry.chapter if entry is not None else block.head.chapter
        rank = (0, entry.order) if entry is not None else (1, position)
        placed.setdefault(chapter, []).append((rank, block))
    order = [*chapters, *(chapter for chapter in placed if chapter not in chapters)]
    arranged: list[LayoutEntry] = []
    for chapter in order:
        for _, block in sorted(placed.get(chapter, []), key=lambda item: item[0]):
            arranged.extend(e.model_copy(update={"chapter": chapter}) for e in (block.head, *block.within))
    return arranged


def _blocks(default: Sequence[LayoutEntry]) -> list[_Block]:
    heads = [e for e in default if e.within is None]
    labels = {e.ref for e in heads if e.kind == "component"}
    within: dict[str, list[LayoutEntry]] = {}
    for entry in default:
        if entry.within is not None:
            within.setdefault(entry.within, []).append(entry)
    stray = sorted(set(within) - labels)
    if stray:
        raise InvalidInput(f"Layout entries sit within components the page lacks: {stray}")
    return [_Block(head, tuple(within.get(head.ref, ()))) for head in heads]
