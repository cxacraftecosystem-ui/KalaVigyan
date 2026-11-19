from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Literal, Self

from pydantic import Field, model_validator

from app.models.enums import DISCIPLINES

from .base import ContractModel
from .crafts import SLUG_MAX_CHARS
from .vocabulary import Discipline

__all__ = [
    "COVERAGE_SCHEMA_VERSION",
    "COVERAGE_SUBJECT_KINDS",
    "COVERED",
    "FIELD_STANDINGS",
    "MISSING",
    "STRUCTURE_FIELDS",
    "THIN",
    "CoverageSubject",
    "FieldCount",
    "FieldCoverage",
    "Holdings",
    "field_coverage",
    "field_standing",
    "held_fields",
]

COVERAGE_SCHEMA_VERSION = 1
COVERAGE_SUBJECT_KINDS = ("craft", "family", "category")
COVERED, THIN, MISSING = "COVERED", "THIN", "MISSING"
FIELD_STANDINGS = (COVERED, THIN, MISSING)
STRUCTURE_FIELDS: Mapping[str, str] = MappingProxyType({"communities": "SOCIETY", "gi": "POLICY"})
NO_IDS: frozenset[str] = frozenset()

Standing = Literal[*FIELD_STANDINGS]
CoverageSubjectKind = Literal[*COVERAGE_SUBJECT_KINDS]


class FieldCount(ContractModel):
    field: Discipline
    claims: int = Field(ge=0)
    structure_claims: int = Field(ge=0)
    sources: int = Field(ge=0)
    sections: int = Field(ge=0, le=1)
    sentences: int = Field(ge=0)
    figures: int = Field(ge=0)
    standing: Standing

    @model_validator(mode="after")
    def _counts_agree(self) -> Self:
        if self.structure_claims > self.claims:
            raise ValueError(f"{self.field} counts more structure-cited claims than claims")
        if (self.claims == 0) != (self.standing == MISSING):
            raise ValueError(f"{self.field} is missing exactly when it holds no cited claim")
        if self.claims and not self.sources:
            raise ValueError(f"{self.field} holds cited claims, so it names their sources")
        if self.sections == 0 and self.sentences:
            raise ValueError(f"{self.field} counts sentences only of a published section")
        return self


class FieldCoverage(ContractModel):
    schema_version: Literal[1] = COVERAGE_SCHEMA_VERSION
    subject_kind: CoverageSubjectKind
    subject_slug: str = Field(min_length=1, max_length=SLUG_MAX_CHARS, pattern=r"^[A-Za-z0-9-]+$")
    name: str = Field(min_length=1)
    claims_min: int = Field(ge=1)
    claims: int = Field(ge=0)
    sources: int = Field(ge=0)
    covered: list[Discipline]
    thin: list[Discipline]
    missing: list[Discipline]
    fields: list[FieldCount]

    @model_validator(mode="after")
    def _every_field_once_in_order(self) -> Self:
        if [count.field for count in self.fields] != list(DISCIPLINES):
            raise ValueError("a coverage lists the sixteen fields once each, in vocabulary order")
        for standing, listed in ((COVERED, self.covered), (THIN, self.thin), (MISSING, self.missing)):
            if listed != [count.field for count in self.fields if count.standing == standing]:
                raise ValueError(f"the {standing.lower()} fields are those whose standing says so")
        wrong = [
            c.field for c in self.fields if c.standing != field_standing(c.claims, claims_min=self.claims_min)
        ]
        if wrong:
            raise ValueError(f"the standing of {', '.join(wrong)} disagrees with its claims")
        return self

    def count(self, discipline: str) -> FieldCount:
        return next(count for count in self.fields if count.field == discipline)


@dataclass(frozen=True)
class CoverageSubject:
    kind: str
    slug: str
    name: str


@dataclass(frozen=True)
class Holdings:
    filed: Mapping[str, frozenset[str]] = field(default_factory=dict)
    sources: Mapping[str, frozenset[str]] = field(default_factory=dict)
    structure: Mapping[str, frozenset[str]] = field(default_factory=dict)
    sections: Mapping[str, int] = field(default_factory=dict)
    figures: Mapping[str, frozenset[str]] = field(default_factory=dict)


def field_standing(claims: int, *, claims_min: int) -> str:
    if claims == 0:
        return MISSING
    return COVERED if claims >= claims_min else THIN


def field_coverage(subject: CoverageSubject, holdings: Holdings, *, claims_min: int) -> FieldCoverage:
    cited = {claim for claim, sources in holdings.sources.items() if sources}
    counts = [_count(discipline, holdings, cited, claims_min) for discipline in DISCIPLINES]
    claimed = {claim for claim in cited if holdings.filed.get(claim) or _structured(claim, holdings)}
    return FieldCoverage(
        subject_kind=subject.kind,
        subject_slug=subject.slug,
        name=subject.name,
        claims_min=claims_min,
        claims=len(claimed),
        sources=len(set().union(*(holdings.sources[claim] for claim in claimed))),
        covered=[count.field for count in counts if count.standing == COVERED],
        thin=[count.field for count in counts if count.standing == THIN],
        missing=[count.field for count in counts if count.standing == MISSING],
        fields=counts,
    )


def held_fields(coverage: FieldCoverage) -> tuple[str, ...]:
    return tuple(count.field for count in coverage.fields if count.claims)


def _count(discipline: str, holdings: Holdings, cited: set[str], claims_min: int) -> FieldCount:
    filed = {claim for claim in cited if discipline in holdings.filed.get(claim, NO_IDS)}
    structured = {claim for claim in holdings.structure.get(discipline, NO_IDS) if claim in cited}
    claims = filed | structured
    sentences = holdings.sections.get(discipline)
    return FieldCount(
        field=discipline,
        claims=len(claims),
        structure_claims=len(structured - filed),
        sources=len(set().union(*(holdings.sources[claim] for claim in claims))),
        sections=0 if sentences is None else 1,
        sentences=sentences or 0,
        figures=len(holdings.figures.get(discipline, NO_IDS)),
        standing=field_standing(len(claims), claims_min=claims_min),
    )


def _structured(claim: str, holdings: Holdings) -> bool:
    return any(claim in claims for claims in holdings.structure.values())
