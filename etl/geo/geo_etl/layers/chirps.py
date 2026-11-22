import dataclasses
import datetime as dt
import re
from functools import partial

import geopandas as gpd
import numpy as np
import pandas as pd
import requests

from geo_etl import raster, remote
from geo_etl.catalog import CHIRPS, CLIMATE_FIRST_YEAR
from geo_etl.layers import Measured, Options, Result, failure
from geo_etl.remote import ABSENT, RETRY_ON, answered, with_retries
from geo_etl.rows import Rows, pick
from geo_etl.trend import AnnualSeries, add_trend_rows

BASE = "https://data.chc.ucsb.edu/products/CHIRPS/v3.0"
ANNUAL_DIR = f"{BASE}/annual/global/tifs/"
ANNUAL_FILE = re.compile(r"chirps-v3\.0\.(\d{4})\.tif(?![\w.])")
LOOKBACK_YEARS = 4
MONSOON = (6, 7, 8, 9)
METHOD = (
    "exactextract coverage weight area_spherical_km2 on the native 0.05 degree grid; negative values treated as "
    "no data; normals are the mean of yearly district means"
)


def annual_url(year: int) -> str:
    return f"{BASE}/annual/global/tifs/chirps-v3.0.{year}.tif"


def monthly_url(year: int, month: int) -> str:
    return f"{BASE}/monthly/global/tifs/chirps-v3.0.{year}.{month:02d}.tif"


def latest_year(today: dt.date | None = None) -> int:
    newest = (today or dt.date.today()).year - 1
    candidates = list(range(newest, newest - LOOKBACK_YEARS, -1))
    try:
        return probed_year(candidates)
    except requests.RequestException as probe_error:
        try:
            return listed_year(candidates)
        except requests.RequestException as listing_error:
            raise RuntimeError(
                f"CHIRPS v3.0 annual files unreachable: probe {probe_error}; listing {listing_error}"
            ) from listing_error


def probed_year(candidates: list[int]) -> int:
    for year in candidates:
        response = with_retries(partial(answered, "HEAD", annual_url(year)), retry_on=RETRY_ON)
        if response.status_code not in ABSENT:
            return year
    raise RuntimeError(f"no CHIRPS v3.0 annual file for {candidates[-1]} to {candidates[0]}: every year is not found")


def listed_year(candidates: list[int]) -> int:
    response = with_retries(partial(answered, "GET", ANNUAL_DIR), retry_on=RETRY_ON)
    if response.status_code in ABSENT:
        raise RuntimeError(f"{ANNUAL_DIR} answered {response.status_code}")
    listed = {int(year) for year in ANNUAL_FILE.findall(response.text)} & set(candidates)
    if not listed:
        raise RuntimeError(f"{ANNUAL_DIR} lists no CHIRPS v3.0 annual file for {candidates[-1]} to {candidates[0]}")
    return max(listed)


def district_means(url: str, districts: gpd.GeoDataFrame, bounds, *, measured: Measured) -> pd.DataFrame:
    grid = raster.read([url], bounds, valid_min=0.0, dtype="float32")
    if grid is None:
        raise RuntimeError(f"{url} not found")
    table = measured.add(raster.zonal(grid, districts, raster.continuous_ops(grid)))
    return table.set_index("districtLgd")


def last_year(options: Options) -> int:
    return latest_year() if options.chirps_last_year is None else options.chirps_last_year


def run(districts: gpd.GeoDataFrame, options: Options) -> Result:
    years = run_years(options.climate_first_year, last_year(options))
    period = f"{years[0]}-{years[-1]}"
    reads = Reads(districts)
    rows = Rows(dataclasses.replace(CHIRPS, period=period), METHOD)
    annual = reads.each({year: annual_url(year) for year in years}, "chirps annual")
    monthly = {}
    if options.chirps_monthly:
        urls = {(year, month): monthly_url(year, month) for year in years for month in range(1, 13)}
        monthly = reads.each(urls, "chirps monthly")
    lookup = districts.set_index("districtLgd")
    for lgd in districts["districtLgd"]:
        district = lookup.loc[int(lgd)].copy()
        district["districtLgd"] = int(lgd)
        add_annual(rows, district, annual, years)
        if options.chirps_monthly:
            add_monthly(rows, district, monthly, period, len(years))
    return Result(
        rows.dataset,
        rows.frame(),
        failures=reads.failures,
        notes={"period": period},
        districts_without_cells=reads.measured.without_cells(),
    )


def run_years(first: int, last: int) -> range:
    if not CLIMATE_FIRST_YEAR <= first <= last:
        raise RuntimeError(f"CHIRPS v3.0 runs from {CLIMATE_FIRST_YEAR} to {last}, not from {first}")
    return range(first, last + 1)


@dataclasses.dataclass
class Reads:
    districts: gpd.GeoDataFrame
    measured: Measured = dataclasses.field(default_factory=Measured)
    failures: list[dict] = dataclasses.field(default_factory=list)
    unreachable: bool = False

    def each[K](self, urls: dict[K, str], step: str) -> dict[K, pd.DataFrame]:
        bounds = raster.bounds_in(self.districts, "EPSG:4326", 0.1)
        tables: dict[K, pd.DataFrame] = {}
        for key, url in urls.items():
            if self.unreachable:
                break
            try:
                tables[key] = district_means(url, self.districts, bounds, measured=self.measured)
            except Exception as error:
                self.unreachable = isinstance(error, remote.Unreachable)
                self.failures.append(failure(self.districts, f"{step} {step_key(key)}", error))
        return tables


def step_key(key: int | tuple[int, int]) -> str:
    return f"{key[0]}-{key[1]:02d}" if isinstance(key, tuple) else str(key)


def add_annual(rows: Rows, district: pd.Series, annual: dict[int, pd.DataFrame], years: range) -> None:
    lgd = int(district["districtLgd"])
    yearly = []
    for year in years:
        table = annual.get(year)
        if table is None or lgd not in table.index:
            yearly.append(float("nan"))
            continue
        record = table.loc[lgd]
        value = float(pick(record, "mean"))
        yearly.append(value)
        pixels = float(record["pixels"])
        rows.add(district, "annual_precipitation", str(year), "DISTRICT_MEAN", value, "mm/year", pixels=pixels)
        rows.add(district, "annual_precipitation", str(year), "DISTRICT_P10", pick(record, "p10"), "mm/year")
        rows.add(district, "annual_precipitation", str(year), "DISTRICT_P90", pick(record, "p90"), "mm/year")
    series = AnnualSeries("annual_precipitation", years[0], tuple(yearly))
    if series.complete:
        add_normals(rows, district, series)


def add_normals(rows: Rows, district: pd.Series, series: AnnualSeries) -> None:
    mean = float(np.mean(series.values))
    rows.add(district, "annual_precipitation", series.period, "NORMAL", mean, "mm/year")
    if len(series.values) >= 2 and mean > 0:
        spread = float(np.std(series.values) / mean)
        rows.add(district, "annual_precipitation_cv", series.period, "NORMAL", spread, "fraction")
    add_trend_rows(rows, district, series)


def add_monthly(
    rows: Rows, district: pd.Series, monthly: dict[tuple[int, int], pd.DataFrame], period: str, year_count: int
) -> None:
    lgd = int(district["districtLgd"])
    by_month: dict[int, list[float]] = {}
    for (_, month), table in monthly.items():
        if lgd in table.index:
            value = float(pick(table.loc[lgd], "mean"))
            if np.isfinite(value):
                by_month.setdefault(month, []).append(value)
    if not all(len(by_month.get(m, [])) == year_count for m in range(1, 13)):
        return
    normals = {m: float(np.mean(by_month[m])) for m in range(1, 13)}
    for month, value in normals.items():
        rows.add(district, "monthly_precipitation", f"{period}-{month:02d}", "NORMAL", value, "mm/month")
    total = sum(normals.values())
    if total > 0:
        share = sum(normals[m] for m in MONSOON) / total
        rows.add(district, "monsoon_share_jjas", period, "NORMAL", share, "fraction of annual")
