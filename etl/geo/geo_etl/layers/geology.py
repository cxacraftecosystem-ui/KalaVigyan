import json
from collections import Counter

import geopandas as gpd
import numpy as np
import pandas as pd
import requests
from defusedxml import ElementTree
from rasterio.crs import CRS
from shapely.geometry import Point

from geo_etl import raster
from geo_etl.catalog import GLIM, MRDS
from geo_etl.layers import USER_AGENT, Measured, Options, Result, by_state, download, failure
from geo_etl.rows import Rows, pick

GEOLOGY_COLUMNS = [
    "districtLgd",
    "stateLgd",
    "districtName",
    "datasetCode",
    "lithology",
    "lithologyName",
    "areaShare",
    "mineralOccurrences",
    "method",
    "source",
    "version",
    "resolution",
    "licence",
]

NS = {"gml": "http://www.opengis.net/gml", "ms": "http://mapserver.gis.umn.edu/mapserver"}
MRDS_PAGE = 5000

GLIM_CLASSES = {
    1: ("su", "Unconsolidated sediments"),
    2: ("vb", "Basic volcanic rocks"),
    3: ("ss", "Siliciclastic sedimentary rocks"),
    4: ("pb", "Basic plutonic rocks"),
    5: ("sm", "Mixed sedimentary rocks"),
    6: ("sc", "Carbonate sedimentary rocks"),
    7: ("va", "Acid volcanic rocks"),
    8: ("mt", "Metamorphics"),
    9: ("pa", "Acid plutonic rocks"),
    10: ("vi", "Intermediate volcanic rocks"),
    11: ("wb", "Water bodies"),
    12: ("py", "Pyroclastics"),
    13: ("pi", "Intermediate plutonic rocks"),
    14: ("ev", "Evaporites"),
    15: ("nd", "No data"),
    16: ("ig", "Ice and glaciers"),
}


MRDS_LITHOLOGY = "mineral_occurrences"


def geology_row(district: pd.Series, dataset, method: str, **values) -> dict:
    return {
        "districtLgd": int(district["districtLgd"]),
        "stateLgd": int(district["stateLgd"]),
        "districtName": str(district["districtName"]),
        "datasetCode": dataset.code,
        "lithology": values.get("lithology"),
        "lithologyName": values.get("lithologyName"),
        "areaShare": values.get("areaShare"),
        "mineralOccurrences": values.get("mineralOccurrences"),
        "method": method,
        "source": dataset.title,
        "version": dataset.edition,
        "resolution": dataset.nativeResolution,
        "licence": dataset.licence,
    }


def parse_mrds(payload: bytes) -> list[dict]:
    root = ElementTree.fromstring(payload)
    out = []
    for member in root.iter("{http://www.opengis.net/gml}featureMember"):
        feature = member.find("ms:mrds", NS)
        if feature is None:
            continue
        coords = feature.findtext("ms:geometry/gml:Point/gml:coordinates", default="", namespaces=NS).strip()
        if not coords:
            continue
        lon, lat = (float(v) for v in coords.split(",")[:2])
        codes = (feature.findtext("ms:code_list", default="", namespaces=NS) or "").split()
        out.append(
            {
                "depId": (feature.findtext("ms:dep_id", default="", namespaces=NS) or "").strip(),
                "name": (feature.findtext("ms:site_name", default="", namespaces=NS) or "").strip(),
                "devStat": (feature.findtext("ms:dev_stat", default="", namespaces=NS) or "").strip(),
                "commodities": [c.upper() for c in codes],
                "url": (feature.findtext("ms:url", default="", namespaces=NS) or "").strip(),
                "lon": lon,
                "lat": lat,
            }
        )
    return out


def fetch_mrds(bounds: tuple[float, float, float, float]) -> list[dict]:
    xmin, ymin, xmax, ymax = bounds
    params = {
        "service": "WFS",
        "version": "1.0.0",
        "request": "GetFeature",
        "typeName": "mrds",
        "bbox": f"{xmin:.5f},{ymin:.5f},{xmax:.5f},{ymax:.5f}",
        "maxFeatures": str(MRDS_PAGE),
    }
    response = requests.get(MRDS.url, params=params, timeout=180, headers={"User-Agent": USER_AGENT})
    response.raise_for_status()
    points = parse_mrds(response.content)
    if len(points) >= MRDS_PAGE:
        raise RuntimeError(f"MRDS bbox {bounds} returned the page limit {MRDS_PAGE}; split the request")
    return points


def assign_points(group: gpd.GeoDataFrame, points: list[dict]) -> dict[int, list[dict]]:
    if not points:
        return {}
    frame = gpd.GeoDataFrame(points, geometry=[Point(p["lon"], p["lat"]) for p in points], crs="EPSG:4326")
    joined = gpd.sjoin(frame, group[["districtLgd", "geometry"]], predicate="within", how="inner")
    out: dict[int, list[dict]] = {}
    for _, row in joined.iterrows():
        out.setdefault(int(row["districtLgd"]), []).append({k: row[k] for k in points[0]})
    return out


def run_mrds(districts: gpd.GeoDataFrame, options: Options) -> Result:
    method = "USGS MRDS WFS points inside the district polygon (point-in-polygon, EPSG:4326)"
    rows = Rows(MRDS, method)
    geology: list[dict] = []
    failures: list[dict] = []
    for group in by_state(districts):
        try:
            xmin, ymin, xmax, ymax = group.total_bounds
            points = fetch_mrds((xmin - 0.01, ymin - 0.01, xmax + 0.01, ymax + 0.01))
            inside = assign_points(group, points)
            for _, district in group.iterrows():
                found = sorted(inside.get(int(district["districtLgd"]), []), key=lambda p: p["depId"])
                rows.add(district, "mineral_occurrences", "", "COUNT", float(len(found)), unit="sites")
                commodities = Counter(c for p in found for c in p["commodities"])
                for code, count in sorted(commodities.items()):
                    rows.add(district, f"mineral_occurrences_{code.lower()}", "", "COUNT", float(count), unit="sites")
                geology.append(
                    geology_row(
                        district,
                        MRDS,
                        method,
                        lithology=MRDS_LITHOLOGY,
                        lithologyName="Mineral occurrences",
                        mineralOccurrences=json.dumps(found),
                    )
                )
        except Exception as error:
            failures.append(failure(group, "mrds", error))
    return Result(MRDS, rows.frame(), geology=pd.DataFrame(geology, columns=GEOLOGY_COLUMNS), failures=failures)


def run_glim(districts: gpd.GeoDataFrame, options: Options) -> Result:
    method = (
        "exactextract class fractions, coverage weight area_spherical_km2, on the 0.5 degree GLiM grid; "
        "coarse: a district usually spans a few cells"
    )
    rows = Rows(GLIM, method)
    geology: list[dict] = []
    failures: list[dict] = []
    measured = Measured()
    try:
        archive = download(GLIM.url, options.cache / "glim" / "glim_wgs84_0point5deg.zip")
        source = f"/vsizip/{archive.as_posix()}/glim_wgs84_0point5deg.txt.asc"
        bounds = raster.bounds_in(districts, "EPSG:4326", 0.5)
        grid = raster.read([source], bounds, nodata_values=(0,), dtype="float32")
        if grid is None:
            raise RuntimeError("GLiM grid unreadable")
        grid = raster.Grid(grid.values, grid.transform, CRS.from_epsg(4326))
        table = measured.add(raster.zonal(grid, districts, raster.class_ops(grid)))
        lookup = districts.set_index("districtLgd")
        for _, record in table.iterrows():
            district = lookup.loc[int(record["districtLgd"])].copy()
            district["districtLgd"] = int(record["districtLgd"])
            classes = np.asarray(pick(record, "classes"), dtype=float)
            shares = np.asarray(pick(record, "shares"), dtype=float)
            pixels = record["pixels"]
            for value, share in sorted(zip(classes, shares, strict=True), key=lambda p: -p[1]):
                code, name = GLIM_CLASSES.get(int(value), (str(int(value)), "Unknown class"))
                geology.append(
                    geology_row(district, GLIM, method, lithology=code, lithologyName=name, areaShare=float(share))
                )
                rows.add(district, f"lithology_{code}", "", "SHARE", float(share), unit="fraction", pixels=pixels)
    except Exception as error:
        failures.append(failure(districts, "glim", error))
    return Result(
        GLIM,
        rows.frame(),
        geology=pd.DataFrame(geology, columns=GEOLOGY_COLUMNS),
        failures=failures,
        districts_without_cells=measured.without_cells(),
    )
