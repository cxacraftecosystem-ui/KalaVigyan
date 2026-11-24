from __future__ import annotations

from typing import Any

import pytest

from maplayers.sources import BREAKS

numpy = pytest.importorskip("numpy")
shapely = pytest.importorskip("shapely")
transform = pytest.importorskip("rasterio.transform")
relief = pytest.importorskip("maplayers.relief")
layers = pytest.importorskip("app.geo.ground_layers")
measure = pytest.importorskip("app.geo.ground_measure")

CELL = 1 / 60
WEST, NORTH = 77.0, 31.0
SIDE = 9
VALLEY_COLUMN = 4
VALLEY_FLOOR_M = 1200.0
RIDGE_M = 3000.0
RING_POINTS = 3


def valley() -> Any:
    values = numpy.full((SIDE, SIDE), RIDGE_M, dtype="float32")
    values[:, VALLEY_COLUMN] = VALLEY_FLOOR_M
    return relief.Grid(values, transform.from_origin(WEST, NORTH, CELL, CELL))


def measured(bands: list[dict[str, Any]], point: tuple[float, float]) -> tuple[int | None, int | None]:
    read = [
        layers.Band(
            int(band["min"]),
            tuple(
                layers.line_of(ring)
                for text in band["rings"]
                for ring in layers.decode_records(text)
                if len(ring) >= RING_POINTS
            ),
        )
        for band in bands
    ]
    return measure.elevation_band(point, read, BREAKS)


def test_a_valley_floor_one_cell_wide_is_measured_at_its_own_height_not_its_ridges() -> None:
    bands = relief.relief_bands(valley(), shapely.box(76.0, 30.0, 78.0, 32.0))
    middle_row = NORTH - (SIDE / 2) * CELL
    floor = (WEST + (VALLEY_COLUMN + 0.5) * CELL, middle_row)
    ridge = (WEST + 1.5 * CELL, middle_row)
    assert [band["min"] for band in bands] == list(BREAKS)
    assert measured(bands, floor) == (1000, 2000)
    assert measured(bands, ridge) == (2000, 4000)
