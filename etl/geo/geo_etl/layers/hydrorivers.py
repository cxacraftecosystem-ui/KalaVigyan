import zipfile
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
from shapely.geometry import Point

from geo_etl.catalog import HYDRORIVERS
from geo_etl.districts import INDIA_LCC
from geo_etl.layers import Options, Result, download, failure
from geo_etl.rows import Rows

URL = HYDRORIVERS.url
ARCHIVE = "HydroRIVERS_v10_as_shp.zip"
MAJOR_ORD_FLOW = 4
MAJOR_DISCHARGE_M3S = 100
COLUMNS = ["HYRIV_ID", "ORD_STRA", "ORD_FLOW", "DIS_AV_CMS", "LENGTH_KM", "UPLAND_SKM"]
METHOD = (
    "River reaches measured inside each district; a major river carries at least "
    f"{MAJOR_DISCHARGE_M3S} m³/s on average; distance from the district's centre to the nearest major river"
)


def cached_archive(cache: Path) -> Path:
    return download(URL, cache / "hydrorivers" / ARCHIVE)


def shapefile_member(archive: Path) -> str:
    with zipfile.ZipFile(archive) as handle:
        for name in handle.namelist():
            if name.lower().endswith(".shp"):
                return name
    raise RuntimeError(f"{archive.name} holds no shapefile")


def load_rivers(archive: Path, bounds: tuple[float, float, float, float]) -> gpd.GeoDataFrame:
    member = shapefile_member(archive)
    rivers = gpd.read_file(f"zip://{archive.as_posix()}!{member}", bbox=bounds, columns=COLUMNS)
    return rivers.set_crs("EPSG:4326", allow_override=True)


def metrics(districts_lcc: gpd.GeoDataFrame, rivers_lcc: gpd.GeoDataFrame) -> pd.DataFrame:
    major = rivers_lcc[rivers_lcc["ORD_FLOW"] <= MAJOR_ORD_FLOW]
    major_union = major.geometry.union_all() if len(major) else None
    index = rivers_lcc.sindex
    out = []
    for _, district in districts_lcc.iterrows():
        shape = district.geometry
        hits = rivers_lcc.iloc[index.query(shape, predicate="intersects")]
        clipped = hits.geometry.intersection(shape)
        lengths = clipped.length / 1000.0
        total = float(lengths.sum())
        is_major = (hits["ORD_FLOW"] <= MAJOR_ORD_FLOW).to_numpy()
        major_length = float(lengths[is_major].sum()) if len(hits) else 0.0
        area_km2 = shape.area / 1e6
        centre = Point(district["centroidX"], district["centroidY"])
        distance = float(centre.distance(major_union) / 1000.0) if major_union is not None else None
        out.append(
            {
                "districtLgd": int(district["districtLgd"]),
                "river_length": total,
                "river_density": total / area_km2 if area_km2 > 0 else None,
                "major_river_length": major_length,
                "distance_centroid_to_major_river": distance,
                "max_strahler_order": float(hits["ORD_STRA"].max()) if len(hits) else None,
                "max_discharge": float(hits["DIS_AV_CMS"].max()) if len(hits) else None,
                "reaches": int(len(hits)),
            }
        )
    return pd.DataFrame(out)


def to_lcc(districts: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    frame = districts.to_crs(INDIA_LCC)
    centres = gpd.GeoSeries(
        [Point(x, y) for x, y in zip(districts["centroidLon"], districts["centroidLat"], strict=True)],
        crs="EPSG:4326",
    ).to_crs(INDIA_LCC)
    frame["centroidX"] = np.asarray(centres.x)
    frame["centroidY"] = np.asarray(centres.y)
    return frame


def run(districts: gpd.GeoDataFrame, options: Options) -> Result:
    rows = Rows(HYDRORIVERS, METHOD)
    failures: list[dict] = []
    try:
        archive = cached_archive(options.cache)
        xmin, ymin, xmax, ymax = districts.total_bounds
        rivers = load_rivers(archive, (xmin - 2, ymin - 2, xmax + 2, ymax + 2)).to_crs(INDIA_LCC)
        table = metrics(to_lcc(districts), rivers)
    except Exception as error:
        failures.append(failure(districts, "hydrorivers", error))
        return Result(HYDRORIVERS, rows.frame(), failures=failures)
    lookup = districts.set_index("districtLgd")
    units = {
        "river_length": ("TOTAL", "km"),
        "river_density": ("DENSITY", "km/km2"),
        "major_river_length": ("TOTAL", "km"),
        "distance_centroid_to_major_river": ("DISTANCE", "km"),
        "max_strahler_order": ("DISTRICT_MAX", "Strahler order"),
        "max_discharge": ("DISTRICT_MAX", "m3/s"),
    }
    for _, record in table.iterrows():
        district = lookup.loc[int(record["districtLgd"])].copy()
        district["districtLgd"] = int(record["districtLgd"])
        for variable, (stat, unit) in units.items():
            value = record[variable]
            rows.add(
                district,
                variable,
                "",
                stat,
                None if pd.isna(value) else float(value),
                unit=unit,
                pixels=record["reaches"],
            )
    return Result(HYDRORIVERS, rows.frame(), failures=failures)
