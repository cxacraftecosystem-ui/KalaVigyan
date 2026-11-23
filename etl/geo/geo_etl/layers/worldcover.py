import math

import geopandas as gpd
import numpy as np
import pandas as pd

from geo_etl import raster
from geo_etl.catalog import WORLDCOVER
from geo_etl.layers import Measured, Options, Result, each_district
from geo_etl.rows import Rows, pick

BASE = "https://esa-worldcover.s3.eu-central-1.amazonaws.com/v200/2021/map"

CLASSES = {
    10: "tree_cover",
    20: "shrubland",
    30: "grassland",
    40: "cropland",
    50: "built_up",
    60: "bare_sparse_vegetation",
    70: "snow_ice",
    80: "permanent_water",
    90: "herbaceous_wetland",
    95: "mangroves",
    100: "moss_lichen",
}


def tile_name(lat: int, lon: int) -> str:
    ns = "N" if lat >= 0 else "S"
    ew = "E" if lon >= 0 else "W"
    return f"{ns}{abs(lat):02d}{ew}{abs(lon):03d}"


def tiles(bounds: tuple[float, float, float, float]) -> list[str]:
    xmin, ymin, xmax, ymax = bounds
    out = []
    for lat in range(math.floor(ymin / 3) * 3, math.ceil(ymax / 3) * 3, 3):
        for lon in range(math.floor(xmin / 3) * 3, math.ceil(xmax / 3) * 3, 3):
            out.append(f"{BASE}/ESA_WorldCover_10m_2021_v200_{tile_name(lat, lon)}_Map.tif")
    return out


def run(districts: gpd.GeoDataFrame, options: Options) -> Result:
    factor = max(1, options.worldcover_factor)
    effective = f"{10 * factor} m (overview read, factor {factor}, nearest)" if factor > 1 else "10 m"
    rows = Rows(
        WORLDCOVER,
        f"exactextract class fractions, coverage weight area_spherical_km2, read at {effective}; "
        "share of mapped area inside the district polygon",
    )
    measured = Measured()

    def measure(group: gpd.GeoDataFrame) -> None:
        bounds = raster.bounds_in(group, "EPSG:4326", 0.01)
        grid = raster.read(tiles(bounds), bounds, factor=factor, nodata_values=(0,), dtype="float32")
        if grid is None:
            raise RuntimeError(f"no WorldCover tile exists under {bounds}")
        record = measured.add(raster.zonal(grid, group, raster.class_ops(grid))).iloc[0]
        if raster.has_cells(record["pixels"]):
            add_shares(rows, group.iloc[0], record, effective)

    failures = each_district(districts, "worldcover", measure)
    return Result(WORLDCOVER, rows.frame(), failures=failures, districts_without_cells=measured.without_cells())


def add_shares(rows: Rows, district: pd.Series, record: pd.Series, effective: str) -> None:
    classes = np.asarray(pick(record, "classes"), dtype=float)
    shares = np.asarray(pick(record, "shares"), dtype=float)
    found = {int(c): float(s) for c, s in zip(classes, shares, strict=True)}
    pixels = float(record["pixels"])
    for code, name in CLASSES.items():
        rows.add(
            district,
            f"landcover_{name}",
            "2021",
            "SHARE",
            found.get(code, 0.0),
            unit="fraction",
            pixels=pixels,
            resolution=effective,
        )
