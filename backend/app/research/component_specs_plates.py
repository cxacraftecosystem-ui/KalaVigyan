from __future__ import annotations

import datetime
from collections.abc import Mapping
from types import MappingProxyType
from typing import Literal, Self

from pydantic import Field, model_validator

from .base import ContractModel
from .component_specs_plates_media import (
    AiIllustrationSpec,
    AiVideoSpec,
    AudioPlayerSpec,
    ComicSpec,
    FilmSpec,
    VoiceSpec,
)
from .component_specs_plates_parts import (
    ClassName,
    ComponentLabel,
    DepictedMaterial,
    DomId,
    DrawingElement,
    HeldOrUnit,
    HeldText,
    Picture,
    UnitRef,
)

__all__ = [
    "PLATE_SETTINGS",
    "SPEC_MODELS_PLATES",
    "CreditsSpec",
    "LabelCardSpec",
    "PicturePlateSpec",
    "SpecimenPlateSpec",
    "SwatchCardsSpec",
    "SwatchPairSpec",
]

PLATE_SETTINGS = ("figure", "row", "pull", "opener", "masthead")
GRADES = ("A", "B", "C", "D")
SETTING_PARTS = ("row", "pull", "opener", "masthead")


class CaptionLine(ContractModel):
    unit: UnitRef
    look: bool = False


class PlateFigure(ContractModel):
    classes: list[ClassName] = Field(default_factory=list)
    crop: ClassName | None = None
    captions: list[CaptionLine] = Field(min_length=1)
    credit: UnitRef


class PlateRow(ContractModel):
    classes: list[ClassName] = Field(min_length=1)
    note: UnitRef


class PlatePull(ContractModel):
    classes: list[ClassName] = Field(min_length=1)
    box: ClassName
    quote: UnitRef
    attribution: HeldOrUnit


class ChapterOpener(ContractModel):
    chapter_no: UnitRef
    kicker: UnitRef
    title: UnitRef
    title_id: DomId
    dek: UnitRef
    credit: UnitRef


class GradeCount(ContractModel):
    grade: Literal[*GRADES]
    count: int = Field(ge=1)


class MastheadLabel(ContractModel):
    kicker: UnitRef
    title: UnitRef
    seal: DrawingElement
    registration: HeldOrUnit
    place: str = Field(min_length=1)
    sources: int = Field(ge=1)
    grades: list[GradeCount] = Field(min_length=1)
    curated: datetime.date

    @model_validator(mode="after")
    def _grades_count_the_sources(self) -> Self:
        if sum(grade.count for grade in self.grades) != self.sources:
            raise ValueError("The graded counts add up to the sources the label names")
        return self


class PicturePlateSpec(ContractModel):
    setting: Literal[*PLATE_SETTINGS]
    picture: Picture
    figure: PlateFigure | None = None
    row: PlateRow | None = None
    pull: PlatePull | None = None
    opener: ChapterOpener | None = None
    masthead: MastheadLabel | None = None

    @model_validator(mode="after")
    def _parts_of_its_setting(self) -> Self:
        if (self.figure is None) != (self.setting == "opener"):
            raise ValueError("Every setting but the chapter opener frames its picture as a plate figure")
        for part in SETTING_PARTS:
            if (getattr(self, part) is not None) != (self.setting == part):
                raise ValueError(f"The {part} part belongs to the {part} setting only")
        return self


class SpecimenReplay(ContractModel):
    label: str = Field(min_length=1)
    status_id: DomId
    status: UnitRef


class SpecimenPlateSpec(ContractModel):
    picture: Picture
    phase: ClassName
    kicker: UnitRef
    name: UnitRef
    name_id: DomId
    sentence: UnitRef
    replay: SpecimenReplay
    credit: UnitRef


class LabelFact(ContractModel):
    term: UnitRef
    value: UnitRef


class LabelCardSpec(ContractModel):
    variant: ClassName
    kicker: UnitRef
    seal: DrawingElement
    sentence: UnitRef
    inset: ComponentLabel | None = None
    facts: list[LabelFact] = Field(min_length=1)


class Swatch(ContractModel):
    dye: DepictedMaterial
    caption: UnitRef


class ColourCard(ContractModel):
    before: Swatch
    join: Literal["becomes", "or"]
    after: Swatch
    name: UnitRef
    agent: UnitRef
    text: UnitRef


class SwatchCardsSpec(ContractModel):
    chapter_no: UnitRef
    title: UnitRef
    title_id: DomId
    intro: UnitRef
    weave: DomId
    colours: list[ColourCard] = Field(min_length=1)


class PairSwatch(ContractModel):
    ground: DepictedMaterial
    motif: list[DrawingElement] = Field(min_length=1)
    label: str = Field(min_length=1)


class StageLink(ContractModel):
    stage: int = Field(ge=1)
    label: HeldText


class SwatchPairSpec(ContractModel):
    id: DomId
    wide: bool
    pair_class: ClassName
    description: str = Field(min_length=1)
    weave: DomId
    swatches: list[PairSwatch] = Field(min_length=2, max_length=2)
    when: UnitRef
    title: UnitRef
    texts: list[UnitRef] = Field(min_length=1)
    go: StageLink | None = None


class CreditLine(ContractModel):
    unit: UnitRef | None = None
    text: HeldText | None = None

    @model_validator(mode="after")
    def _a_unit_or_held_text(self) -> Self:
        if (self.unit is None) == (self.text is None):
            raise ValueError("A credit line is a unit or held text, not both or neither")
        return self


class CreditGroup(ContractModel):
    title: UnitRef
    list_class: ClassName | None = None
    lines: list[CreditLine] = Field(min_length=1)


class CreditsSpec(ContractModel):
    groups: list[CreditGroup] = Field(min_length=1)


SPEC_MODELS_PLATES: Mapping[str, type[ContractModel]] = MappingProxyType(
    {
        "picture_plate": PicturePlateSpec,
        "ai_illustration": AiIllustrationSpec,
        "specimen_plate": SpecimenPlateSpec,
        "label_card": LabelCardSpec,
        "swatch_cards": SwatchCardsSpec,
        "swatch_pair": SwatchPairSpec,
        "film": FilmSpec,
        "ai_video": AiVideoSpec,
        "comic": ComicSpec,
        "audio_player": AudioPlayerSpec,
        "voice": VoiceSpec,
        "credits": CreditsSpec,
    }
)
