from __future__ import annotations

import re
from collections.abc import Mapping
from types import MappingProxyType
from typing import Annotated, Any, Literal, Self

from pydantic import Field, model_validator

from .base import ContractModel
from .monograph_page import COMPONENT_LABEL_PATTERN
from .unit_ids import UNIT_REF_PATTERN

__all__ = [
    "SPEC_MODELS_TOOLS",
    "AskNextSpec",
    "CiteRef",
    "ExplainerSpec",
    "GeneratorSection",
    "GeneratorSpec",
    "LanguagePanel",
    "LanguageSwitchSpec",
    "QuizSpec",
    "ReadingLevelSpec",
    "spec_component_labels",
    "spec_unit_refs",
]

LANG_PATTERN = r"^[a-z]{2,3}$"

UnitRef = Annotated[str, Field(pattern=UNIT_REF_PATTERN)]
ComponentLabel = Annotated[str, Field(pattern=COMPONENT_LABEL_PATTERN)]
SourceKey = Annotated[str, Field(min_length=1, max_length=40)]
Nodes = Annotated[list[Any], Field(min_length=1)]
Words = Annotated[str, Field(min_length=1, max_length=400)]
Grade = Literal["A", "B", "C", "D"]
Direction = Literal["ltr", "rtl"]


class QuoteCard(ContractModel):
    source: SourceKey
    byline: Words
    quote: Words | None = None
    quote_unit: UnitRef | None = None
    locator: Words
    keyed: bool = False

    @model_validator(mode="after")
    def _one_quote(self) -> Self:
        if (self.quote is None) == (self.quote_unit is None):
            raise ValueError("a quote card quotes either its own words or a unit, exactly one")
        return self


class ExplainerSpec(ContractModel):
    kicker: UnitRef
    title: UnitRef
    sentence: UnitRef
    keys: list[UnitRef] = Field(min_length=1, max_length=8)
    cards_label: Words
    cards: list[QuoteCard] = Field(min_length=1, max_length=4)


class CiteRef(ContractModel):
    key: Words
    sources: list[SourceKey] = Field(min_length=1)


class QuizChoice(ContractModel):
    term: Words
    right: bool
    sentence: Nodes


class QuizQuestion(ContractModel):
    before: str
    after: str
    cite: CiteRef
    choices: list[QuizChoice] = Field(min_length=2, max_length=6)

    @model_validator(mode="after")
    def _one_right_choice(self) -> Self:
        if sum(choice.right for choice in self.choices) != 1:
            raise ValueError("a quiz question has exactly one right choice")
        return self


class QuizSpec(ContractModel):
    title: UnitRef
    kicker: Words
    dek: UnitRef
    score: UnitRef
    status: UnitRef
    next_label: Words
    questions: list[QuizQuestion] = Field(min_length=1, max_length=12)


class AskNextSpec(ContractModel):
    craft: Annotated[str, Field(pattern=r"^[A-Za-z0-9-]+$")]
    action: Words
    questions: list[Words] = Field(min_length=1, max_length=12)


class GradeCount(ContractModel):
    grade: Grade
    count: int = Field(ge=0)


class Reliability(ContractModel):
    label: Words
    grades: list[GradeCount] = Field(min_length=1)


class PanelLink(ContractModel):
    text: Words
    href: Annotated[str, Field(pattern=r"^#[A-Za-z][\w-]*$")]


class ListenLabel(ContractModel):
    label: Words
    minutes: int = Field(ge=1)
    unit: Words


class PanelProvenance(ContractModel):
    items: list[Words] = Field(min_length=1)
    reliability: Reliability
    monograph: PanelLink
    answered: Words
    listen: ListenLabel


class PanelActions(ContractModel):
    save: Words
    cite: Words


class PanelSection(ContractModel):
    kind: Words
    title: UnitRef
    body: Nodes


class MarginPlate(ContractModel):
    src: Annotated[str, Field(pattern=r"^/[\w./-]+$")]
    width: int = Field(ge=1)
    height: int = Field(ge=1)
    alt: Words
    caption: Nodes
    credit: UnitRef


class LanguagePanel(ContractModel):
    lang: Annotated[str, Field(pattern=LANG_PATTERN)]
    direction: Direction
    provenance: PanelProvenance
    lede: Nodes
    actions: PanelActions
    section: PanelSection
    figure: ComponentLabel | None = None
    notes: list[UnitRef] = Field(default_factory=list)
    plate: MarginPlate | None = None


class LanguageOption(ContractModel):
    lang: Annotated[str, Field(pattern=LANG_PATTERN)]
    name: Words
    direction: Direction
    status: Words


class LanguageSwitchSpec(ContractModel):
    label: Words
    options: list[LanguageOption] = Field(min_length=2, max_length=6)
    english: UnitRef
    panels: list[LanguagePanel]

    @model_validator(mode="after")
    def _a_panel_for_each_other_language(self) -> Self:
        others = [option.lang for option in self.options[1:]]
        if [panel.lang for panel in self.panels] != others:
            raise ValueError("each language after the first has one panel, in the options' order")
        return self


class ReadingLevelSpec(ContractModel):
    level: Annotated[str, Field(pattern=r"^[a-z]+$")]
    summary: Words
    detail: Words
    title: UnitRef
    lede: UnitRef


class GeneratorSection(ContractModel):
    number: int = Field(ge=1)
    title: Words | None = None
    title_unit: UnitRef | None = None
    kind: Words
    text: Nodes | None = None
    text_unit: UnitRef | None = None
    media: list[ComponentLabel] = Field(default_factory=list)
    split: bool

    @model_validator(mode="after")
    def _own_words_or_a_unit(self) -> Self:
        if (self.title is None) == (self.title_unit is None) or (self.text is None) == (
            self.text_unit is None
        ):
            raise ValueError("a section's title and text are each its own words or a unit, exactly one")
        return self


class GeneratorStage(ContractModel):
    state: Words
    detail: Words


class GeneratorJob(ContractModel):
    title: Words
    state: Words


class GeneratorSpec(ContractModel):
    stage: GeneratorStage
    switch_label: Words
    switch_detail: Words
    replay: Words
    status: Words
    sections: list[GeneratorSection] = Field(min_length=1)
    film: ComponentLabel | None = None
    rail_title: UnitRef
    rail_detail: UnitRef
    jobs: list[GeneratorJob] = Field(default_factory=list)


SPEC_MODELS_TOOLS: Mapping[str, type[ContractModel]] = MappingProxyType(
    {
        "explainer": ExplainerSpec,
        "quiz": QuizSpec,
        "ask_next": AskNextSpec,
        "language_switch": LanguageSwitchSpec,
        "reading_level": ReadingLevelSpec,
        "generator": GeneratorSpec,
    }
)


def spec_unit_refs(spec: ContractModel) -> list[str]:
    return [
        value for value in _strings(spec.model_dump(mode="json")) if re.fullmatch(UNIT_REF_PATTERN, value)
    ]


def spec_component_labels(spec: ContractModel, labels: set[str]) -> list[str]:
    return [value for value in _strings(spec.model_dump(mode="json")) if value in labels]


def _strings(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [found for item in value for found in _strings(item)]
    if isinstance(value, dict):
        return [found for item in value.values() for found in _strings(item)]
    return []
