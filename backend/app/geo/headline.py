from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from types import MappingProxyType

from app.geo.climate import P_VALUE_STAT, SLOPE_STAT, TREND_DATASETS
from app.geo.layers import MAP_LAYERS
from app.geo.records import (
    GEOLOGY_STAT,
    GEOLOGY_VARIABLE,
    LITHOLOGY_DATASET,
    DatasetRecord,
    SeriesTotals,
    ValueRecord,
)
from app.schemas.region import DATASET_FACETS, REGION_FACETS

__all__ = ["HEADLINE_SERIES", "HeadlineSeries", "headline_rows"]

SeriesKey = tuple[str, str, str | None, str]


@dataclass(frozen=True)
class HeadlineSeries:
    dataset_code: str
    variable: str
    depth_or_period: str | None
    stat: str

    def stored(self, dataset: DatasetRecord) -> SeriesKey:
        stored = dataset.period if self.depth_or_period is None else self.depth_or_period
        return (self.dataset_code, self.variable, stored, self.stat)


def _registry() -> tuple[HeadlineSeries, ...]:
    return tuple(
        HeadlineSeries(spec.dataset_code, spec.variable, spec.depth_or_period, spec.stat)
        for spec in MAP_LAYERS
    )


def _trends() -> tuple[HeadlineSeries, ...]:
    return tuple(
        HeadlineSeries(code, variable, None, stat)
        for variable, code in TREND_DATASETS.items()
        for stat in (SLOPE_STAT, P_VALUE_STAT)
    )


_LISTED = (*_registry(), *_trends(), HeadlineSeries(LITHOLOGY_DATASET, GEOLOGY_VARIABLE, "", GEOLOGY_STAT))
HEADLINE_SERIES: Mapping[str, tuple[HeadlineSeries, ...]] = MappingProxyType(
    {
        facet: tuple(series for series in _LISTED if DATASET_FACETS[series.dataset_code] == facet)
        for facet in REGION_FACETS
    }
)


def headline_rows[R: ValueRecord | SeriesTotals](
    rows: Iterable[R], datasets: Mapping[str, DatasetRecord]
) -> list[R]:
    wanted = {
        series.stored(datasets[series.dataset_code])
        for listed in HEADLINE_SERIES.values()
        for series in listed
        if series.dataset_code in datasets
    }
    return [row for row in rows if (row.dataset_code, row.variable, row.depth_or_period, row.stat) in wanted]
