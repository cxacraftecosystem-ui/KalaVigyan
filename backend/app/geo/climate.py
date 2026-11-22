from __future__ import annotations

import logging
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from types import MappingProxyType

from pydantic import ValidationError

from app.geo.datasets import region_dataset, value_grid
from app.geo.records import DatasetRecord, ValueRecord
from app.research.blocks_climate import TREND_SIGNIFICANCE, TREND_UNITS, ClimateTrend, GroundwaterValue
from app.research.blocks_place import DistrictRef
from app.research.datasets import DatasetRef

__all__ = [
    "MEAN_STAT",
    "P_VALUE_STAT",
    "P_VALUE_UNIT",
    "SLOPE_STAT",
    "TREND_DATASETS",
    "TREND_STATS",
    "ClimateTrends",
    "climate_trends",
]

logger = logging.getLogger(__name__)

TREND_DATASETS: Mapping[str, str] = MappingProxyType(
    {"annual_precipitation": "CHIRPS_3_0", "annual_mean_temperature": "GHCN_CAMS_T2M"}
)
MEAN_STAT = "NORMAL"
SLOPE_STAT = "TREND_PER_DECADE"
P_VALUE_STAT = "TREND_P_VALUE"
TREND_STATS = (MEAN_STAT, SLOPE_STAT, P_VALUE_STAT)
P_VALUE_UNIT = "p-value"

ValueKey = tuple[int, str, str, str, str]


@dataclass(frozen=True)
class ClimateTrends:
    trends: tuple[ClimateTrend, ...] = ()
    datasets: tuple[DatasetRef, ...] = ()
    groundwater: tuple[GroundwaterValue, ...] = ()


def climate_trends(
    districts: Sequence[DistrictRef], values: Iterable[ValueRecord], datasets: Mapping[str, DatasetRecord]
) -> ClimateTrends:
    stored = {_key(row): row for row in values}
    trends: list[ClimateTrend] = []
    for district in districts:
        for variable, code in TREND_DATASETS.items():
            dataset = datasets.get(code)
            trend = _trend(district, variable, dataset, stored) if dataset and dataset.period else None
            if trend is not None:
                trends.append(trend)
    used = dict.fromkeys(trend.dataset_code for trend in trends)
    return ClimateTrends(tuple(trends), tuple(region_dataset(datasets[code]) for code in used))


def _key(row: ValueRecord) -> ValueKey:
    return row.district_lgd, row.dataset_code, row.variable, row.depth_or_period, row.stat


def _trend(
    district: DistrictRef, variable: str, dataset: DatasetRecord, stored: Mapping[ValueKey, ValueRecord]
) -> ClimateTrend | None:
    period = str(dataset.period)
    rows = [stored.get((district.district_lgd, dataset.code, variable, period, stat)) for stat in TREND_STATS]
    mean, slope, p_value = rows
    if mean is None or slope is None or p_value is None:
        return None
    mean_unit, slope_unit = TREND_UNITS[variable]
    if (mean.unit, slope.unit, p_value.unit) != (mean_unit, slope_unit, P_VALUE_UNIT):
        logger.warning(
            "the %s trend of district %s is stored in other units", variable, district.district_lgd
        )
        return None
    if mean.value is None or slope.value is None or p_value.value is None:
        return None
    try:
        return ClimateTrend(
            district=district,
            variable=variable,
            dataset_code=dataset.code,
            period=period,
            resolution=value_grid(slope.resolution, dataset),
            mean=mean.value,
            mean_unit=mean_unit,
            slope_per_decade=slope.value,
            slope_unit=slope_unit,
            p_value=p_value.value,
            significant=p_value.value < TREND_SIGNIFICANCE,
        )
    except ValidationError as refused:
        logger.warning(
            "the %s trend of district %s is not shown: %s", variable, district.district_lgd, refused
        )
        return None
