import dataclasses
import datetime as dt
import json
from collections import Counter
from collections.abc import Callable
from pathlib import Path

import geopandas as gpd
import pandas as pd

from geo_etl.catalog import HYDRORIVERS, OSM_RIVER_NAMES, WIKIDATA_RIVER_NAMES, Dataset
from geo_etl.osm_rivers import WAY_FILTER, OsmWays, fetch_ways
from geo_etl.river_districts import REACH_DISTRICTS_FILE, districts_by_reach
from geo_etl.river_names import AREA_RATIO, MOUTH_KM, SOURCE_KM, wikidata_matches, wikidata_rivers
from geo_etl.river_names_osm import NEAR_M, SAMPLE_M, SHARE_MIN, osm_names, osm_rivers
from geo_etl.river_network import network_of
from geo_etl.rivers import REACHES_FILE
from geo_etl.wikidata_rivers import Ask, fetch_rivers

SCHEMA_VERSION = 1
WIKIDATA_FILE = "river_names.wikidata.json"
OSM_FILE = "river_names.osm.json"
SUMMARY_FILE = "river_names_summary.json"
BOUNDS_MARGIN_DEGREES = 0.5
WIKIDATA_RULES = {"mouthKm": MOUTH_KM, "sourceKm": SOURCE_KM, "areaRatio": AREA_RATIO}
OSM_RULES = {"wayFilter": WAY_FILTER, "sampleM": SAMPLE_M, "nearM": NEAR_M, "shareMin": SHARE_MIN}


def build_names(
    rivers: Path, *, scratch: Path, ask: Ask | None = None, ways: Callable[[Path], OsmWays] = fetch_ways
) -> dict:
    reaches = gpd.read_parquet(rivers / REACHES_FILE)
    districts_of = districts_by_reach(pd.read_parquet(rivers / REACH_DISTRICTS_FILE))
    network = network_of(reaches)
    answer = fetch_rivers(padded_bounds(reaches), ask)
    wikidata_at = dt.datetime.now(dt.UTC)
    matches = wikidata_matches(network, answer.rivers)
    named = wikidata_rivers(network, matches.courses, districts_of)
    taken = {reach for river in named for reach in river["reachIds"]}
    found = ways(scratch)
    osm_at = dt.datetime.now(dt.UTC)
    filled = osm_rivers(network, osm_names(reaches, found.ways, taken), districts_of)
    write_names(
        rivers / WIKIDATA_FILE, name_file(WIKIDATA_RIVER_NAMES, wikidata_at, answer.sha256, named, WIKIDATA_RULES)
    )
    write_names(rivers / OSM_FILE, name_file(OSM_RIVER_NAMES, osm_at, found.sha256, filled, OSM_RULES))
    summary = {
        "wikidataItems": len(answer.rivers),
        "wikidataRivers": len(named),
        "wikidataReaches": len(taken),
        "wikidataRefused": dict(sorted(Counter(matches.refused.values()).items())),
        "osmWays": int(len(found.ways)),
        "osmRivers": len(filled),
        "osmReaches": sum(len(river["reachIds"]) for river in filled),
        "reaches": int(len(reaches)),
    }
    (rivers / SUMMARY_FILE).write_text(json.dumps(summary, indent=1) + "\n", encoding="utf-8")
    return summary


def padded_bounds(reaches: gpd.GeoDataFrame) -> tuple[float, float, float, float]:
    west, south, east, north = (float(value) for value in reaches.total_bounds)
    pad = BOUNDS_MARGIN_DEGREES
    return west - pad, south - pad, east + pad, north + pad


def name_file(dataset: Dataset, retrieved_at: dt.datetime, sha256: str, rivers: list[dict], rules: dict) -> dict:
    read_on = retrieved_at.date().isoformat()
    row = dataclasses.replace(dataset, edition=read_on, period=read_on).as_row()
    return {
        "schemaVersion": SCHEMA_VERSION,
        "dataset": row | {"retrievedAt": retrieved_at.isoformat(timespec="seconds"), "sha256": sha256},
        "hydrorivers": {"code": HYDRORIVERS.code, "edition": HYDRORIVERS.edition},
        "rules": rules,
        "rivers": rivers,
    }


def write_names(path: Path, body: dict) -> None:
    head = json.dumps({key: value for key, value in body.items() if key != "rivers"}, indent=1, ensure_ascii=False)
    rows = ",\n".join("  " + json.dumps(river, ensure_ascii=False) for river in body["rivers"])
    path.write_text(head[:-2] + ',\n "rivers": [\n' + rows + "\n ]\n}\n", encoding="utf-8", newline="\n")
