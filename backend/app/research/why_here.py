from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType
from typing import Literal, Self

from pydantic import Field, model_validator

from .base import ContractModel
from .citations import SourceRef
from .crafts import CraftRef
from .datasets import DatasetRef
from .place_ground import (
    GroundLayer,
    GroundPlace,
    MineralClass,
    reading_codes_problems,
)

__all__ = [
    "NOTE_READINGS",
    "SPEC_MODELS_WHY_HERE",
    "WHY_HERE_KIND",
    "CraftGround",
    "FrameBand",
    "FrameLabel",
    "FrameLine",
    "GroundDeposit",
    "GroundFrame",
    "GroundNote",
    "WhyHereSpec",
]

WHY_HERE_KIND = "why_here"
NOTE_READINGS = ("elevation", "river", "lake", "deposits", "rainfall", "soil", "cover")
NOTE_UNIT = r"^[a-z0-9][a-z0-9-]*$"
Point = tuple[float, float]


class FrameBand(ContractModel):
    low_m: int = Field(ge=0)
    rings: list[list[Point]]


class FrameLine(ContractModel):
    rank: int = Field(ge=0)
    points: list[Point] = Field(min_length=2)


class FrameLabel(ContractModel):
    text: str = Field(min_length=1)
    longitude: float
    latitude: float
    angle: float


class GroundFrame(ContractModel):
    west: float
    south: float
    east: float
    north: float
    bands: list[FrameBand]
    rivers: list[FrameLine]
    lakes: list[list[Point]]
    labels: list[FrameLabel]

    @model_validator(mode="after")
    def _a_box(self) -> Self:
        if self.west >= self.east or self.south >= self.north:
            raise ValueError("a frame runs west to east and south to north")
        return self

    def holds(self, longitude: float, latitude: float) -> bool:
        return self.west <= longitude <= self.east and self.south <= latitude <= self.north


class GroundDeposit(ContractModel):
    dep_id: int = Field(ge=1)
    name: str
    longitude: float
    latitude: float
    class_index: int = Field(ge=0)
    status: str = Field(min_length=1)
    commodities: str = Field(min_length=1)
    nearest_km: float = Field(ge=0)
    matched: bool


class CraftGround(ContractModel):
    schema_version: Literal[1]
    craft: CraftRef
    radius_km: int = Field(ge=1)
    places: list[GroundPlace] = Field(min_length=1)
    soil_materials: list[str]
    deposits: list[GroundDeposit]
    classes: list[MineralClass] = Field(min_length=1)
    frame: GroundFrame
    layers: list[GroundLayer] = Field(min_length=1)
    datasets: list[DatasetRef]
    sources: list[SourceRef]

    @model_validator(mode="after")
    def _every_value_cited(self) -> Self:
        problems = reading_codes_problems(self.datasets, [place.ground for place in self.places])
        if problems:
            raise ValueError("; ".join(problems))
        if [source.id for source in self.sources] != list(dict.fromkeys(p.source_id for p in self.places)):
            raise ValueError("the places cite each of their sources once, in order")
        if len({place.key for place in self.places}) != len(self.places):
            raise ValueError("each place is listed once")
        if any(not self.frame.holds(p.longitude, p.latitude) for p in self.places):
            raise ValueError("the frame holds every place")
        if any(deposit.class_index >= len(self.classes) for deposit in self.deposits):
            raise ValueError("every deposit belongs to a listed class")
        return self


class GroundNote(ContractModel):
    reading: Literal[*NOTE_READINGS]
    unit: str = Field(pattern=NOTE_UNIT)


class WhyHereSpec(ContractModel):
    ground: CraftGround
    notes: list[GroundNote]

    @model_validator(mode="after")
    def _each_note_once(self) -> Self:
        if len({note.unit for note in self.notes}) != len(self.notes):
            raise ValueError("each cited fact sits beside one reading")
        return self


SPEC_MODELS_WHY_HERE: Mapping[str, type[ContractModel]] = MappingProxyType({WHY_HERE_KIND: WhyHereSpec})
