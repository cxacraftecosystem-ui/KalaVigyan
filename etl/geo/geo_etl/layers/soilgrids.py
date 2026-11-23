import math

import geopandas as gpd
import numpy as np
import pandas as pd
import requests
from rasterio.crs import CRS
from rasterio.io import MemoryFile
from rasterio.transform import from_origin

from geo_etl import raster
from geo_etl.catalog import SOILGRIDS
from geo_etl.layers import Measured, Options, Result, by_state, failure
from geo_etl.remote import USER_AGENT, with_retries
from geo_etl.rows import Rows, pick

WCS = "https://maps.isric.org/mapserv"
HOMOLOSINE = CRS.from_proj4("+proj=igh +lat_0=0 +lon_0=0 +datum=WGS84 +units=m +no_defs")
CELL = 250.0
CHUNK = 2000
NODATA = -32768
MASKED = 0
PAD_M = 1000.0

CONVERSION = {
    "clay": (10.0, "%"),
    "sand": (10.0, "%"),
    "silt": (10.0, "%"),
    "soc": (10.0, "g/kg"),
    "phh2o": (10.0, "pH"),
    "cec": (10.0, "cmol(c)/kg"),
    "bdod": (100.0, "kg/dm3"),
    "nitrogen": (100.0, "g/kg"),
}


def snap(bounds: tuple[float, float, float, float]) -> tuple[float, float, float, float]:
    xmin, ymin, xmax, ymax = bounds
    return (
        math.floor(xmin / CELL) * CELL,
        math.floor(ymin / CELL) * CELL,
        math.ceil(xmax / CELL) * CELL,
        math.ceil(ymax / CELL) * CELL,
    )


def coverage(variable: str, depth: str, layer: str, bounds: tuple[float, float, float, float]) -> np.ndarray:
    xmin, ymin, xmax, ymax = bounds
    params = {
        "map": f"/map/{variable}.map",
        "SERVICE": "WCS",
        "VERSION": "2.0.1",
        "REQUEST": "GetCoverage",
        "COVERAGEID": f"{variable}_{depth}_{layer}",
        "FORMAT": "image/tiff",
        "SUBSET": [f"X({xmin:.0f},{xmax:.0f})", f"Y({ymin:.0f},{ymax:.0f})"],
    }
    expected = (round((ymax - ymin) / CELL), round((xmax - xmin) / CELL))

    def fetch() -> np.ndarray:
        response = requests.get(WCS, params=params, timeout=300, headers={"User-Agent": USER_AGENT})
        response.raise_for_status()
        with MemoryFile(response.content) as memory, memory.open() as dataset:
            if dataset.shape != expected or abs(dataset.res[0] - CELL) > 1e-6:
                raise RuntimeError(f"WCS returned {dataset.shape} at {dataset.res}, expected {expected} at {CELL}")
            return dataset.read(1)

    return with_retries(fetch, retry_on=(requests.RequestException, RuntimeError))


def read(variable: str, depth: str, layer: str, bounds: tuple[float, float, float, float], divisor: float):
    xmin, ymin, xmax, ymax = snap(bounds)
    cols = round((xmax - xmin) / CELL)
    rows = round((ymax - ymin) / CELL)
    out = np.full((rows, cols), np.nan, dtype="float32")
    for r0 in range(0, rows, CHUNK):
        for c0 in range(0, cols, CHUNK):
            r1, c1 = min(rows, r0 + CHUNK), min(cols, c0 + CHUNK)
            part = coverage(
                variable,
                depth,
                layer,
                (xmin + c0 * CELL, ymax - r1 * CELL, xmin + c1 * CELL, ymax - r0 * CELL),
            )
            block = part.astype("float32") / divisor
            block[part == NODATA] = np.nan
            if layer == "mean":
                block[part == MASKED] = np.nan
            out[r0:r1, c0:c1] = block
    return raster.Grid(out, from_origin(xmin, ymax, CELL, CELL), HOMOLOSINE)


def run(districts: gpd.GeoDataFrame, options: Options) -> Result:
    rows = Rows(
        SOILGRIDS,
        "ISRIC WCS 2.0.1 GetCoverage on the native 250 m Homolosine grid (request bounds snapped to the grid, "
        "no resampling); cells the service returns as 0 (SoilGrids mask: built-up, water, rock) and their "
        "uncertainty cells treated as no data; district polygons reprojected to Homolosine; exactextract "
        "coverage-weighted (area_cartesian); values divided by the ISRIC conversion factor",
    )
    failures: list[dict] = []
    measured = Measured()
    for group in by_state(districts):
        bounds = raster.bounds_in(group, HOMOLOSINE, PAD_M)
        for variable in options.soil_vars:
            divisor, unit = CONVERSION[variable]
            for depth in options.soil_depths:
                layers = [("mean", None)]
                if options.soil_uncertainty:
                    layers += [("Q0.05", "UNCERTAINTY_Q05_MEAN"), ("Q0.95", "UNCERTAINTY_Q95_MEAN")]
                valid = None
                for layer, stat in layers:
                    try:
                        grid = read(variable, depth, layer, bounds, divisor)
                        if layer == "mean":
                            valid = ~np.isnan(grid.values)
                        elif valid is None:
                            raise RuntimeError("mean layer missing, so the SoilGrids mask is unknown")
                        else:
                            grid.values[~valid] = np.nan
                        ops = raster.continuous_ops(grid)
                        if stat is not None:
                            ops = [ops[0], ops[-1]]
                        table = measured.add(raster.zonal(grid, group, ops))
                        emit(rows, group, table, variable, depth, unit, stat)
                    except Exception as error:
                        failures.append(failure(group, f"{variable} {depth} {layer}", error))
    return Result(SOILGRIDS, rows.frame(), failures=failures, districts_without_cells=measured.without_cells())


def emit(rows: Rows, group: gpd.GeoDataFrame, table: pd.DataFrame, variable, depth, unit, stat) -> None:
    lookup = group.set_index("districtLgd")
    for _, record in table.iterrows():
        district = lookup.loc[int(record["districtLgd"])].copy()
        district["districtLgd"] = int(record["districtLgd"])
        pixels = float(record["pixels"])
        if stat is None:
            rows.add(district, variable, depth, "DISTRICT_MEAN", pick(record, "mean"), unit, pixels=pixels)
            rows.add(district, variable, depth, "DISTRICT_P10", pick(record, "p10"), unit, pixels=pixels)
            rows.add(district, variable, depth, "DISTRICT_P90", pick(record, "p90"), unit, pixels=pixels)
        else:
            rows.add(district, variable, depth, stat, pick(record, "mean"), unit, pixels=pixels)
