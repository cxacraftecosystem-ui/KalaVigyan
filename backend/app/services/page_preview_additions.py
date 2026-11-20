from __future__ import annotations

import uuid
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any

from app.models.enums import DISCIPLINES
from app.research.monograph_page import CitedSource
from app.research.page_layout import PageLayout

from .knowledge_view import ClaimView
from .monograph_generated_parts import RegisteredComponent, StoredSection
from .monograph_generated_pictures import PlateSource

__all__ = ["NO_ADDITIONS", "PageAdditions"]

FIELD_ORDER = MappingProxyType({name: n for n, name in enumerate(DISCIPLINES)})
NEW_SECTION_VERSION = 0


@dataclass(frozen=True)
class PageAdditions:
    sentences: Mapping[str, tuple[Mapping[str, Any], ...]] = field(default_factory=dict)
    claims: Mapping[uuid.UUID, ClaimView] = field(default_factory=dict)
    sources: Mapping[str, CitedSource] = field(default_factory=dict)
    delivered: tuple[RegisteredComponent, ...] = ()
    layout: PageLayout | None = None
    given: tuple[PlateSource, ...] = ()

    def pictures(self, found: Sequence[PlateSource]) -> tuple[PlateSource, ...]:
        held = {picture.key for picture in found}
        return (*found, *(picture for picture in self.given if picture.key not in held))

    def sections(self, stored: Sequence[StoredSection]) -> list[StoredSection]:
        by_field = {section.field: section for section in stored}
        for name, sentences in self.sentences.items():
            held = by_field.get(name)
            version = held.version if held is not None else NEW_SECTION_VERSION
            kept = held.sentences if held is not None else ()
            by_field[name] = StoredSection(name, version, (*kept, *sentences))
        return sorted(by_field.values(), key=lambda section: FIELD_ORDER.get(section.field, len(FIELD_ORDER)))

    def components(self, found: Sequence[RegisteredComponent]) -> tuple[RegisteredComponent, ...]:
        replaced = {component.label for component in self.delivered}
        kept = [component for component in found if component.label not in replaced]
        return tuple(sorted([*kept, *self.delivered], key=lambda component: component.label))


NO_ADDITIONS = PageAdditions()
