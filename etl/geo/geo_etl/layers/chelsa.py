import geopandas as gpd

from geo_etl import raster, remote
from geo_etl.catalog import CHELSA
from geo_etl.layers import Measured, Options, Result, failure
from geo_etl.rows import Rows, pick

BASE = "https://os.zhdk.cloud.switch.ch/chelsav2/GLOBAL/climatologies/1981-2010"
PERIOD = "1981-2010"
NODATA = (65535,)
METHOD = (
    "Averaged over each district on the 1 km grid, each cell weighted by the share of it inside the district; "
    "the 10th and 90th percentiles are across the district's cells"
)

BIO = {
    "bio1": ("annual_mean_temperature", "degC"),
    "bio5": ("max_temperature_warmest_month", "degC"),
    "bio6": ("min_temperature_coldest_month", "degC"),
    "bio12": ("annual_precipitation", "mm/year"),
    "bio15": ("precipitation_seasonality", "coefficient of variation %"),
}

MONTHLY = {
    "tas": ("mean_temperature", "degC"),
    "pr": ("precipitation", "mm/month"),
}


def bio_url(code: str) -> str:
    return f"{BASE}/bio/CHELSA_{code}_{PERIOD}_V.2.1.tif"


def month_url(variable: str, month: int) -> str:
    return f"{BASE}/{variable}/CHELSA_{variable}_{month:02d}_{PERIOD}_V.2.1.tif"


def layers(options: Options) -> list[tuple[str, str, str, str]]:
    out = [(bio_url(code), BIO[code][0], PERIOD, BIO[code][1]) for code in options.chelsa_bio]
    if options.chelsa_months:
        for variable, (name, unit) in MONTHLY.items():
            out.extend((month_url(variable, m), name, f"{PERIOD}-{m:02d}", unit) for m in range(1, 13))
    return out


def run(districts: gpd.GeoDataFrame, options: Options) -> Result:
    rows = Rows(CHELSA, METHOD)
    failures: list[dict] = []
    measured = Measured()
    bounds = raster.bounds_in(districts, "EPSG:4326", 0.02)
    lookup = districts.set_index("districtLgd")
    for url, variable, period, unit in layers(options):
        try:
            grid = raster.read([url], bounds, nodata_values=NODATA, dtype="float32")
            if grid is None:
                raise RuntimeError(f"{url} not found")
            table = measured.add(raster.zonal(grid, districts, raster.continuous_ops(grid)))
            for _, record in table.iterrows():
                district = lookup.loc[int(record["districtLgd"])].copy()
                district["districtLgd"] = int(record["districtLgd"])
                pixels = float(record["pixels"])
                rows.add(district, variable, period, "NORMAL", pick(record, "mean"), unit=unit, pixels=pixels)
                rows.add(district, variable, period, "DISTRICT_P10", pick(record, "p10"), unit=unit, pixels=pixels)
                rows.add(district, variable, period, "DISTRICT_P90", pick(record, "p90"), unit=unit, pixels=pixels)
        except Exception as error:
            failures.append(failure(districts, f"chelsa {variable} {period}", error))
            if isinstance(error, remote.Unreachable):
                break
    return Result(CHELSA, rows.frame(), failures=failures, districts_without_cells=measured.without_cells())
