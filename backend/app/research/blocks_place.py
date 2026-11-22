from __future__ import annotations

import uuid
from typing import Annotated, ClassVar, Literal, Self

from pydantic import Field, model_validator

from .base import ContractModel
from .blocks import (
    SENTENCE,
    BlockBase,
    ExplainerSentence,
    SentenceSpec,
    named_in,
    require_facts,
    stated_texts,
)
from .calendar import MONTHS, SEASONS, months_named, seasons_named
from .datasets import (
    BOUNDARY_CAPTION,
    BOUNDARY_DATASET_CODE,
    DATASET_CODE_PATTERN,
    DatasetRef,
    dataset_codes_problems,
)
from .rivers import RiverTrace
from .subject_keys import TermKey
from .terms import WIKIDATA_ID_PATTERN

__all__ = [
    "LAYER_KEY_PATTERN",
    "LAYER_VERSION_PATTERN",
    "DistrictRef",
    "MapLayerBlock",
    "MonthlyRain",
    "RegionStoryBlock",
    "RiverPath",
    "SeasonRow",
    "SeasonsBlock",
    "StoryStep",
    "SupplyLink",
    "SupplyMapBlock",
]

LAYER_KEY_PATTERN = r"^[a-z0-9]+(?:-[a-z0-9]+)*$"
LAYER_VERSION_PATTERN = r"^[0-9a-f]{64}$"
MAP_LAYER_DATASETS = 2

Season = Literal[*SEASONS]
LayerKey = Annotated[str, Field(pattern=LAYER_KEY_PATTERN, max_length=80)]
DistrictLgd = Annotated[int, Field(ge=1)]


class DistrictRef(ContractModel):
    district_lgd: DistrictLgd
    name: str = Field(min_length=1, max_length=200)
    state_name: str = Field(min_length=1, max_length=200)


class RiverPath(RiverTrace):
    name: str | None = Field(min_length=1, max_length=200)


class StoryStep(ContractModel):
    district_lgd: DistrictLgd | None
    sentence: ExplainerSentence


class RegionStoryBlock(BlockBase):
    SENTENCES: ClassVar[SentenceSpec] = (("steps", [(("sentence", SENTENCE),)]),)

    kind: Literal["region_story"]
    version: Literal[1]
    river: RiverPath | None
    districts: list[DistrictRef] = Field(min_length=1)
    steps: list[StoryStep] = Field(min_length=1)
    layers: list[LayerKey]
    datasets: list[DatasetRef] = Field(min_length=1)
    boundary_caption: str

    @model_validator(mode="after")
    def _a_cited_story_over_real_geometry(self) -> Self:
        require_facts(f"region story {self.id}", [step.sentence for step in self.steps])
        _require_caption(self.id, self.boundary_caption)
        drawn = [BOUNDARY_DATASET_CODE] + ([self.river.dataset_code] if self.river else [])
        problems = dataset_codes_problems(f"region story {self.id}", self.datasets, drawn)
        listed = [district.district_lgd for district in self.districts]
        if len(set(listed)) != len(listed) or len(set(self.layers)) != len(self.layers):
            problems.append(f"region story {self.id} lists each district and layer once")
        problems += _step_district_problems(self.id, self.districts, self.steps)
        if self.river is not None:
            problems += _river_problems(self.id, self.river, listed, self.steps)
        if problems:
            raise ValueError("; ".join(problems))
        return self

    def cites_datasets(self) -> bool:
        return bool(self.datasets)

    def shown_labels(self) -> list[str]:
        named = [self.river.name] if self.river and self.river.name else []
        return [*named, *(district.name for district in self.districts)]


class MapLayerBlock(BlockBase):
    kind: Literal["map_layer"]
    version: Literal[1]
    layer: LayerKey
    layer_version: str = Field(pattern=LAYER_VERSION_PATTERN)
    title: str = Field(min_length=1, max_length=120)
    datasets: list[DatasetRef] = Field(min_length=MAP_LAYER_DATASETS, max_length=MAP_LAYER_DATASETS)
    highlighted: list[DistrictLgd] = Field(min_length=1)
    boundary_caption: str

    @model_validator(mode="after")
    def _the_layer_over_the_boundary(self) -> Self:
        _require_caption(self.id, self.boundary_caption)
        layer_dataset, boundary = self.datasets
        if boundary.code != BOUNDARY_DATASET_CODE or layer_dataset.code == BOUNDARY_DATASET_CODE:
            raise ValueError(f"map layer {self.id} cites its own dataset row, then {BOUNDARY_DATASET_CODE}")
        if len(set(self.highlighted)) != len(self.highlighted):
            raise ValueError(f"map layer {self.id} highlights each district once")
        return self

    def cites_datasets(self) -> bool:
        return bool(self.datasets)

    def shown_labels(self) -> list[str]:
        return [self.title]


class SeasonRow(ContractModel):
    stage_id: uuid.UUID | None
    label: str = Field(min_length=1, max_length=120)
    months: list[int] = Field(max_length=MONTHS)
    season: Season | None
    sentence: ExplainerSentence

    @model_validator(mode="after")
    def _months_and_seasons_its_source_names(self) -> Self:
        if self.months != sorted(set(self.months)) or not all(1 <= m <= MONTHS for m in self.months):
            raise ValueError(f"season row {self.label!r} lists months 1-12 once each, in order")
        if not self.months and self.season is None and self.stage_id is None:
            raise ValueError(f"season row {self.label!r} is a stage or is placed by months or a season")
        texts = stated_texts(self.sentence)
        if not set(self.months) <= months_named(texts):
            raise ValueError(f"season row {self.label!r} shows months its sentence and quotes do not name")
        if self.season is not None and self.season not in seasons_named(texts):
            raise ValueError(f"season row {self.label!r} shows a season its sentence and quotes do not name")
        return self


class MonthlyRain(ContractModel):
    district: DistrictRef
    dataset_code: str = Field(pattern=DATASET_CODE_PATTERN, max_length=80)
    period: str = Field(min_length=1, max_length=80)
    millimetres: list[Annotated[float, Field(ge=0)]] = Field(min_length=MONTHS, max_length=MONTHS)


class SeasonsBlock(BlockBase):
    SENTENCES: ClassVar[SentenceSpec] = (("rows", [(("sentence", SENTENCE),)]),)

    kind: Literal["seasons"]
    version: Literal[1]
    rows: list[SeasonRow]
    rainfall: MonthlyRain | None
    datasets: list[DatasetRef]

    @model_validator(mode="after")
    def _cited_rows_or_rain_from_its_dataset(self) -> Self:
        if not self.rows and self.rainfall is None:
            raise ValueError(f"seasons {self.id} shows season rows, its district's rainfall or both")
        require_facts(f"seasons {self.id}", [row.sentence for row in self.rows])
        expected = [self.rainfall.dataset_code] if self.rainfall is not None else []
        if [dataset.code for dataset in self.datasets] != expected:
            raise ValueError(f"seasons {self.id} cites the rainfall's dataset row, and only it")
        return self

    def cites_datasets(self) -> bool:
        return bool(self.datasets)

    def shown_labels(self) -> list[str]:
        return [row.label for row in self.rows]


class SupplyLink(ContractModel):
    material: str = Field(min_length=1, max_length=300)
    material_id: uuid.UUID | None
    term_key: TermKey | None
    origin: str = Field(min_length=1, max_length=300)
    wikidata_id: str | None = Field(pattern=WIKIDATA_ID_PATTERN)
    latitude: float | None = Field(ge=-90, le=90)
    longitude: float | None = Field(ge=-180, le=180)
    sentence: ExplainerSentence

    @model_validator(mode="after")
    def _origin_as_stated_and_placed_from_wikidata(self) -> Self:
        placed = self.latitude is not None or self.longitude is not None
        if placed and (self.latitude is None or self.longitude is None or self.wikidata_id is None):
            raise ValueError(f"supply origin {self.origin!r} is placed only with Wikidata coordinates")
        if not named_in(self.origin, self.sentence):
            raise ValueError(f"supply origin {self.origin!r} is not what its sentence states")
        stored = self.material_id is not None or self.term_key is not None
        if not stored and not named_in(self.material, self.sentence):
            raise ValueError(f"supply material {self.material!r} is neither stored nor stated")
        return self


class SupplyMapBlock(BlockBase):
    SENTENCES: ClassVar[SentenceSpec] = (("links", [(("sentence", SENTENCE),)]),)

    kind: Literal["supply_map"]
    version: Literal[1]
    links: list[SupplyLink] = Field(min_length=1)

    @model_validator(mode="after")
    def _each_origin_of_each_material_once(self) -> Self:
        require_facts(f"supply map {self.id}", [link.sentence for link in self.links])
        pairs = [(link.material.casefold(), link.origin.casefold()) for link in self.links]
        if len(set(pairs)) != len(pairs):
            raise ValueError(f"supply map {self.id} lists each origin of a material once")
        return self

    def shown_labels(self) -> list[str]:
        return list(dict.fromkeys(text for link in self.links for text in (link.material, link.origin)))


def _require_caption(block_id: str, caption: str) -> None:
    if caption != BOUNDARY_CAPTION:
        raise ValueError(f"map {block_id} carries the boundary caption word for word")


def _step_district_problems(block_id: str, districts: list[DistrictRef], steps: list[StoryStep]) -> list[str]:
    names = {district.district_lgd: district.name for district in districts}
    placed = [step for step in steps if step.district_lgd is not None]
    if any(step.district_lgd not in names for step in placed):
        return [f"region story {block_id} narrates only districts it lists"]
    if any(not named_in(names[step.district_lgd], step.sentence) for step in placed):
        return [f"region story {block_id} places a step only in a district its sentence or quotes name"]
    return []


def _river_problems(block_id: str, river: RiverPath, listed: list[int], steps: list[StoryStep]) -> list[str]:
    problems = []
    if listed[: len(river.district_lgds)] != river.district_lgds:
        problems.append(f"region story {block_id} lists the river's districts first, in path order")
    if river.name is not None and not any(named_in(river.name, step.sentence) for step in steps):
        problems.append(f"region story {block_id} names the river only as a cited step states it")
    return problems
