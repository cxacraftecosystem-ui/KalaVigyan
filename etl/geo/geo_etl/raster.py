import math
import os
from collections.abc import Iterable, Sequence
from contextlib import ExitStack
from dataclasses import dataclass
from functools import partial

import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
from exactextract import exact_extract
from exactextract.raster import NumPyRasterSource
from rasterio.crs import CRS
from rasterio.enums import Resampling
from rasterio.merge import merge
from rasterio.transform import Affine

from geo_etl import remote

GDAL_ENV = {
    "GDAL_DISABLE_READDIR_ON_OPEN": "EMPTY_DIR",
    "CPL_VSIL_CURL_ALLOWED_EXTENSIONS": ".tif,.TIF,.vrt,.ovr",
    "GDAL_HTTP_MULTIRANGE": "YES",
    "GDAL_HTTP_MERGE_CONSECUTIVE_RANGES": "YES",
    "GDAL_HTTP_MAX_RETRY": "5",
    "GDAL_HTTP_RETRY_DELAY": "3",
    "GDAL_HTTP_TIMEOUT": "120",
    "VSI_CACHE": "TRUE",
    "VSI_CACHE_SIZE": "268435456",
    "GDAL_CACHEMAX": "1024",
    "CPL_VSIL_CURL_CACHE_SIZE": "536870912",
}


def gdal_env() -> rasterio.Env:
    overrides = {k: os.environ.get(k, v) for k, v in GDAL_ENV.items()}
    return rasterio.Env(**{k: int(v) if v.isdigit() else v for k, v in overrides.items()})


def vsicurl(url: str) -> str:
    return url if url.startswith("/vsi") or not url.startswith("http") else "/vsicurl/" + url


@dataclass
class Grid:
    values: np.ndarray
    transform: Affine
    crs: CRS

    @property
    def bounds(self) -> tuple[float, float, float, float]:
        rows, cols = self.values.shape
        xmin, ymax = self.transform.c, self.transform.f
        xmax = xmin + cols * self.transform.a
        ymin = ymax + rows * self.transform.e
        return xmin, ymin, xmax, ymax

    @property
    def resolution(self) -> tuple[float, float]:
        return abs(self.transform.a), abs(self.transform.e)

    def source(self) -> NumPyRasterSource:
        xmin, ymin, xmax, ymax = self.bounds
        return NumPyRasterSource(self.values, xmin, ymin, xmax, ymax, srs_wkt=self.crs.to_wkt())


@dataclass(frozen=True)
class Mosaic:
    raw: np.ndarray
    transform: Affine
    crs: CRS
    fill: float
    scale: float
    offset: float


def read(
    urls: Sequence[str],
    bounds: tuple[float, float, float, float],
    *,
    factor: int = 1,
    resampling: Resampling = Resampling.nearest,
    nodata_values: Iterable[float] = (),
    valid_min: float | None = None,
    scale: float | None = None,
    offset: float | None = None,
    dtype: str = "float32",
) -> Grid | None:
    present = [location for location in urls if not remote.is_remote(location) or remote.found(location)]
    if not present:
        return None
    mosaic = remote.within_deadline(
        partial(mosaic_of, present, bounds, factor=factor, resampling=resampling),
        seconds=remote.FILE_DEADLINE_S * len(present),
        what=f"{len(present)} file(s) from {present[0]}",
    )
    values = mosaic.raw.astype("float64")
    values = values * (mosaic.scale if scale is None else scale) + (mosaic.offset if offset is None else offset)
    mask = nodata_mask(mosaic, nodata_values)
    if valid_min is not None:
        mask |= values < valid_min
    values[mask] = np.nan
    return Grid(values=values.astype(dtype), transform=mosaic.transform, crs=mosaic.crs)


def mosaic_of(
    locations: Sequence[str], bounds: tuple[float, float, float, float], *, factor: int, resampling: Resampling
) -> Mosaic:
    with gdal_env(), ExitStack() as opened:
        datasets = [opened.enter_context(rasterio.open(vsicurl(location))) for location in locations]
        first = datasets[0]
        rx, ry = first.res
        res = (rx * factor, ry * factor)
        snapped = snap_bounds(bounds, (first.transform.c, first.transform.f), res)
        fill = first.nodata if first.nodata is not None else _fill_for(first.dtypes[0])
        array, transform = merge(datasets, bounds=snapped, res=res, nodata=fill, resampling=resampling, indexes=[1])
        return Mosaic(
            raw=array[0],
            transform=transform,
            crs=first.crs,
            fill=fill,
            scale=first.scales[0] if first.scales else 1.0,
            offset=first.offsets[0] if first.offsets else 0.0,
        )


def nodata_mask(mosaic: Mosaic, nodata_values: Iterable[float]) -> np.ndarray:
    raw = mosaic.raw
    mask = np.isnan(raw) if np.isnan(mosaic.fill) else raw == mosaic.fill
    for value in nodata_values:
        mask |= raw == value
    return mask


def _fill_for(dtype: str) -> float:
    kind = np.dtype(dtype)
    if kind.kind == "u":
        return float(np.iinfo(kind).max)
    if kind.kind == "i":
        return float(np.iinfo(kind).min)
    return float("nan")


def bounds_in(frame: gpd.GeoDataFrame, crs: CRS | str, pad: float = 0.0) -> tuple[float, float, float, float]:
    xmin, ymin, xmax, ymax = frame.to_crs(crs).total_bounds
    return xmin - pad, ymin - pad, xmax + pad, ymax + pad


def snap_bounds(
    bounds: tuple[float, float, float, float], origin: tuple[float, float], step: tuple[float, float]
) -> tuple[float, float, float, float]:
    ox, oy = origin
    sx, sy = step
    xmin = ox + math.floor((bounds[0] - ox) / sx) * sx
    xmax = ox + math.ceil((bounds[2] - ox) / sx) * sx
    ymin = oy + math.floor((bounds[1] - oy) / sy) * sy
    ymax = oy + math.ceil((bounds[3] - oy) / sy) * sy
    return xmin, ymin, xmax, ymax


QUANTILES = {"p10": 0.1, "p90": 0.9}
CELL_VALUES = "cellvalues"
CELL_WEIGHTS = "cellweights"


def weighted_quantile(values: np.ndarray, weights: np.ndarray, q: float) -> float:
    values = np.asarray(values, dtype="float64")
    weights = np.asarray(weights, dtype="float64")
    keep = np.isfinite(values) & np.isfinite(weights) & (weights > 0)
    if not keep.any():
        return float("nan")
    order = np.argsort(values[keep], kind="stable")
    ordered = values[keep][order]
    cumulative = np.cumsum(weights[keep][order])
    index = int(np.searchsorted(cumulative, q * cumulative[-1], side="left"))
    return float(ordered[min(index, len(ordered) - 1)])


def zonal(grid: Grid, frame: gpd.GeoDataFrame, ops: list[str]) -> pd.DataFrame:
    local = frame[["districtLgd", "geometry"]].to_crs(grid.crs)
    table = pd.DataFrame(exact_extract(grid.source(), local, ops, include_cols=["districtLgd"], output="pandas"))
    if CELL_VALUES in table.columns:
        for name, q in QUANTILES.items():
            table[name] = [
                weighted_quantile(v, w, q) for v, w in zip(table[CELL_VALUES], table[CELL_WEIGHTS], strict=True)
            ]
        table = table.drop(columns=[CELL_VALUES, CELL_WEIGHTS])
    return table


def has_cells(pixels: float) -> bool:
    return float(pixels) > 0.0


def geographic(grid: Grid) -> bool:
    return bool(grid.crs.is_geographic)


def weight(grid: Grid) -> str:
    return "area_spherical_km2" if geographic(grid) else "area_cartesian"


def continuous_ops(grid: Grid) -> list[str]:
    w = weight(grid)
    return [
        f"mean=mean(coverage_weight={w})",
        f"{CELL_VALUES}=values",
        f"{CELL_WEIGHTS}=coverage(coverage_weight={w})",
        "pixels=count(coverage_weight=fraction)",
    ]


def class_ops(grid: Grid) -> list[str]:
    w = weight(grid)
    return ["classes=unique", f"shares=frac(coverage_weight={w})", "pixels=count(coverage_weight=fraction)"]


def describe(grid: Grid) -> str:
    rx, ry = grid.resolution
    unit = "degree" if geographic(grid) else "m"
    return f"{rx:.8g} x {ry:.8g} {unit} grid"
