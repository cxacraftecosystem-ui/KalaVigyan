import json
import re
import subprocess
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from pathlib import Path

import geopandas as gpd
from shapely.geometry import shape

from geo_etl.catalog import OSM_RIVER_NAMES
from geo_etl.districts import sha256_of
from geo_etl.layers import download

EXTRACT = "india-latest.osm.pbf"
FILTERED = "india-rivers.osm.pbf"
EXPORTED = "india-rivers.geojsonseq"
WAY_FILTER = "w/waterway=river"
LATIN = re.compile(r"^[A-Za-z][A-Za-z .'()-]*$")
RECORD_SEPARATOR = "\x1e"
WAY_COLUMNS = ["osmWay", "name", "geometry"]


@dataclass(frozen=True)
class OsmWays:
    ways: gpd.GeoDataFrame
    sha256: str


def fetch_ways(cache: Path) -> OsmWays:
    folder = cache / "osm"
    extract = download(OSM_RIVER_NAMES.url, folder / EXTRACT)
    exported = export_rivers(extract, folder)
    return OsmWays(ways=read_ways(exported), sha256=sha256_of(extract))


def export_rivers(extract: Path, folder: Path) -> Path:
    filtered, exported = folder / FILTERED, folder / EXPORTED
    subprocess.run(["osmium", "tags-filter", str(extract), WAY_FILTER, "-o", str(filtered), "--overwrite"], check=True)
    subprocess.run(
        [
            "osmium",
            "export",
            str(filtered),
            "-o",
            str(exported),
            "-f",
            "geojsonseq",
            "--geometry-types=linestring",
            "--add-unique-id=type_id",
            "--overwrite",
        ],
        check=True,
    )
    return exported


def read_ways(exported: Path) -> gpd.GeoDataFrame:
    with exported.open(encoding="utf-8") as handle:
        rows = list(named_ways(handle))
    return gpd.GeoDataFrame(rows, columns=WAY_COLUMNS, geometry="geometry", crs="EPSG:4326")


def named_ways(lines: Iterable[str]) -> Iterator[dict]:
    for line in lines:
        text = line.strip().lstrip(RECORD_SEPARATOR)
        if not text:
            continue
        feature = json.loads(text)
        name = shown_name(feature.get("properties") or {})
        way = way_id(str(feature.get("id", "")))
        geometry = feature.get("geometry") or {}
        if name and way and geometry.get("type") == "LineString":
            yield {"osmWay": way, "name": name, "geometry": shape(geometry)}


def shown_name(tags: dict) -> str | None:
    for key in ("name:en", "name"):
        value = str(tags.get(key) or "").strip()
        if LATIN.match(value):
            return value
    return None


def way_id(value: str) -> int | None:
    return int(value[1:]) if value[:1] == "w" and value[1:].isdigit() else None
