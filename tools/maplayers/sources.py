from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

__all__ = [
    "BOUNDS",
    "BREAKS",
    "ETOPO",
    "MRDS",
    "NATURAL_EARTH",
    "NATURAL_EARTH_SITE",
    "Downloads",
    "Source",
    "digest",
]

BOUNDS = (64.7, 5.3, 98.5, 37.9)
BREAKS = (100, 300, 600, 1000, 2000, 4000)
NATURAL_EARTH_SITE = "https://www.naturalearthdata.com"
NATURAL_EARTH_DOWNLOADS = "https://naciscdn.org/naturalearth/10m"
NATURAL_EARTH = {
    "rivers": ("physical", "ne_10m_rivers_lake_centerlines"),
    "lakes": ("physical", "ne_10m_lakes"),
    "regions": ("physical", "ne_10m_geography_regions_polys"),
    "peaks": ("physical", "ne_10m_geography_regions_elevation_points"),
}


@dataclass(frozen=True)
class Source:
    file: str
    title: str
    publisher: str
    url: str
    licence: str
    citation: str


ETOPO = Source(
    file="etopo1_india.asc",
    title="ETOPO1 1 Arc-Minute Global Relief Model, ice surface",
    publisher="NOAA National Centers for Environmental Information",
    url=(
        "https://coastwatch.pfeg.noaa.gov/erddap/griddap/etopo180.esriAscii"
        "?altitude%5B(37.6):1:(5.6)%5D%5B(65):1:(98.2)%5D"
    ),
    licence="Public domain (U.S. Government work)",
    citation=(
        "Amante, C. and B.W. Eakins, 2009. ETOPO1 1 Arc-Minute Global Relief Model: Procedures, Data Sources "
        "and Analysis. NOAA Technical Memorandum NESDIS NGDC-24. https://doi.org/10.7289/V5C8276M"
    ),
)

MRDS = Source(
    file="mrds-csv.zip",
    title="Mineral Resources Data System",
    publisher="U.S. Geological Survey",
    url="https://mrdata.usgs.gov/mrds/mrds-csv.zip",
    licence="Public domain (U.S. Government work)",
    citation="U.S. Geological Survey. Mineral Resources Data System (MRDS). Reston, Virginia. https://mrdata.usgs.gov/mrds/",
)


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


@dataclass(frozen=True)
class Downloads:
    folder: Path

    def shapefile(self, key: str) -> Path:
        name = NATURAL_EARTH[key][1]
        return self.folder / name / f"{name}.shp"

    def natural_earth(self, key: str) -> dict[str, str]:
        theme, name = NATURAL_EARTH[key]
        version = (self.folder / name / f"{name}.VERSION.txt").read_text(encoding="utf-8").strip()
        return {
            "dataset": name,
            "version": version,
            "url": f"{NATURAL_EARTH_DOWNLOADS}/{theme}/{name}.zip",
            "sha256": digest(self.folder / f"{name}.zip"),
        }

    def source(self, source: Source) -> dict[str, str]:
        return {
            "dataset": source.title,
            "publisher": source.publisher,
            "url": source.url,
            "licence": source.licence,
            "citation": source.citation,
            "sha256": digest(self.folder / source.file),
        }
