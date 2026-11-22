from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from typing import Any

from .open_data_text import (
    BIBTEX_KEY,
    DATASET_TITLE,
    KEYWORDS,
    SUMMARY,
    citation_bibtex,
    citation_text,
    data_page,
)

__all__ = ["CRAFT_PROPERTY", "PACKAGE_NAME", "WHOLE", "ReleaseScope", "scope_of_descriptor"]

PACKAGE_NAME = "kalavigyan-open-knowledge"
CRAFT_PROPERTY = "craft"
CRAFT_KEY = "kalavigyan_{craft}"
CRAFTS_PATH = "/crafts/"
NOT_KEY_CHARS = re.compile(r"[^a-z0-9]+")
NOT_NAME_CHARS = re.compile(r"[^a-z0-9._-]+")
HALF_SCOPE = "A craft release names both its craft's slug and its name."
CRAFT_SUMMARY = (
    "The slice of KalaVigyan's knowledge about {name}: the cited facts an answer about {name} reads (its "
    "own, those its craft family shares and its category's science), with the sources they rest on and "
    "where in each source the supporting words stand; the craft with its Wikidata item, its places by Local "
    "Government Directory code, its family and its category; its curated structure (stages, materials and "
    "tools, reactions as stated, native names and its geographical indication); the components that rest on "
    "its facts; and the records of the open datasets those components draw."
)


@dataclass(frozen=True)
class ReleaseScope:
    craft: str | None = None
    name: str | None = None

    def __post_init__(self) -> None:
        if (self.craft is None) != (self.name is None) or self.craft == "" or self.name == "":
            raise ValueError(HALF_SCOPE)

    @property
    def title(self) -> str:
        return DATASET_TITLE if self.name is None else f"{self.name}: {DATASET_TITLE}"

    @property
    def summary(self) -> str:
        return SUMMARY if self.name is None else CRAFT_SUMMARY.format(name=self.name)

    @property
    def keywords(self) -> tuple[str, ...]:
        return KEYWORDS if self.name is None else (*KEYWORDS, self.name)

    @property
    def package_name(self) -> str:
        if self.craft is None:
            return PACKAGE_NAME
        return f"{PACKAGE_NAME}-{NOT_NAME_CHARS.sub('-', self.craft.lower()).strip('-')}"

    @property
    def bibtex_key(self) -> str:
        if self.craft is None:
            return BIBTEX_KEY
        return CRAFT_KEY.format(craft=NOT_KEY_CHARS.sub("_", self.craft.lower()).strip("_"))

    def craft_page(self, site: str) -> str | None:
        return None if self.craft is None else f"{site.rstrip('/')}{CRAFTS_PATH}{self.craft}"

    def citation(self, version: str, released: date, doi: str) -> str:
        return citation_text(version, released, doi, title=self.title)

    def bibtex(self, version: str, released: date, doi: str) -> str:
        return citation_bibtex(version, released, doi, title=self.title, key=self.bibtex_key)

    def whole_note(self, site: str) -> str | None:
        if self.craft is None:
            return None
        return f"The whole of KalaVigyan's knowledge is released as {DATASET_TITLE}: {data_page(site)}."

    def descriptor_property(self, site: str) -> dict[str, Any]:
        if self.craft is None:
            return {}
        return {CRAFT_PROPERTY: {"slug": self.craft, "name": self.name, "path": self.craft_page(site)}}


WHOLE = ReleaseScope()


def scope_of_descriptor(descriptor: Mapping[str, Any]) -> ReleaseScope:
    found = descriptor.get(CRAFT_PROPERTY)
    if not isinstance(found, Mapping):
        return WHOLE
    return ReleaseScope(craft=str(found.get("slug") or ""), name=str(found.get("name") or ""))
