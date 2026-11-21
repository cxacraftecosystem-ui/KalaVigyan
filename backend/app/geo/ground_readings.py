from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping, Sequence

from pydantic import ValidationError

from app.core.errors import InvalidInput
from app.research.datasets import DatasetRef
from app.research.place_ground import GroundReading
from app.schemas.region import split_depth_or_period

from .datasets import region_dataset, value_grid
from .layers import LAYERS_BY_ID, stored_depth_or_period
from .records import DatasetRecord, ValueRecord

__all__ = ["READING_LAYERS", "cited_readings", "reading_codes"]

READING_LAYERS: tuple[tuple[str, str], ...] = (
    ("rainfall", "annual-precipitation"),
    ("soil", "clay-0-5cm"),
    ("soil", "soil-ph-0-5cm"),
    ("cover", "tree-cover-share"),
    ("cover", "cropland-share"),
)

Readings = dict[int, tuple[GroundReading, ...]]


def reading_codes() -> set[str]:
    return {LAYERS_BY_ID[layer].dataset_code for _, layer in READING_LAYERS}


def _usable(datasets: Mapping[str, DatasetRecord]) -> dict[str, DatasetRef]:
    usable: dict[str, DatasetRef] = {}
    for code, record in datasets.items():
        try:
            usable[code] = region_dataset(record)
        except ValidationError:
            continue
    return usable


def _reading(kind: str, row: ValueRecord, dataset: DatasetRecord) -> GroundReading | None:
    if row.value is None or not row.unit:
        return None
    try:
        grid = value_grid(row.resolution, dataset)
    except InvalidInput:
        return None
    depth, period = split_depth_or_period(row.depth_or_period, dataset.period or "")
    return GroundReading(
        reading=kind,
        dataset_code=row.dataset_code,
        variable=row.variable,
        depth=depth,
        period=period,
        stat=row.stat,
        value=row.value,
        unit=row.unit,
        resolution=grid,
    )


def _wanted(datasets: Mapping[str, DatasetRecord]) -> dict[tuple[str, str, str, str], str]:
    wanted: dict[tuple[str, str, str, str], str] = {}
    for kind, layer in READING_LAYERS:
        spec = LAYERS_BY_ID[layer]
        dataset = datasets.get(spec.dataset_code)
        stored = stored_depth_or_period(spec, dataset) if dataset is not None else None
        if stored is not None:
            wanted[(spec.dataset_code, spec.variable, stored, spec.stat)] = kind
    return wanted


def cited_readings(
    values: Sequence[ValueRecord], datasets: Mapping[str, DatasetRecord]
) -> tuple[Readings, list[DatasetRef]]:
    usable = _usable(datasets)
    wanted = _wanted({code: datasets[code] for code in usable})
    found: dict[int, list[GroundReading]] = defaultdict(list)
    for row in sorted(values, key=lambda r: (r.district_lgd, r.dataset_code, r.variable, r.stat)):
        match = wanted.get((row.dataset_code, row.variable, row.depth_or_period, row.stat))
        reading = _reading(match, row, datasets[row.dataset_code]) if match else None
        if reading is not None:
            found[row.district_lgd].append(reading)
    order = {layer: at for at, (_, layer) in enumerate(READING_LAYERS)}
    readings = {
        lgd: tuple(sorted(rows, key=lambda r: order.get(_layer_of(r), len(order))))
        for lgd, rows in found.items()
    }
    codes = sorted({reading.dataset_code for rows in readings.values() for reading in rows})
    return readings, [usable[code] for code in codes]


def _layer_of(reading: GroundReading) -> str:
    for _, layer in READING_LAYERS:
        spec = LAYERS_BY_ID[layer]
        if (spec.dataset_code, spec.variable) == (reading.dataset_code, reading.variable):
            return layer
    return ""
