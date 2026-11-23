import math

import geopandas as gpd
import numpy as np

from geo_etl import raster
from geo_etl.catalog import COPDEM
from geo_etl.layers import Measured, Options, Result, each_district
from geo_etl.rows import Rows, pick

BASE = "https://copernicus-dem-90m.s3.amazonaws.com"


def tile_url(lat: int, lon: int) -> str:
    ns = "N" if lat >= 0 else "S"
    ew = "E" if lon >= 0 else "W"
    name = f"Copernicus_DSM_COG_30_{ns}{abs(lat):02d}_00_{ew}{abs(lon):03d}_00_DEM"
    return f"{BASE}/{name}/{name}.tif"


def tiles(bounds: tuple[float, float, float, float]) -> list[str]:
    xmin, ymin, xmax, ymax = bounds
    return [
        tile_url(lat, lon)
        for lat in range(math.floor(ymin), math.ceil(ymax))
        for lon in range(math.floor(xmin), math.ceil(xmax))
    ]


def slope_degrees(elevation: np.ndarray, transform) -> np.ndarray:
    rows = elevation.shape[0]
    rx, ry = abs(transform.a), abs(transform.e)
    lat = np.radians(transform.f - (np.arange(rows) + 0.5) * ry)
    m_lat = 111132.954 - 559.822 * np.cos(2 * lat) + 1.175 * np.cos(4 * lat)
    m_lon = 111412.84 * np.cos(lat) - 93.5 * np.cos(3 * lat)
    dz_dy = np.gradient(elevation, axis=0) / (ry * m_lat)[:, None]
    dz_dx = np.gradient(elevation, axis=1) / (rx * m_lon)[:, None]
    return np.degrees(np.arctan(np.hypot(dz_dx, dz_dy))).astype("float32")


def run(districts: gpd.GeoDataFrame, options: Options) -> Result:
    factor = max(1, options.dem_factor)
    effective = "3 arc-seconds (about 90 m)" if factor == 1 else f"{3 * factor} arc-seconds (overview, nearest)"
    rows = Rows(
        COPDEM,
        f"exactextract coverage weight area_spherical_km2 at {effective}; slope from central differences with "
        "latitude-dependent metres per degree; missing ocean tiles are no data",
    )
    measured = Measured()

    def measure(group: gpd.GeoDataFrame) -> None:
        district = group.iloc[0]
        bounds = raster.bounds_in(group, "EPSG:4326", 0.01)
        grid = raster.read(tiles(bounds), bounds, factor=factor, dtype="float32")
        if grid is None:
            raise RuntimeError(f"no Copernicus DEM tile exists under {bounds}")
        ops = [*raster.continuous_ops(grid), "low=min", "high=max"]
        record = measured.add(raster.zonal(grid, group, ops)).iloc[0]
        if not raster.has_cells(record["pixels"]):
            return
        pixels = float(record["pixels"])
        for stat, key in (
            ("DISTRICT_MEAN", "mean"),
            ("DISTRICT_P10", "p10"),
            ("DISTRICT_P90", "p90"),
            ("DISTRICT_MIN", "low"),
            ("DISTRICT_MAX", "high"),
        ):
            rows.add(district, "elevation", "", stat, pick(record, key), unit="m", pixels=pixels, resolution=effective)
        slope = raster.Grid(slope_degrees(grid.values, grid.transform), grid.transform, grid.crs)
        record = raster.zonal(slope, group, raster.continuous_ops(slope)).iloc[0]
        for stat, key in (("DISTRICT_MEAN", "mean"), ("DISTRICT_P10", "p10"), ("DISTRICT_P90", "p90")):
            rows.add(district, "slope", "", stat, pick(record, key), unit="degree", pixels=pixels, resolution=effective)

    failures = each_district(districts, "copdem", measure)
    return Result(COPDEM, rows.frame(), failures=failures, districts_without_cells=measured.without_cells())
