from __future__ import annotations

from typing import Annotated, Literal, Self

from pydantic import Field, model_validator

from .base import ContractModel
from .datasets import DatasetRef
from .vocabulary import EnvStat, PlaceRole

__all__ = [
    "DEPOSIT_RADIUS_KM",
    "GROUND_LAYERS",
    "GROUND_SCHEMA_VERSION",
    "PLACE_PRECISIONS",
    "READING_KINDS",
    "Elevation",
    "GroundAt",
    "GroundLayer",
    "GroundPlace",
    "GroundReading",
    "Latitude",
    "Longitude",
    "MapPlaceGround",
    "MaterialDeposits",
    "MineralClass",
    "Tally",
    "Water",
    "reading_codes_problems",
]

GROUND_SCHEMA_VERSION = 1
DEPOSIT_RADIUS_KM = 50
GROUND_LAYERS = ("ETOPO1", "NE_RIVERS", "NE_LAKES", "USGS_MRDS")
PLACE_PRECISIONS = ("POINT", "DISTRICT")
READING_KINDS = ("rainfall", "soil", "cover")
Longitude = Annotated[float, Field(ge=-180, le=180)]
Latitude = Annotated[float, Field(ge=-90, le=90)]


class GroundLayer(ContractModel):
    key: Literal[*GROUND_LAYERS]
    title: str = Field(min_length=1)
    publisher: str = Field(min_length=1)
    edition: str = Field(min_length=1)
    url: str = Field(min_length=1)
    licence: str = Field(min_length=1)
    citation: str | None


class MineralClass(ContractModel):
    id: str = Field(min_length=1)
    label: str = Field(min_length=1)


class Elevation(ContractModel):
    low_m: int | None = Field(ge=0)
    high_m: int | None = Field(ge=1)

    @model_validator(mode="after")
    def _a_band_between_two_breaks(self) -> Self:
        if self.low_m is None and self.high_m is None:
            raise ValueError("an elevation band has at least one bound")
        if self.low_m is not None and self.high_m is not None and self.low_m >= self.high_m:
            raise ValueError("an elevation band rises from its low bound to its high one")
        return self


class Water(ContractModel):
    distance_km: float = Field(ge=0)
    scale_rank: int | None = Field(ge=0)
    longitude: Longitude
    latitude: Latitude


class Tally(ContractModel):
    key: str = Field(min_length=1)
    label: str = Field(min_length=1)
    count: int = Field(ge=1)


class GroundReading(ContractModel):
    reading: Literal[*READING_KINDS]
    dataset_code: str = Field(min_length=1, max_length=80)
    variable: str = Field(min_length=1, max_length=120)
    depth: str | None
    period: str = Field(min_length=1)
    stat: EnvStat
    value: float
    unit: str
    resolution: str = Field(min_length=1)


class GroundAt(ContractModel):
    elevation: Elevation
    river: Water | None
    lake: Water | None
    deposit_classes: list[Tally]
    commodities: list[Tally]
    readings: list[GroundReading]

    @model_validator(mode="after")
    def _counts_agree(self) -> Self:
        classes = sum(tally.count for tally in self.deposit_classes)
        if self.commodities and not classes:
            raise ValueError("commodities are counted only among the deposits within the radius")
        if len({tally.key for tally in self.deposit_classes}) != len(self.deposit_classes):
            raise ValueError("each deposit class is counted once")
        if len({(r.dataset_code, r.variable, r.stat) for r in self.readings}) != len(self.readings):
            raise ValueError("each district reading is listed once")
        return self

    @property
    def deposit_total(self) -> int:
        return sum(tally.count for tally in self.deposit_classes)


class MaterialDeposits(ContractModel):
    material: str = Field(min_length=1, max_length=300)
    commodities: list[str] = Field(min_length=1)
    count: int = Field(ge=1)
    nearest_km: float = Field(ge=0)


class GroundPlace(ContractModel):
    key: str = Field(min_length=1)
    name: str = Field(min_length=1, max_length=300)
    roles: list[PlaceRole]
    precision: Literal[*PLACE_PRECISIONS]
    district: str | None
    state: str | None
    longitude: Longitude
    latitude: Latitude
    source_id: str = Field(min_length=1)
    ground: GroundAt
    materials: list[MaterialDeposits]

    @model_validator(mode="after")
    def _materials_within_the_radius(self) -> Self:
        if sum(material.count for material in self.materials) and not self.ground.deposit_total:
            raise ValueError(f"{self.name} matches materials only to deposits within the radius")
        if len(set(self.roles)) != len(self.roles):
            raise ValueError(f"{self.name} names each role once")
        return self


class MapPlaceGround(ContractModel):
    schema_version: Literal[1]
    district: str | None
    longitude: Longitude
    latitude: Latitude
    radius_km: int = Field(ge=1)
    ground: GroundAt
    classes: list[MineralClass] = Field(min_length=1)
    layers: list[GroundLayer] = Field(min_length=1)
    datasets: list[DatasetRef]

    @model_validator(mode="after")
    def _cites_every_reading(self) -> Self:
        problems = reading_codes_problems(self.datasets, [self.ground])
        if problems:
            raise ValueError("; ".join(problems))
        return self


def reading_codes_problems(datasets: list[DatasetRef], grounds: list[GroundAt]) -> list[str]:
    codes = [dataset.code for dataset in datasets]
    used = sorted({reading.dataset_code for ground in grounds for reading in ground.readings})
    if codes != used:
        return [f"the district readings cite {', '.join(used) or 'no dataset'}, each once, by code"]
    return []
