import threading

import geopandas as gpd
import numpy as np
import pytest
import rasterio
from rasterio.crs import CRS
from rasterio.transform import from_origin
from shapely.geometry import box
from test_chirps import serve

from geo_etl import raster, remote
from geo_etl.districts import load_districts

WEST_TILE = "https://tiles.test/west.tif"
EAST_TILE = "https://tiles.test/east.tif"
BOTH = (0.0, 0.0, 4.0, 2.0)


def tile(path, west: float, value: float) -> str:
    profile = {"driver": "GTiff", "height": 2, "width": 2, "count": 1, "dtype": "float32", "crs": "EPSG:4326"}
    with rasterio.open(path, "w", **profile, transform=from_origin(west, 2.0, 1.0, 1.0)) as dataset:
        dataset.write(np.full((2, 2), value, dtype="float32"), 1)
    return str(path)


@pytest.fixture
def two_tiles(tmp_path, monkeypatch) -> dict[str, str]:
    local = {WEST_TILE: tile(tmp_path / "west.tif", 0.0, 7.0), EAST_TILE: tile(tmp_path / "east.tif", 2.0, 9.0)}
    monkeypatch.setattr(raster, "vsicurl", lambda location: local.get(location, location))
    return local


def test_read_mosaics_local_files_without_probing_them(two_tiles, monkeypatch):
    def no_network(*args, **kwargs):
        raise AssertionError("a local file was probed over HTTP")

    monkeypatch.setattr(remote.requests, "request", no_network)
    grid = raster.read([two_tiles[WEST_TILE], two_tiles[EAST_TILE]], BOTH)
    assert grid.values.tolist() == [[7.0, 7.0, 9.0, 9.0], [7.0, 7.0, 9.0, 9.0]]


def test_a_tile_that_answers_404_is_left_out_of_the_mosaic(two_tiles, monkeypatch, sleeps):
    server = serve(monkeypatch, {("HEAD", WEST_TILE): [200], ("HEAD", EAST_TILE): [404]})
    grid = raster.read([WEST_TILE, EAST_TILE], BOTH)
    assert server.calls == [("HEAD", WEST_TILE), ("HEAD", EAST_TILE)]
    assert grid.values[:, :2].tolist() == [[7.0, 7.0], [7.0, 7.0]]
    assert np.isnan(grid.values[:, 2:]).all()


def test_no_tile_that_exists_reads_as_none(monkeypatch, sleeps):
    serve(monkeypatch, {("HEAD", WEST_TILE): [404], ("HEAD", EAST_TILE): [410]})
    assert raster.read([WEST_TILE, EAST_TILE], BOTH) is None


def test_a_tile_that_answers_neither_200_nor_404_fails_the_read(two_tiles, monkeypatch, sleeps):
    serve(monkeypatch, {("HEAD", WEST_TILE): [200], ("HEAD", EAST_TILE): [503]})
    with pytest.raises(remote.Unreachable, match=r"east\.tif is unreachable: 503"):
        raster.read([WEST_TILE, EAST_TILE], BOTH)
    assert sleeps == [5.0, 10.0, 15.0]


def test_a_read_past_its_deadline_fails_as_unreachable(two_tiles, monkeypatch):
    released = threading.Event()

    def stalled_open(*args, **kwargs):
        released.wait(5.0)
        raise RuntimeError("released")

    monkeypatch.setattr(remote, "FILE_DEADLINE_S", 0.05)
    monkeypatch.setattr(raster.rasterio, "open", stalled_open)
    try:
        with pytest.raises(remote.Unreachable, match=r"2 file\(s\) from .*west\.tif not read within 0\.1 s"):
            raster.read([two_tiles[WEST_TILE], two_tiles[EAST_TILE]], BOTH)
    finally:
        released.set()


def grid_of(values: np.ndarray) -> raster.Grid:
    rows, _ = values.shape
    return raster.Grid(values.astype("float32"), from_origin(0, rows, 1, 1), CRS.from_epsg(3857))


def zone(*bounds: float) -> gpd.GeoDataFrame:
    return gpd.GeoDataFrame({"districtLgd": [1]}, geometry=[box(*bounds)], crs="EPSG:3857")


def test_weighted_quantile_follows_weights_on_ties():
    values = np.r_[np.zeros(95), np.full(5, 20.0)]
    weights = np.ones(100)
    assert raster.weighted_quantile(values, weights, 0.1) == 0.0
    assert raster.weighted_quantile(values, weights, 0.9) == 0.0
    assert raster.weighted_quantile(values, weights, 0.96) == 20.0


def test_weighted_quantile_ignores_nan_and_zero_weight():
    values = np.array([np.nan, 1.0, 2.0, 100.0])
    weights = np.array([5.0, 1.0, 1.0, 0.0])
    assert raster.weighted_quantile(values, weights, 0.9) == 2.0
    assert np.isnan(raster.weighted_quantile(np.array([np.nan]), np.array([1.0]), 0.5))


def test_zonal_quantiles_bracket_the_mean_on_tied_data():
    values = np.zeros((10, 10))
    values[0, :5] = 20
    table = raster.zonal(grid_of(values), zone(0, 0, 10, 10), raster.continuous_ops(grid_of(values)))
    record = table.iloc[0]
    assert raster.CELL_VALUES not in table.columns
    assert raster.CELL_WEIGHTS not in table.columns
    assert record["p10"] == 0.0
    assert record["p90"] == 0.0
    assert record["mean"] == pytest.approx(1.0)


def test_zonal_takes_every_district_shape_in_one_call():
    districts = load_districts()
    step = 0.05
    west, north = 68.0, 38.0
    field = np.full((int(32 / step), int(30 / step)), 7.0)
    grid = raster.Grid(field.astype("float32"), from_origin(west, north, step, step), CRS.from_epsg(4326))
    assert grid.bounds[0] <= districts.total_bounds[0] and grid.bounds[2] >= districts.total_bounds[2]
    assert grid.bounds[1] <= districts.total_bounds[1] and grid.bounds[3] >= districts.total_bounds[3]
    table = raster.zonal(grid, districts, raster.continuous_ops(grid))
    assert sorted(table["districtLgd"]) == sorted(districts["districtLgd"])
    assert table["mean"].to_numpy() == pytest.approx(np.full(len(districts), 7.0))


def test_zonal_quantiles_skip_nodata_cells():
    values = np.arange(16, dtype="float64").reshape(4, 4)
    values[0, 0] = np.nan
    table = raster.zonal(grid_of(values), zone(0, 0, 4, 4), raster.continuous_ops(grid_of(values)))
    record = table.iloc[0]
    assert record["p10"] == 2.0
    assert record["p90"] == 14.0
    assert record["pixels"] == pytest.approx(15.0)


def test_zonal_counts_no_cells_under_nodata_or_outside_the_grid_and_a_fraction_inside_one_cell():
    values = np.arange(16, dtype="float64").reshape(4, 4)
    values[2:, 2:] = np.nan
    zones = gpd.GeoDataFrame(
        {"districtLgd": [1, 2, 3]},
        geometry=[box(2.2, 0.2, 3.8, 1.8), box(10, 10, 11, 11), box(0.4, 0.4, 0.6, 0.6)],
        crs="EPSG:3857",
    )
    table = raster.zonal(grid_of(values), zones, raster.continuous_ops(grid_of(values)))
    assert list(table["districtLgd"]) == [1, 2, 3]
    assert list(table["pixels"]) == pytest.approx([0.0, 0.0, 0.04])
    assert [raster.has_cells(p) for p in table["pixels"]] == [False, False, True]
    assert table["mean"].iloc[2] == 12.0
    assert not raster.has_cells(float("nan"))
