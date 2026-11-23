from __future__ import annotations

from collections.abc import Mapping
from itertools import pairwise
from typing import Annotated, Literal, Protocol, Self

from pydantic import Field, model_validator

from app.models.rivers import STRAHLER_MAX

from .base import ContractModel

__all__ = [
    "HYDRORIVERS_DATASET_CODE",
    "MOUTH",
    "RIVER_BASIN_ROUTE",
    "RIVER_NAME_DATASET_CODES",
    "RIVER_REACHES_OBJECT",
    "STRAHLER_MAX",
    "Coordinate",
    "ReachTopology",
    "RiverReach",
    "RiverTrace",
    "trace_problems",
]

HYDRORIVERS_DATASET_CODE = "HYDRORIVERS_1_0"
RIVER_BASIN_ROUTE = "/api/rivers/{mainRiv}"
RIVER_NAME_DATASET_CODES = ("WIKIDATA_RIVER_NAMES", "OSM_RIVER_NAMES")
RIVER_REACHES_OBJECT = "reaches"
MOUTH = 0

Longitude = Annotated[float, Field(ge=-180, le=180)]
Latitude = Annotated[float, Field(ge=-90, le=90)]
Coordinate = tuple[Longitude, Latitude]
ReachId = Annotated[int, Field(ge=1)]


class RiverReach(ContractModel):
    hyriv_id: ReachId
    next_down: int = Field(ge=MOUTH)
    main_riv: ReachId
    ord_stra: int = Field(ge=1, le=STRAHLER_MAX)
    upland_skm: float = Field(ge=0)
    dis_av_cms: float = Field(ge=0)
    length_km: float = Field(gt=0)
    geometry: list[Coordinate] = Field(min_length=2)

    @model_validator(mode="after")
    def _flows_on_or_ends_its_river(self) -> Self:
        if self.next_down == self.hyriv_id:
            raise ValueError(f"reach {self.hyriv_id} never flows into itself")
        if (self.next_down == MOUTH) != (self.hyriv_id == self.main_riv):
            raise ValueError(f"reach {self.hyriv_id} ends its river exactly when it is the river's outlet")
        return self


class ReachTopology(Protocol):
    @property
    def hyriv_id(self) -> int: ...

    @property
    def next_down(self) -> int: ...

    @property
    def main_riv(self) -> int: ...


class RiverTrace(ContractModel):
    dataset_code: Literal["HYDRORIVERS_1_0"]
    main_riv: ReachId
    reach_ids: list[ReachId] = Field(min_length=1)
    district_lgds: list[Annotated[int, Field(ge=1)]]

    @model_validator(mode="after")
    def _source_to_mouth_once_each(self) -> Self:
        if len(set(self.reach_ids)) != len(self.reach_ids) or self.reach_ids[-1] != self.main_riv:
            raise ValueError(f"river {self.main_riv} lists each reach once, from its source to its outlet")
        if len(set(self.district_lgds)) != len(self.district_lgds):
            raise ValueError(f"river {self.main_riv} lists each district it reaches once, in path order")
        return self


def trace_problems(trace: RiverTrace, reaches: Mapping[int, ReachTopology]) -> list[str]:
    problems = [f"reach {rid} is not stored" for rid in trace.reach_ids if rid not in reaches]
    if problems:
        return problems
    path = [reaches[rid] for rid in trace.reach_ids]
    problems += [
        f"reach {reach.hyriv_id} belongs to river {reach.main_riv}, not {trace.main_riv}"
        for reach in path
        if reach.main_riv != trace.main_riv
    ]
    problems += [
        f"reach {here.hyriv_id} flows into {here.next_down}, not {there.hyriv_id}"
        for here, there in pairwise(path)
        if here.next_down != there.hyriv_id
    ]
    headwater = trace.reach_ids[0]
    if any(reach.next_down == headwater for reach in reaches.values()):
        problems.append(f"reach {headwater} has a reach upstream, so the path does not start at a source")
    return problems
