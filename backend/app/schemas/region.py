from __future__ import annotations

import re
from collections.abc import Sequence
from itertools import pairwise
from types import MappingProxyType
from typing import Literal, Self

from pydantic import Field, model_validator

from app.research.base import ContractModel
from app.research.crafts import CraftRef
from app.research.datasets import BOUNDARY_CAPTION, BOUNDARY_DATASET_CODE, INDIA_OUTLINE_CAPTION, DatasetRef
from app.research.stream import SourceRef
from app.research.vocabulary import EnvStat, EvidenceLevel

__all__ = [
    "AGGREGATIONS",
    "DATASET_FACETS",
    "DEPTH_PATTERN",
    "INHERITED_REASON",
    "LAYER_CLASS_MAX",
    "LAYER_ID_PATTERN",
    "MASTER_LIST_LABEL",
    "PLACE_BASES",
    "PLACE_SCOPES",
    "REGION_FACETS",
    "REGION_SCHEMA_VERSION",
    "STATE_AGGREGATIONS",
    "BoundaryNote",
    "CraftRegion",
    "LayerClass",
    "MapLayer",
    "MapLayerList",
    "MapLayerSummary",
    "PlaceBasis",
    "RegionFacet",
    "RegionPlace",
    "RegionValue",
    "basis_source_ids",
    "place_key",
    "split_depth_or_period",
]

REGION_SCHEMA_VERSION = 1
REGION_FACETS = ("SOIL", "CLIMATE", "WATER", "FOREST", "LAND_COVER", "TERRAIN", "GEOLOGY")
DATASET_FACETS = MappingProxyType(
    {
        "SOILGRIDS_2_0": "SOIL",
        "CHELSA_2_1_1981_2010": "CLIMATE",
        "CHIRPS_3_0": "CLIMATE",
        "GHCN_CAMS_T2M": "CLIMATE",
        "HYDRORIVERS_1_0": "WATER",
        "HANSEN_GFC_2025_V1_13": "FOREST",
        "ESA_WORLDCOVER_2021_V200": "LAND_COVER",
        "COPERNICUS_DEM_GLO90": "TERRAIN",
        "USGS_MRDS": "GEOLOGY",
        "GLIM_1_0_05DEG": "GEOLOGY",
    }
)
PLACE_SCOPES = ("DISTRICT", "STATE")
PLACE_BASES = ("CRAFT_LOCATION", "MASTER_LIST")
AGGREGATIONS = ("DISTRICT", "STATE_AREA_MEAN", "STATE_SUM", "STATE_MIN", "STATE_MAX")
STATE_AGGREGATIONS = MappingProxyType(
    {
        "DISTRICT_MEAN": "STATE_AREA_MEAN",
        "NORMAL": "STATE_AREA_MEAN",
        "SHARE": "STATE_AREA_MEAN",
        "DENSITY": "STATE_AREA_MEAN",
        "TOTAL": "STATE_SUM",
        "COUNT": "STATE_SUM",
        "DISTRICT_MIN": "STATE_MIN",
        "DISTRICT_MAX": "STATE_MAX",
    }
)
DEPTH_PATTERN = r"^\d+-\d+cm$"
INHERITED_REASON = "NO_DISTRICT_POLYGON"
MASTER_LIST_LABEL = "IIT Crafts Master List, 2026-10-20"
LAYER_ID_PATTERN = r"^[a-z0-9]+(?:-[a-z0-9]+)*$"
LAYER_CLASS_MAX = 5

RegionFacetName = Literal[*REGION_FACETS]
PlaceScope = Literal[*PLACE_SCOPES]
PlaceBasisKind = Literal[*PLACE_BASES]
Aggregation = Literal[*AGGREGATIONS]


class PlaceBasis(ContractModel):
    kind: PlaceBasisKind
    source_id: str | None
    label: str = Field(min_length=1, max_length=300)
    level: EvidenceLevel

    @model_validator(mode="after")
    def _a_location_cites_its_source(self) -> Self:
        if self.kind == "CRAFT_LOCATION" and not self.source_id:
            raise ValueError("a craft location is shown only with the source that places it")
        if self.kind == "MASTER_LIST" and (self.source_id is not None or self.label != MASTER_LIST_LABEL):
            raise ValueError(f"a state of practice cites {MASTER_LIST_LABEL!r}")
        return self


class RegionValue(ContractModel):
    dataset_code: str = Field(min_length=1, max_length=80)
    variable: str = Field(min_length=1, max_length=120)
    depth: str | None = Field(pattern=DEPTH_PATTERN)
    period: str = Field(min_length=1)
    stat: EnvStat
    aggregation: Aggregation
    value: float | None
    value_text: str | None
    unit: str
    resolution: str = Field(min_length=1)
    method: str | None
    district_count: int | None = Field(ge=1)
    district_total: int | None = Field(ge=1)

    @model_validator(mode="after")
    def _aggregation_matches_the_stat(self) -> Self:
        if self.value is None and self.value_text is None:
            raise ValueError("a region value has a number, a text or both")
        if self.aggregation == "DISTRICT":
            if self.district_count is not None or self.district_total is not None:
                raise ValueError("a district value carries no district counts")
            return self
        if STATE_AGGREGATIONS.get(self.stat) != self.aggregation:
            raise ValueError(f"{self.stat} is not aggregated to a state as {self.aggregation}")
        if self.district_count is None or self.district_total is None:
            raise ValueError("a state aggregate says how many districts it covers")
        if self.district_count > self.district_total:
            raise ValueError("a state aggregate covers at most the state's districts")
        return self


class RegionFacet(ContractModel):
    facet: RegionFacetName
    values: list[RegionValue] = Field(min_length=1)

    @model_validator(mode="after")
    def _values_belong_to_the_facet(self) -> Self:
        for value in self.values:
            if DATASET_FACETS.get(value.dataset_code) != self.facet:
                raise ValueError(f"{value.dataset_code} does not belong to {self.facet}")
        return self


class RegionPlace(ContractModel):
    key: str
    scope: PlaceScope
    state_lgd: int = Field(ge=1)
    state_name: str = Field(min_length=1)
    district_lgd: int | None = Field(ge=1)
    district_name: str | None
    place_label: str = Field(min_length=1, max_length=300)
    basis: PlaceBasis
    values_from: PlaceScope
    inherited_reason: str | None
    facets: list[RegionFacet]

    @model_validator(mode="after")
    def _scope_values_and_facets_agree(self) -> Self:
        if self.key != place_key(self.scope, self.state_lgd, self.district_lgd):
            raise ValueError(f"place {self.key} is keyed by its scope and LGD code")
        if (self.scope == "DISTRICT") != (self.district_lgd is not None and self.district_name is not None):
            raise ValueError("a district place names its district; a state place names none")
        if (self.scope, self.values_from) == ("STATE", "DISTRICT"):
            raise ValueError("a state place shows state aggregates")
        inherited = self.scope == "DISTRICT" and self.values_from == "STATE"
        if (self.inherited_reason == INHERITED_REASON) != inherited:
            raise ValueError("a district shows its state's values only when it has no polygon")
        _check_facets(self.facets, self.values_from)
        return self


class CraftRegion(ContractModel):
    schema_version: Literal[1]
    craft: CraftRef
    places: list[RegionPlace]
    datasets: list[DatasetRef]
    sources: list[SourceRef]

    @model_validator(mode="after")
    def _datasets_and_sources_are_the_cited_ones(self) -> Self:
        used = {value.dataset_code for place in self.places for f in place.facets for value in f.values}
        codes = [dataset.code for dataset in self.datasets]
        if codes != sorted(used):
            raise ValueError("datasets lists every cited dataset once, by code")
        if len({place.key for place in self.places}) != len(self.places):
            raise ValueError("each place appears once")
        if [source.id for source in self.sources] != basis_source_ids(self.places):
            raise ValueError("sources lists every place's source once, in the order of the places")
        return self


def basis_source_ids(places: Sequence[RegionPlace]) -> list[str]:
    ordered = {place.basis.source_id: None for place in places if place.basis.source_id}
    return list(ordered)


class BoundaryNote(ContractModel):
    caption: str
    dataset: DatasetRef

    @model_validator(mode="after")
    def _the_survey_of_india_caption(self) -> Self:
        if self.caption != BOUNDARY_CAPTION or self.dataset.code != BOUNDARY_DATASET_CODE:
            raise ValueError("the boundary note is the PLAN 8 caption over the district shapes dataset")
        return self


class MapLayerSummary(ContractModel):
    id: str = Field(pattern=LAYER_ID_PATTERN, max_length=80)
    facet: RegionFacetName
    title: str = Field(min_length=1, max_length=120)
    dataset_code: str = Field(min_length=1, max_length=80)
    variable: str = Field(min_length=1, max_length=120)
    depth: str | None = Field(pattern=DEPTH_PATTERN)
    period: str = Field(min_length=1)
    stat: EnvStat
    unit: str

    @model_validator(mode="after")
    def _layer_dataset_belongs_to_its_facet(self) -> Self:
        if DATASET_FACETS.get(self.dataset_code) != self.facet:
            raise ValueError(f"layer {self.id}: {self.dataset_code} does not belong to {self.facet}")
        return self


class MapLayerList(ContractModel):
    layers: list[MapLayerSummary]
    datasets: list[DatasetRef]
    boundary: BoundaryNote
    outline_caption: str

    @model_validator(mode="after")
    def _datasets_are_the_listed_ones(self) -> Self:
        if self.outline_caption != INDIA_OUTLINE_CAPTION:
            raise ValueError("the outline caption is the Survey of India line of the boundary caption")
        if [d.code for d in self.datasets] != sorted({layer.dataset_code for layer in self.layers}):
            raise ValueError("datasets lists every layer's dataset once, by code")
        if len({layer.id for layer in self.layers}) != len(self.layers):
            raise ValueError("each layer appears once")
        return self


class LayerClass(ContractModel):
    min: float
    max: float

    @model_validator(mode="after")
    def _ordered_bounds(self) -> Self:
        if self.min > self.max:
            raise ValueError("a class's min is at most its max")
        return self


class MapLayer(ContractModel):
    layer: MapLayerSummary
    dataset: DatasetRef
    resolution: str = Field(min_length=1)
    classes: list[LayerClass] = Field(min_length=1, max_length=LAYER_CLASS_MAX)
    values: dict[str, float] = Field(min_length=1)
    version: str = Field(pattern=r"^[0-9a-f]{64}$")
    boundary: BoundaryNote

    @model_validator(mode="after")
    def _classes_cover_every_value(self) -> Self:
        if self.dataset.code != self.layer.dataset_code:
            raise ValueError("a layer cites its own dataset")
        if any(not re.fullmatch(r"[1-9]\d*", key) for key in self.values):
            raise ValueError("values are keyed by district LGD code")
        if any(a.max != b.min for a, b in pairwise(self.classes)):
            raise ValueError("classes are contiguous and rising")
        low, high = self.classes[0].min, self.classes[-1].max
        if any(not low <= value <= high for value in self.values.values()):
            raise ValueError("every value falls in a class")
        return self


def place_key(scope: str, state_lgd: int, district_lgd: int | None) -> str:
    return f"district-{district_lgd}" if scope == "DISTRICT" else f"state-{state_lgd}"


def split_depth_or_period(depth_or_period: str, dataset_period: str) -> tuple[str | None, str]:
    text = depth_or_period.strip()
    if re.fullmatch(DEPTH_PATTERN, text):
        return text, dataset_period
    return None, text or dataset_period


def _check_facets(facets: Sequence[RegionFacet], values_from: str) -> None:
    names = [facet.facet for facet in facets]
    if names != [name for name in REGION_FACETS if name in names]:
        raise ValueError("facets appear once each, in REGION_FACETS order")
    for facet in facets:
        for value in facet.values:
            if (value.aggregation == "DISTRICT") != (values_from == "DISTRICT"):
                raise ValueError("a place's values are all district values or all state aggregates")
