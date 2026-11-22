from __future__ import annotations

import logging
import re
from collections import defaultdict
from collections.abc import Callable, Iterable, Mapping, Sequence
from types import MappingProxyType

from app.core.errors import InvalidInput
from app.geo.aggregation import state_aggregate
from app.geo.climate import MEAN_STAT, TREND_DATASETS
from app.geo.datasets import region_dataset, value_grid
from app.geo.headline import headline_rows
from app.geo.records import DatasetRecord, PlaceRecord, RegionRecords, SeriesTotals, ValueRecord
from app.research.citations import SourceRef
from app.research.vocabulary import ENV_STATS
from app.schemas.region import (
    DATASET_FACETS,
    INHERITED_REASON,
    REGION_FACETS,
    REGION_SCHEMA_VERSION,
    CraftRegion,
    PlaceBasis,
    RegionFacet,
    RegionPlace,
    RegionValue,
    basis_source_ids,
    place_key,
    split_depth_or_period,
)

__all__ = [
    "CLIMATE_QUANTITIES",
    "NORMAL_SOURCES",
    "craft_region",
    "district_value",
    "one_normal_per_quantity",
    "region_facets",
    "value_order",
]

logger = logging.getLogger(__name__)

GRID_SEPARATOR = "; "
CHELSA = "CHELSA_2_1_1981_2010"
RAINFALL_SOURCE = TREND_DATASETS["annual_precipitation"]
TEMPERATURE_SOURCE = TREND_DATASETS["annual_mean_temperature"]
CLIMATE_QUANTITIES: Mapping[tuple[str, str], str] = MappingProxyType(
    {
        (CHELSA, "annual_precipitation"): "annual rainfall",
        (RAINFALL_SOURCE, "annual_precipitation"): "annual rainfall",
        (CHELSA, "precipitation"): "monthly rainfall",
        (RAINFALL_SOURCE, "monthly_precipitation"): "monthly rainfall",
        (CHELSA, "annual_mean_temperature"): "annual temperature",
        (TEMPERATURE_SOURCE, "annual_mean_temperature"): "annual temperature",
    }
)
NORMAL_SOURCES: Mapping[str, str] = MappingProxyType(
    {
        "annual rainfall": RAINFALL_SOURCE,
        "monthly rainfall": RAINFALL_SOURCE,
        "annual temperature": TEMPERATURE_SOURCE,
    }
)
NORMAL_STATS = (MEAN_STAT, "DISTRICT_P10", "DISTRICT_P90")
NORMAL_PERIOD = re.compile(r"(\d{4})-(\d{4})(?:-(\d{2}))?")

NormalKey = tuple[str, str | None]


def craft_region(records: RegionRecords) -> CraftRegion:
    district_values = _by_key(_headline(records, records.district_values), lambda row: row.district_lgd)
    state_totals = _by_key(_headline(records, records.state_totals), lambda row: row.state_lgd)
    shown_states: dict[int, list[RegionValue]] = {}
    places: list[RegionPlace] = []
    for place in records.places:
        if place.values_from == "DISTRICT":
            rows = district_values.get(place.district_lgd, []) if place.district_lgd else []
            values = [district_value(row, _dataset(records, row.dataset_code)) for row in rows]
        else:
            lgd = place.state.lgd
            if lgd not in shown_states:
                shown_states[lgd] = [_state_value(records, series) for series in state_totals.get(lgd, [])]
            values = shown_states[lgd]
        places.append(_region_place(place, values))
    cited = sorted({value.dataset_code for place in places for f in place.facets for value in f.values})
    return CraftRegion(
        schema_version=REGION_SCHEMA_VERSION,
        craft=records.craft,
        places=places,
        datasets=[region_dataset(_dataset(records, code)) for code in cited],
        sources=_place_sources(records, places),
    )


def region_facets(values: Iterable[RegionValue]) -> list[RegionFacet]:
    grouped: dict[str, list[RegionValue]] = defaultdict(list)
    for value in one_normal_per_quantity(values):
        grouped[DATASET_FACETS[value.dataset_code]].append(value)
    return [
        RegionFacet(facet=facet, values=sorted(grouped[facet], key=value_order))
        for facet in REGION_FACETS
        if facet in grouped
    ]


def one_normal_per_quantity(values: Iterable[RegionValue]) -> list[RegionValue]:
    listed = list(values)
    keys = [_normal_key(value) for value in listed]
    preferred = {
        key
        for key, value in zip(keys, listed, strict=True)
        if key is not None and value.stat == MEAN_STAT and _from_preferred_source(key, value)
    }
    return [
        value
        for key, value in zip(keys, listed, strict=True)
        if key not in preferred or _from_preferred_source(key, value)
    ]


def _normal_key(value: RegionValue) -> NormalKey | None:
    quantity = CLIMATE_QUANTITIES.get((value.dataset_code, value.variable))
    period = NORMAL_PERIOD.fullmatch(value.period)
    if quantity is None or period is None or value.stat not in NORMAL_STATS:
        return None
    return quantity, period.group(3)


def _from_preferred_source(key: NormalKey, value: RegionValue) -> bool:
    return NORMAL_SOURCES[key[0]] == value.dataset_code


def value_order(value: RegionValue) -> tuple[str, str, int, int, str, int, str]:
    top = int(value.depth.split("-", 1)[0]) if value.depth else 0
    return (
        value.dataset_code,
        value.variable,
        0 if value.depth is None else 1,
        top,
        value.period,
        ENV_STATS.index(value.stat),
        value.value_text or "",
    )


def _place_sources(records: RegionRecords, places: Sequence[RegionPlace]) -> list[SourceRef]:
    order = basis_source_ids(places)
    missing = [source_id for source_id in order if source_id not in records.sources]
    if missing:
        raise InvalidInput(f"Place sources {', '.join(missing)} of {records.craft.slug} were not loaded")
    return [records.sources[source_id] for source_id in order]


def _region_place(place: PlaceRecord, values: Sequence[RegionValue]) -> RegionPlace:
    return RegionPlace(
        key=place_key(place.scope, place.state.lgd, place.district_lgd),
        scope=place.scope,
        state_lgd=place.state.lgd,
        state_name=place.state.name,
        district_lgd=place.district_lgd,
        district_name=place.district_name,
        place_label=place.place_label,
        basis=PlaceBasis(
            kind=place.basis_kind, source_id=place.source_id, label=place.basis_label, level=place.level
        ),
        values_from=place.values_from,
        inherited_reason=INHERITED_REASON if place.inherits else None,
        facets=region_facets(values),
    )


def district_value(row: ValueRecord, dataset: DatasetRecord) -> RegionValue:
    depth, period = split_depth_or_period(row.depth_or_period, dataset.period or "")
    return RegionValue(
        dataset_code=row.dataset_code,
        variable=row.variable,
        depth=depth,
        period=period,
        stat=row.stat,
        aggregation="DISTRICT",
        value=row.value,
        value_text=row.value_text,
        unit=_unit(row.unit, f"district {row.district_lgd}", row),
        resolution=value_grid(row.resolution, dataset),
        method=row.method,
        district_count=None,
        district_total=None,
    )


def _state_value(records: RegionRecords, series: SeriesTotals) -> RegionValue:
    dataset = _dataset(records, series.dataset_code)
    aggregate = state_aggregate(series)
    total = records.district_totals.get(series.state_lgd)
    if total is None:
        raise InvalidInput(f"state {series.state_lgd} has no district count")
    depth, period = split_depth_or_period(series.depth_or_period, dataset.period or "")
    grids = sorted({value_grid(resolution, dataset) for resolution in series.resolutions})
    return RegionValue(
        dataset_code=series.dataset_code,
        variable=series.variable,
        depth=depth,
        period=period,
        stat=series.stat,
        aggregation=aggregate.aggregation,
        value=aggregate.value,
        value_text=series.value_text,
        unit=_unit(series.unit, f"state {series.state_lgd}", series),
        resolution=GRID_SEPARATOR.join(grids),
        method=GRID_SEPARATOR.join(sorted(set(series.methods))) or None,
        district_count=aggregate.districts,
        district_total=total,
    )


def _unit(unit: str | None, where: str, row: ValueRecord | SeriesTotals) -> str:
    if unit is None:
        raise InvalidInput(f"{where}: {row.dataset_code}.{row.variable} has no unit")
    return unit


def _dataset(records: RegionRecords, code: str) -> DatasetRecord:
    dataset = records.datasets.get(code)
    if dataset is None:
        raise InvalidInput(f"a stored value cites dataset {code}, which has no EnvDataset row")
    return dataset


def _headline[R: ValueRecord | SeriesTotals](records: RegionRecords, rows: Iterable[R]) -> list[R]:
    mapped = _mapped(rows)
    for code in sorted({row.dataset_code for row in mapped}):
        _dataset(records, code)
    return headline_rows(mapped, records.datasets)


def _mapped[R: ValueRecord | SeriesTotals](rows: Iterable[R]) -> list[R]:
    kept: list[R] = []
    unmapped: set[str] = set()
    for row in rows:
        if row.dataset_code in DATASET_FACETS:
            kept.append(row)
        else:
            unmapped.add(row.dataset_code)
    for code in sorted(unmapped):
        logger.warning("dataset %s has no region facet; its values are left out", code)
    return kept


def _by_key[R](rows: Iterable[R], key: Callable[[R], int]) -> dict[int, list[R]]:
    grouped: dict[int, list[R]] = defaultdict(list)
    for row in rows:
        grouped[key(row)].append(row)
    return grouped
