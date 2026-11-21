from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import date
from functools import cache
from pathlib import Path
from typing import Any

__all__ = [
    "BOUNDS",
    "BREAKS",
    "ETOPO",
    "MRDS",
    "NATURAL_EARTH",
    "NATURAL_EARTH_CODE",
    "NATURAL_EARTH_SITE",
    "REGISTRY",
    "Downloads",
    "Source",
    "digest",
    "record",
]

BOUNDS = (64.7, 5.3, 98.5, 37.9)
BREAKS = (100, 300, 600, 1000, 2000, 4000)
REGISTRY = Path(__file__).resolve().parents[2] / "backend" / "app" / "data" / "datasets" / "registry.json"
NATURAL_EARTH_CODE = "NATURAL_EARTH_10M_PHYSICAL"
NATURAL_EARTH_SITE = "https://www.naturalearthdata.com"
NATURAL_EARTH_DOWNLOADS = "https://naciscdn.org/naturalearth/10m"
NATURAL_EARTH = {
    "rivers": ("physical", "ne_10m_rivers_lake_centerlines"),
    "lakes": ("physical", "ne_10m_lakes"),
    "regions": ("physical", "ne_10m_geography_regions_polys"),
    "peaks": ("physical", "ne_10m_geography_regions_elevation_points"),
}
SHOWN_FIELDS = (
    "code",
    "title",
    "publisher",
    "edition",
    "version",
    "period",
    "nativeResolution",
    "crs",
    "licence",
    "licenceUrl",
    "attribution",
    "redistributable",
    "citation",
    "doi",
    "landingUrl",
)


@dataclass(frozen=True)
class Source:
    code: str
    file: str
    url: str


ETOPO = Source(
    code="ETOPO1_ICE",
    file="etopo1_india.asc",
    url=(
        "https://coastwatch.pfeg.noaa.gov/erddap/griddap/etopo180.esriAscii"
        "?altitude%5B(37.6):1:(5.6)%5D%5B(65):1:(98.2)%5D"
    ),
)

MRDS = Source(code="USGS_MRDS", file="mrds-csv.zip", url="https://mrdata.usgs.gov/mrds/mrds-csv.zip")


@cache
def _registry(path: Path = REGISTRY) -> dict[str, dict[str, Any]]:
    body = json.loads(path.read_text(encoding="utf-8"))
    return {entry["code"]: entry for entry in body["datasets"]}


def record(code: str) -> dict[str, Any]:
    entry = _registry()[code]
    return {field: entry[field] for field in SHOWN_FIELDS}


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


@dataclass(frozen=True)
class Downloads:
    folder: Path
    read_on: date = field(default_factory=date.today)

    def shapefile(self, key: str) -> Path:
        name = NATURAL_EARTH[key][1]
        return self.folder / name / f"{name}.shp"

    def natural_earth(self, key: str) -> dict[str, Any]:
        theme, name = NATURAL_EARTH[key]
        version = (self.folder / name / f"{name}.VERSION.txt").read_text(encoding="utf-8").strip()
        return record(NATURAL_EARTH_CODE) | {
            "version": version,
            "file": name,
            "url": f"{NATURAL_EARTH_DOWNLOADS}/{theme}/{name}.zip",
            "readOn": self.read_on.isoformat(),
            "sha256": digest(self.folder / f"{name}.zip"),
        }

    def source(self, source: Source) -> dict[str, Any]:
        return record(source.code) | {
            "file": source.file,
            "url": source.url,
            "readOn": self.read_on.isoformat(),
            "sha256": digest(self.folder / source.file),
        }
