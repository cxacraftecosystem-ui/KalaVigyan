from __future__ import annotations

import logging
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, replace
from types import MappingProxyType

from pydantic import ValidationError

from app.geo.climate import ClimateTrends
from app.geo.datasets import region_dataset, value_grid
from app.geo.records import DatasetRecord, ValueRecord
from app.research.blocks_climate import GroundwaterValue
from app.research.blocks_place import DistrictRef

__all__ = [
    "GROUNDWATER_DATASETS",
    "GROUNDWATER_VARIABLES",
    "GroundwaterReading",
    "groundwater_values",
    "with_groundwater",
]

logger = logging.getLogger(__name__)

GROUNDWATER_DATASETS = ("OGD_GW_RESOURCES_RAJASTHAN_2023",)


@dataclass(frozen=True)
class GroundwaterReading:
    stat: str
    unit: str


GROUNDWATER_VARIABLES: Mapping[str, GroundwaterReading] = MappingProxyType(
    {
        "annual_groundwater_recharge": GroundwaterReading("TOTAL", "ham"),
        "annual_extractable_groundwater": GroundwaterReading("TOTAL", "ham"),
        "annual_groundwater_extraction": GroundwaterReading("TOTAL", "ham"),
        "stage_of_groundwater_extraction": GroundwaterReading("SHARE", "%"),
    }
)

ValueKey = tuple[int, str, str, str, str]


def groundwater_values(
    districts: Sequence[DistrictRef], values: Iterable[ValueRecord], datasets: Mapping[str, DatasetRecord]
) -> tuple[GroundwaterValue, ...]:
    stored: dict[ValueKey, ValueRecord] = {
        (row.district_lgd, row.dataset_code, row.variable, row.depth_or_period, row.stat): row
        for row in values
    }
    found: list[GroundwaterValue] = []
    for district in districts:
        for code in GROUNDWATER_DATASETS:
            dataset = datasets.get(code)
            if dataset is None or not dataset.period:
                continue
            for variable, reading in GROUNDWATER_VARIABLES.items():
                row = stored.get((district.district_lgd, code, variable, dataset.period, reading.stat))
                value = _value(district, dataset, row, reading) if row is not None else None
                if value is not None:
                    found.append(value)
    return tuple(found)


def with_groundwater(
    climate: ClimateTrends,
    districts: Sequence[DistrictRef],
    values: Iterable[ValueRecord],
    datasets: Mapping[str, DatasetRecord],
) -> ClimateTrends:
    water = groundwater_values(districts, values, datasets)
    if not water:
        return climate
    cited = {dataset.code for dataset in climate.datasets}
    added = [code for code in dict.fromkeys(value.dataset_code for value in water) if code not in cited]
    shown = (*climate.datasets, *(region_dataset(datasets[code]) for code in added))
    return replace(climate, datasets=shown, groundwater=water)


def _value(
    district: DistrictRef, dataset: DatasetRecord, row: ValueRecord, reading: GroundwaterReading
) -> GroundwaterValue | None:
    if row.value is None:
        return None
    if row.unit != reading.unit:
        logger.warning(
            "the %s of district %s is stored in %s, not %s",
            row.variable,
            district.district_lgd,
            row.unit,
            reading.unit,
        )
        return None
    try:
        return GroundwaterValue(
            district=district,
            dataset_code=dataset.code,
            variable=row.variable,
            period=str(dataset.period),
            value=row.value,
            value_text=row.value_text,
            unit=row.unit,
            resolution=value_grid(row.resolution, dataset),
        )
    except ValidationError as refused:
        logger.warning("the %s of district %s is not shown: %s", row.variable, district.district_lgd, refused)
        return None
