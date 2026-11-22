from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date

from app.research.citations import SourceRef
from app.research.crafts import CraftRef
from app.schemas.region import DATASET_FACETS

__all__ = [
    "GEOLOGY_STAT",
    "GEOLOGY_UNIT",
    "GEOLOGY_VARIABLE",
    "LITHOLOGY_TWIN_PREFIX",
    "Coverage",
    "DatasetRecord",
    "LayerListing",
    "LayerRow",
    "LayerSpec",
    "LayerValues",
    "LocationRecord",
    "PlaceRecord",
    "RegionRecords",
    "SeriesTotals",
    "StateRecord",
    "StoredLayer",
    "ValueRecord",
]

GEOLOGY_VARIABLE = "lithology"
GEOLOGY_STAT = "SHARE"
GEOLOGY_UNIT = "fraction"
LITHOLOGY_TWIN_PREFIX = "lithology_"


@dataclass(frozen=True)
class DatasetRecord:
    code: str
    title: str
    publisher: str | None
    edition: str | None
    period: str | None
    native_resolution: str | None
    licence: str | None
    licence_url: str | None
    attribution: str | None
    citation: str | None
    url: str | None
    version: str | None = None
    crs: str | None = None
    redistributable: bool | None = None
    doi: str | None = None
    landing_url: str | None = None
    read_on: date | None = None
    sha256: str | None = None


@dataclass(frozen=True)
class ValueRecord:
    district_lgd: int
    dataset_code: str
    variable: str
    depth_or_period: str
    stat: str
    value: float | None
    value_text: str | None
    unit: str | None
    resolution: str | None
    method: str | None


@dataclass(frozen=True)
class SeriesTotals:
    state_lgd: int
    dataset_code: str
    variable: str
    depth_or_period: str
    stat: str
    unit: str | None
    value_text: str | None
    districts: int
    weighted_sum: float
    area: float
    total: float
    low: float
    high: float
    resolutions: tuple[str | None, ...]
    methods: tuple[str, ...]


@dataclass(frozen=True)
class Coverage:
    state_lgd: int
    dataset_code: str
    districts: int
    area: float


@dataclass(frozen=True)
class StateRecord:
    lgd: int
    name: str


@dataclass(frozen=True)
class LocationRecord:
    id: str
    precision: str
    state: StateRecord | None
    district_lgd: int | None
    district_name: str | None
    has_polygon: bool
    place_label: str | None
    source_id: str | None
    source_title: str | None
    level: str


@dataclass(frozen=True)
class PlaceRecord:
    scope: str
    state: StateRecord
    district_lgd: int | None
    district_name: str | None
    has_polygon: bool
    place_label: str
    basis_kind: str
    source_id: str | None
    basis_label: str
    level: str

    @property
    def values_from(self) -> str:
        return "DISTRICT" if self.scope == "DISTRICT" and self.has_polygon else "STATE"

    @property
    def inherits(self) -> bool:
        return self.scope == "DISTRICT" and not self.has_polygon


@dataclass(frozen=True)
class RegionRecords:
    craft: CraftRef
    places: tuple[PlaceRecord, ...]
    district_values: tuple[ValueRecord, ...]
    state_totals: tuple[SeriesTotals, ...]
    coverage: tuple[Coverage, ...]
    district_totals: Mapping[int, int]
    datasets: Mapping[str, DatasetRecord]
    sources: Mapping[str, SourceRef]


@dataclass(frozen=True)
class LayerSpec:
    id: str
    title: str
    dataset_code: str
    variable: str
    depth_or_period: str | None
    stat: str

    @property
    def facet(self) -> str:
        return DATASET_FACETS[self.dataset_code]


@dataclass(frozen=True)
class StoredLayer:
    spec: LayerSpec
    unit: str


@dataclass(frozen=True)
class LayerRow:
    district_lgd: int
    value: float
    resolution: str | None


@dataclass(frozen=True)
class LayerListing:
    layers: tuple[StoredLayer, ...]
    datasets: Mapping[str, DatasetRecord]
    boundary: DatasetRecord | None


@dataclass(frozen=True)
class LayerValues:
    layer: StoredLayer
    dataset: DatasetRecord
    rows: tuple[LayerRow, ...]
    boundary: DatasetRecord
