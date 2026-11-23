import geopandas as gpd
import numpy as np
import pandas as pd
import pytest
import requests
from rasterio.crs import CRS
from rasterio.io import MemoryFile
from rasterio.transform import from_origin
from shapely.geometry import box

from geo_etl import raster, remote
from geo_etl.coverage import Coverage, coverage_of, covered_districts
from geo_etl.layers import (
    Measured,
    Options,
    chelsa,
    chirps,
    copdem,
    each_district,
    geology,
    hansen,
    soilgrids,
    worldcover,
)


def geotiff(rows: int, cols: int, value: int) -> bytes:
    with MemoryFile() as memory:
        transform = from_origin(0.0, rows * soilgrids.CELL, soilgrids.CELL, soilgrids.CELL)
        profile = {"driver": "GTiff", "height": rows, "width": cols, "count": 1, "dtype": "int16"}
        with memory.open(**profile, transform=transform) as dataset:
            dataset.write(np.full((rows, cols), value, dtype="int16"), 1)
        return bytes(memory.getbuffer())


def test_soilgrids_coverage_retries_a_tile_of_the_wrong_shape(monkeypatch, sleeps):
    bodies = [geotiff(2, 2, 1), geotiff(3, 2, 250)]

    def fake_get(url, **kwargs):
        made = requests.Response()
        made.status_code = 200
        made._content = bodies.pop(0)
        return made

    monkeypatch.setattr(soilgrids.requests, "get", fake_get)
    block = soilgrids.coverage("clay", "0-5cm", "mean", (0.0, 0.0, 500.0, 750.0))
    assert block.shape == (3, 2)
    assert (block == 250).all()
    assert sleeps == [5.0]


RASTER_LAYERS = {
    "soilgrids": soilgrids.run,
    "worldcover": worldcover.run,
    "hansen": hansen.run,
    "chelsa": chelsa.run,
    "chirps": chirps.run,
    "copdem": copdem.run,
    "glim": geology.run_glim,
}


def half_valid_grid(*args, **kwargs) -> raster.Grid:
    values = np.full((4, 4), np.nan, dtype="float32")
    values[:, :2] = 1.0
    return raster.Grid(values, from_origin(70.0, 24.0, 1.0, 1.0), CRS.from_epsg(4326))


def districts_beside_nodata() -> gpd.GeoDataFrame:
    return gpd.GeoDataFrame(
        {"districtLgd": [11, 12, 21], "stateLgd": [1, 1, 2], "districtName": ["valid", "nodata", "island"]},
        geometry=[box(70.2, 20.2, 71.8, 21.8), box(72.2, 20.2, 73.8, 21.8), box(72.2, 22.2, 73.8, 23.8)],
        crs="EPSG:4326",
    )


@pytest.fixture
def offline_reads(monkeypatch):
    monkeypatch.setattr(raster, "read", half_valid_grid)
    monkeypatch.setattr(soilgrids, "read", half_valid_grid)
    monkeypatch.setattr(chirps, "latest_year", lambda: 2025)
    monkeypatch.setattr(geology, "download", lambda url, target: target)


@pytest.mark.parametrize("key", list(RASTER_LAYERS))
def test_every_raster_layer_lists_districts_measured_without_valid_cells(key, offline_reads, tmp_path):
    options = Options(
        cache=tmp_path,
        soil_vars=("clay",),
        soil_depths=("0-5cm",),
        chelsa_bio=("bio1",),
        chelsa_months=False,
        climate_first_year=2025,
    )
    districts = districts_beside_nodata()
    result = RASTER_LAYERS[key](districts, options)
    assert result.failures == []
    assert covered_districts(result) == {11}
    assert result.districts_without_cells == [12, 21]
    assert coverage_of(districts, result) == Coverage(
        districts_without_values=[12, 21],
        districts_without_cells=[12, 21],
        unexpected_without_cells=[12, 21],
        silent_districts=[],
        lost_states=[],
    )


TILED_LAYERS = {"worldcover": worldcover.run, "hansen": hansen.run, "copdem": copdem.run}


def unreachable_east_of_72(urls, bounds, **kwargs) -> raster.Grid:
    if bounds[0] > 72.0:
        raise remote.Unreachable("tiles.test is unreachable: 503")
    return half_valid_grid()


@pytest.mark.parametrize("key", list(TILED_LAYERS))
def test_an_unreachable_tile_fails_its_district_and_every_later_one(key, monkeypatch, tmp_path):
    monkeypatch.setattr(raster, "read", unreachable_east_of_72)
    result = TILED_LAYERS[key](districts_beside_nodata(), Options(cache=tmp_path))
    assert covered_districts(result) == {11}
    assert result.failures == [
        {"step": key, "districtLgds": [12, 21], "error": "Unreachable: tiles.test is unreachable: 503"}
    ]
    assert result.districts_without_cells == []


def test_any_other_error_fails_only_its_own_district():
    measured: list[int] = []

    def measure(group):
        measured.append(int(group.iloc[0]["districtLgd"]))
        if measured[-1] == 12:
            raise ValueError("Mixed-type geometries not supported.")

    failures = each_district(districts_beside_nodata(), "copdem", measure)
    assert measured == [11, 12, 21]
    assert failures == [
        {"step": "copdem", "districtLgds": [12], "error": "ValueError: Mixed-type geometries not supported."}
    ]


def test_an_unreachable_chelsa_file_ends_the_shards_reads(monkeypatch, tmp_path):
    read: list[str] = []

    def stalled(urls, bounds, **kwargs):
        read.append(urls[0])
        raise remote.Unreachable(f"{urls[0]} is unreachable: read timed out")

    monkeypatch.setattr(raster, "read", stalled)
    options = Options(cache=tmp_path, chelsa_bio=("bio1", "bio12"), chelsa_months=True)
    result = chelsa.run(districts_beside_nodata(), options)
    assert read == [chelsa.bio_url("bio1")]
    assert [item["step"] for item in result.failures] == ["chelsa annual_mean_temperature 1981-2010"]
    assert result.failures[0]["districtLgds"] == [11, 12, 21]


def test_glim_writes_geology_only_for_the_district_with_cells(offline_reads, tmp_path):
    result = geology.run_glim(districts_beside_nodata(), Options(cache=tmp_path))
    assert list(result.geology["districtLgd"]) == [11]
    assert list(result.geology["lithology"]) == ["su"]
    assert result.geology["areaShare"].tolist() == pytest.approx([1.0])


def test_measured_lists_only_districts_without_cells_in_every_step_it_measured():
    measured = Measured()
    measured.add(pd.DataFrame({"districtLgd": [11, 12, 21], "pixels": [3.0, 0.0, 0.0]}))
    measured.add(pd.DataFrame({"districtLgd": [11, 12], "pixels": [3.0, 0.5]}))
    measured.add(pd.DataFrame({"districtLgd": [21], "pixels": [float("nan")]}))
    assert measured.without_cells() == [21]
