from __future__ import annotations

import datetime
from typing import Literal, Self

from pydantic import Field, model_validator

from .base import ContractModel
from .component_specs_plates_parts import (
    ArtFrame,
    ClassName,
    DomId,
    DrawingElement,
    FileName,
    HeldOrUnit,
    HeldText,
    UnitRef,
    ViewBox,
)

__all__ = [
    "AiIllustrationSpec",
    "AiVideoSpec",
    "AudioPlayerSpec",
    "ComicSpec",
    "FilmSpec",
    "VoiceSpec",
]

VOICE_SETTINGS = ("testimony", "coda")


class AiIllustrationSpec(ContractModel):
    section: int = Field(ge=1)
    art: ArtFrame
    subject: str = Field(min_length=1)
    sentences: list[int] = Field(min_length=1)
    made: datetime.date
    download_name: FileName


class Playback(ContractModel):
    duration_ms: int = Field(ge=1)
    step_ms: int = Field(ge=1)
    rest_ms: int = Field(ge=0)

    @model_validator(mode="after")
    def _rests_within_its_length(self) -> Self:
        if self.rest_ms > self.duration_ms:
            raise ValueError("A player rests within its length")
        return self


class AiVideoSpec(ContractModel):
    section: int = Field(ge=1)
    art: DrawingElement
    phase: UnitRef
    playback: Playback
    caption: HeldText
    made: datetime.date
    download_key: str = Field(min_length=1)
    download_name: FileName


class FilmScene(ContractModel):
    art: ArtFrame
    title: str = Field(min_length=1)
    field: str = Field(min_length=1)
    forming: bool = False


class FilmSpec(ContractModel):
    title: UnitRef
    meta: UnitRef
    scene_label: UnitRef
    subtitle: UnitRef
    scenes: list[FilmScene] = Field(min_length=1)
    playback: Playback
    tags: list[str] = Field(min_length=1)
    note: str = Field(min_length=1)
    download_name: FileName
    subtitles_name: FileName


class ComicPanel(ContractModel):
    layout: ClassName | None = None
    caption: HeldOrUnit
    art: DrawingElement
    tag: str = Field(min_length=1)


class ComicSpec(ContractModel):
    label: str = Field(min_length=1)
    panels: list[ComicPanel] = Field(min_length=1)


class AudioPlayerSpec(ContractModel):
    title: UnitRef
    description: UnitRef
    action: str = Field(min_length=1)
    minutes: int = Field(ge=1)
    player_id: DomId


class VoiceEcho(ContractModel):
    quote: UnitRef
    attribution: HeldOrUnit


class VoiceTestimony(ContractModel):
    kicker: UnitRef
    kicker_id: DomId
    evidence: str = Field(min_length=1)
    quote: UnitRef
    credit: UnitRef
    meta: UnitRef
    echo: VoiceEcho | None = None


class VoiceCoda(ContractModel):
    label: str = Field(min_length=1)
    view_box: ViewBox
    tile: DomId
    weave: DomId
    kicker: UnitRef
    quote: UnitRef
    caption: UnitRef
    note: UnitRef


class VoiceSpec(ContractModel):
    setting: Literal[*VOICE_SETTINGS]
    testimony: VoiceTestimony | None = None
    coda: VoiceCoda | None = None

    @model_validator(mode="after")
    def _parts_of_its_setting(self) -> Self:
        if (self.testimony is not None) != (self.setting == "testimony"):
            raise ValueError("A testimony voice has its testimony part and no other")
        if (self.coda is not None) != (self.setting == "coda"):
            raise ValueError("A coda voice has its coda part and no other")
        return self
