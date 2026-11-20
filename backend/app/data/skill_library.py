from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from types import MappingProxyType

from .contributor_kit import CONTRIBUTOR_SKILL_PATH

__all__ = [
    "DATASETS_SITE_PATH",
    "DATASETS_SKILL_PATH",
    "REFERENCES",
    "REFERENCES_DIR",
    "Reference",
    "datasets_skill",
    "prompt_reference",
    "reference_text",
]

CONTRIBUTOR_DIR = CONTRIBUTOR_SKILL_PATH.parent
REFERENCES_DIR = CONTRIBUTOR_DIR / "references"
DATASETS_SKILL_PATH = CONTRIBUTOR_DIR / "kalavigyan-datasets" / "SKILL.md"
DATASETS_SITE_PATH = "/skills/kalavigyan-datasets/SKILL.md"
REFERENCE_URI_PREFIX = "kalavigyan://skills/references/"
REFERENCE_SITE_PREFIX = "/skills/references/"
HEADING = re.compile(r"^(#+) ", re.MULTILINE)


@dataclass(frozen=True)
class Reference:
    name: str
    title: str
    holds: str

    @property
    def file_name(self) -> str:
        return f"{self.name}.md"

    @property
    def path(self) -> Path:
        return REFERENCES_DIR / self.file_name

    @property
    def uri(self) -> str:
        return REFERENCE_URI_PREFIX + self.file_name

    @property
    def site_path(self) -> str:
        return REFERENCE_SITE_PREFIX + self.file_name


REFERENCES: Mapping[str, Reference] = MappingProxyType(
    {
        reference.name: reference
        for reference in (
            Reference(
                "page-checklist",
                "The page checklist",
                "The 26 rules every craft, family, category and answer page meets, and the three lists each "
                "page derives first",
            ),
            Reference(
                "sources",
                "What counts as a source",
                "How sources are chosen, graded A to D and recorded, and the licences that let their material "
                "be shown",
            ),
            Reference(
                "quotes",
                "Quotes and locators",
                "Verbatim quotes, their locators and the one-fact-per-sentence rules every fact follows",
            ),
            Reference("fields", "The fields", "The sixteen fields a fact is filed under and what each holds"),
            Reference(
                "components",
                "Authoring a component",
                "Choosing among the 42 kinds and the five general kinds, units and citations in a spec, and the "
                "design rules for a contributed figure",
            ),
            Reference(
                "datasets",
                "Datasets",
                "The open datasets behind charts, tables, timelines and map layers: licences, provenance, units, "
                "projection, simplification, delivery and checks",
            ),
        )
    }
)


@cache
def reference_text(name: str) -> str:
    return REFERENCES[name].path.read_bytes().decode("utf-8")


def prompt_reference(name: str) -> str:
    return HEADING.sub(r"#\1 ", reference_text(name)).strip()


@cache
def datasets_skill() -> str:
    return DATASETS_SKILL_PATH.read_bytes().decode("utf-8")
