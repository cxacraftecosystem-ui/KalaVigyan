from __future__ import annotations

import uuid
from typing import Literal

from pydantic import Field

from .article_sections import ArticleSection
from .base import ContractModel, absent, empty
from .coverage import FieldCount, FieldCoverage
from .crafts import QUESTION_MAX_CHARS, SLUG_MAX_CHARS, CraftRef
from .open_work import OpenTask
from .vocabulary import Discipline, EvidenceLevel, PieceKind, PieceSubjectKind

__all__ = [
    "ATTRIBUTION",
    "COMPONENTS_LIMIT_MAX",
    "FACTS_LIMIT_DEFAULT",
    "FACTS_LIMIT_MAX",
    "KNOWLEDGE_API_SCHEMA_VERSION",
    "ComponentSubject",
    "ComponentSummary",
    "CoverageSummary",
    "CraftComponents",
    "CraftFacts",
    "CraftSection",
    "Fact",
    "FactCitation",
    "FactFigure",
    "FactQuantity",
    "FactReading",
    "FactSource",
    "FieldFacts",
    "FieldInfo",
    "FieldList",
    "FieldSection",
    "FoundCraft",
    "FoundCrafts",
    "SchemaVersion",
    "SubjectCoverage",
    "coverage_summary",
]

KNOWLEDGE_API_SCHEMA_VERSION = 1
FACTS_LIMIT_DEFAULT = 20
FACTS_LIMIT_MAX = 50
COMPONENTS_LIMIT_MAX = 100
ATTRIBUTION = (
    "KalaVigyan, Centre of Excellence for Unified AI-Enabled Craft Ecosystem Platform, IIT Kharagpur. "
    "Name KalaVigyan and the Centre, and link the craft's page, wherever this content is shown."
)

SchemaVersion = Literal[1]


class FieldInfo(ContractModel):
    field: Discipline
    title: str
    covers: str
    chapter: str
    held: FieldCount | None = Field(default=None, exclude_if=absent)


class FieldList(ContractModel):
    schema_version: SchemaVersion = KNOWLEDGE_API_SCHEMA_VERSION
    craft_slug: str | None = Field(default=None, max_length=SLUG_MAX_CHARS, exclude_if=absent)
    fields: list[FieldInfo]


class CoverageSummary(ContractModel):
    claims: int = Field(ge=0)
    covered: list[Discipline]
    thin: list[Discipline]
    missing: list[Discipline]
    field_claims: dict[Discipline, int]


class FoundCraft(ContractModel):
    craft: CraftRef
    score: float = Field(ge=0.0, le=1.0)
    page_url: str
    fields: CoverageSummary | None = Field(default=None, exclude_if=absent)


class FoundCrafts(ContractModel):
    schema_version: SchemaVersion = KNOWLEDGE_API_SCHEMA_VERSION
    query: str = Field(min_length=1, max_length=QUESTION_MAX_CHARS)
    crafts: list[FoundCraft]


class FactCitation(ContractModel):
    source_id: str
    quote: str | None
    locator: str | None


class FactSource(ContractModel):
    id: str
    kind: str
    title: str
    authors: list[str]
    year: int | None
    doi: str | None
    url: str | None
    publisher: str | None
    licence: str | None
    attribution: str | None


class FactQuantity(ContractModel):
    value: float
    unit: str


class FactReading(ContractModel):
    label: str
    stated: str
    low: float | None
    high: float | None
    unit: str


class FactFigure(ContractModel):
    label: str
    kind: str
    title: str


class Fact(ContractModel):
    id: uuid.UUID
    text: str
    level: EvidenceLevel
    field: Discipline | None
    fields: list[Discipline]
    citations: list[FactCitation] = Field(min_length=1)
    quantity: FactQuantity | None = Field(default=None, exclude_if=absent)
    readings: list[FactReading] = Field(default_factory=list, exclude_if=empty)
    figures: list[FactFigure] = Field(default_factory=list, exclude_if=empty)


class FieldFacts(ContractModel):
    field: Discipline
    count: int = Field(ge=0)
    shown: list[uuid.UUID]


class CraftFacts(ContractModel):
    schema_version: SchemaVersion = KNOWLEDGE_API_SCHEMA_VERSION
    craft: CraftRef
    field: Discipline | None
    query: str | None
    facts: list[Fact]
    by_field: list[FieldFacts] = Field(default_factory=list)
    open_work: list[OpenTask] = Field(default_factory=list)
    sources: list[FactSource]
    page_url: str
    attribution: str = ATTRIBUTION


class FieldSection(ContractModel):
    field: Discipline
    sentences: int = Field(ge=0)
    claims: int = Field(ge=0)


class CraftSection(ContractModel):
    schema_version: SchemaVersion = KNOWLEDGE_API_SCHEMA_VERSION
    craft: CraftRef
    field: Discipline | None
    section: ArticleSection | None
    sections: list[ArticleSection] = Field(default_factory=list)
    by_field: list[FieldSection] = Field(default_factory=list)
    open_work: list[OpenTask] = Field(default_factory=list)
    page_url: str
    attribution: str = ATTRIBUTION


class SubjectCoverage(ContractModel):
    schema_version: SchemaVersion = KNOWLEDGE_API_SCHEMA_VERSION
    coverage: FieldCoverage
    open_work: list[OpenTask]
    page_url: str
    attribution: str = ATTRIBUTION


class ComponentSubject(ContractModel):
    kind: PieceSubjectKind
    key: str
    name: str


class ComponentSummary(ContractModel):
    label: str
    title: str
    description: str
    kind: str
    field: Discipline
    fields: list[Discipline]
    craft_slug: str | None
    subjects: list[ComponentSubject]


class CraftComponents(ContractModel):
    schema_version: SchemaVersion = KNOWLEDGE_API_SCHEMA_VERSION
    craft_slug: str | None = Field(max_length=SLUG_MAX_CHARS)
    field: Discipline | None
    kind: PieceKind | None = None
    query: str | None = Field(default=None, max_length=QUESTION_MAX_CHARS)
    components: list[ComponentSummary]


def coverage_summary(coverage: FieldCoverage) -> CoverageSummary:
    return CoverageSummary(
        claims=coverage.claims,
        covered=list(coverage.covered),
        thin=list(coverage.thin),
        missing=list(coverage.missing),
        field_claims={count.field: count.claims for count in coverage.fields},
    )
