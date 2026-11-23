import dataclasses
import datetime as dt
import math
import re
from collections.abc import Sequence
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
from rasterio.crs import CRS
from rasterio.transform import Affine
from rasterio.windows import Window

from geo_etl import raster
from geo_etl.catalog import GHCN_CAMS
from geo_etl.layers import Measured, Options, Result, download, failure
from geo_etl.rows import Rows, pick
from geo_etl.trend import AnnualSeries, add_trend_rows

VARIABLE = "air"
TEMPERATURE = "annual_mean_temperature"
UNIT = "degC"
KELVIN = 273.15
KELVIN_UNITS = ("degK", "K")
VALID_KELVIN = (150.0, 400.0)
RECORD_FIRST_YEAR = 1948
MONTHS = tuple(range(1, 13))
TIME_UNITS = re.compile(r"^\s*(hours|days) since (\d{4})-(\d{1,2})-(\d{1,2})")
STEPS = {"hours": dt.timedelta(hours=1), "days": dt.timedelta(days=1)}
GRID_CRS = CRS.from_epsg(4326)
BOUNDS_PAD_DEGREES = 0.5
METHOD = (
    "annual mean of the twelve monthly means of each 0.5 degree cell, a cell missing any month left out of "
    "that year; Kelvin less 273.15; exactextract coverage weight area_spherical_km2 on the native grid; "
    "normals are the mean of yearly district means"
)


@dataclasses.dataclass(frozen=True)
class MonthlyGrids:
    months: tuple[tuple[int, int], ...]
    celsius: np.ndarray
    transform: Affine


def run(districts: gpd.GeoDataFrame, options: Options) -> Result:
    path = download(GHCN_CAMS.url, options.cache / "ghcncams" / cached_name(dt.date.today()))
    grids = read_months(path, raster.bounds_in(districts, "EPSG:4326", BOUNDS_PAD_DEGREES))
    years = complete_years(grids.months, options.climate_first_year)
    rows = Rows(dataclasses.replace(GHCN_CAMS, period=f"{years[0]}-{years[-1]}"), METHOD)
    measured = Measured()
    failures: list[dict] = []
    annual: dict[int, pd.DataFrame] = {}
    for year in years:
        try:
            grid = annual_grid(grids, year)
            table = measured.add(raster.zonal(grid, districts, raster.continuous_ops(grid)))
            annual[year] = table.set_index("districtLgd")
        except Exception as error:
            failures.append(failure(districts, f"ghcncams annual {year}", error))
    lookup = districts.set_index("districtLgd")
    for lgd in districts["districtLgd"]:
        district = lookup.loc[int(lgd)].copy()
        district["districtLgd"] = int(lgd)
        add_district(rows, district, annual, years)
    return Result(
        rows.dataset,
        rows.frame(),
        failures=failures,
        notes={"period": rows.dataset.period},
        districts_without_cells=measured.without_cells(),
    )


def cached_name(today: dt.date) -> str:
    return f"air.mon.mean.{today:%Y-%m}.nc"


def read_months(path: Path, bounds: tuple[float, float, float, float]) -> MonthlyGrids:
    with raster.gdal_env(), rasterio.open(f'NETCDF:"{path.as_posix()}":{VARIABLE}') as source:
        tags = source.tags()
        times = [float(source.tags(band)["NETCDF_DIM_time"]) for band in source.indexes]
        months = month_keys(times, tags["time#units"])
        window = grid_window(source, bounds)
        stack = source.read(window=window, out_dtype="float64")
        scales = np.asarray(source.scales, dtype="float64").reshape(-1, 1, 1)
        offsets = np.asarray(source.offsets, dtype="float64").reshape(-1, 1, 1)
        transform = source.window_transform(window)
    return MonthlyGrids(months, celsius(stack * scales + offsets, tags.get(f"{VARIABLE}#units")), transform)


def month_keys(times: Sequence[float], units: str) -> tuple[tuple[int, int], ...]:
    found = TIME_UNITS.match(units)
    if found is None:
        raise RuntimeError(f"GHCN CAMS time units {units!r} are not hours or days since a date")
    base = dt.datetime(int(found[2]), int(found[3]), int(found[4]))
    stamps = [base + STEPS[found[1]] * value for value in times]
    keys = tuple((stamp.year, stamp.month) for stamp in stamps)
    for before, after in zip(keys, keys[1:], strict=False):
        if after != next_month(before):
            raise RuntimeError(f"GHCN CAMS months are not consecutive: {before} is followed by {after}")
    return keys


def next_month(key: tuple[int, int]) -> tuple[int, int]:
    year, month = key
    return (year + 1, 1) if month == 12 else (year, month + 1)


def grid_window(source: rasterio.DatasetReader, bounds: tuple[float, float, float, float]) -> Window:
    left, bottom, right, top = source.bounds
    xmin, ymin, xmax, ymax = bounds
    if source.transform.e >= 0 or xmin < left or xmax > right or ymin < bottom or ymax > top:
        raise RuntimeError(f"GHCN CAMS grid {source.bounds} does not hold {bounds} north up")
    first_row, first_col = source.index(xmin, ymax, op=math.floor)
    last_row, last_col = source.index(xmax, ymin, op=math.floor)
    whole = Window(0, 0, source.width, source.height)
    return Window(first_col, first_row, last_col - first_col + 1, last_row - first_row + 1).intersection(whole)


def celsius(kelvin: np.ndarray, units: str | None) -> np.ndarray:
    if units not in KELVIN_UNITS:
        raise RuntimeError(f"GHCN CAMS {VARIABLE} is in {units!r}, not Kelvin")
    low, high = VALID_KELVIN
    values = np.where(np.isfinite(kelvin) & (kelvin >= low) & (kelvin <= high), kelvin, np.nan)
    return values - KELVIN


def complete_years(months: Sequence[tuple[int, int]], first: int) -> range:
    if first < RECORD_FIRST_YEAR:
        raise RuntimeError(f"GHCN CAMS starts in {RECORD_FIRST_YEAR}, not {first}")
    held = set(months)
    complete = [year for year in {year for year, _ in held} if all((year, m) in held for m in MONTHS)]
    last = max(complete, default=first - 1)
    if last < first or any(year not in complete for year in range(first, last + 1)):
        raise RuntimeError(f"GHCN CAMS holds no complete run of years from {first}")
    return range(first, last + 1)


def annual_grid(grids: MonthlyGrids, year: int) -> raster.Grid:
    position = {key: index for index, key in enumerate(grids.months)}
    bands = [position[(year, month)] for month in MONTHS]
    mean = grids.celsius[bands].mean(axis=0)
    return raster.Grid(values=mean.astype("float32"), transform=grids.transform, crs=GRID_CRS)


def add_district(rows: Rows, district: pd.Series, annual: dict[int, pd.DataFrame], years: range) -> None:
    lgd = int(district["districtLgd"])
    yearly = []
    for year in years:
        table = annual.get(year)
        if table is None or lgd not in table.index:
            yearly.append(math.nan)
            continue
        record = table.loc[lgd]
        value = float(pick(record, "mean"))
        yearly.append(value)
        rows.add(district, TEMPERATURE, str(year), "DISTRICT_MEAN", value, unit=UNIT, pixels=float(record["pixels"]))
    series = AnnualSeries(TEMPERATURE, years[0], tuple(yearly))
    if series.complete:
        rows.add(district, TEMPERATURE, series.period, "NORMAL", float(np.mean(series.values)), unit=UNIT)
        add_trend_rows(rows, district, series)
