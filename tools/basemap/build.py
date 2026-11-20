from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pyogrio
import shapely

from .geometry import Basemap, Bounds, basemap, clipped, india_outline, line_parts, polygon_rings
from .polyline import encode_records, encode_ring, india_payload

__all__ = ["DATASETS", "Datasets", "build", "rann_module", "render"]

BOUNDS: Bounds = (64.7, 5.3, 98.5, 37.9)
TOLERANCE = 0.012
RANN_NAME = "Rann of Kutch"
SITE = "https://www.naturalearthdata.com"
DOWNLOADS = "https://naciscdn.org/naturalearth/10m"
DATASETS = {
    "countries": ("cultural", "ne_10m_admin_0_countries_ind"),
    "playas": ("physical", "ne_10m_playas"),
}


@dataclass(frozen=True)
class Datasets:
    folder: Path

    def shapefile(self, key: str) -> Path:
        name = DATASETS[key][1]
        return self.folder / name / f"{name}.shp"

    def version(self, key: str) -> str:
        name = DATASETS[key][1]
        return (self.folder / name / f"{name}.VERSION.txt").read_text(encoding="utf-8").strip()

    def digest(self, key: str) -> str:
        archive = self.folder / f"{DATASETS[key][1]}.zip"
        return hashlib.sha256(archive.read_bytes()).hexdigest()


def _countries(datasets: Datasets) -> tuple[dict[str, Any], dict[str, str]]:
    frame = pyogrio.read_dataframe(datasets.shapefile("countries"), columns=["ADM0_A3", "NAME"], bbox=BOUNDS)
    shapes: dict[str, Any] = {}
    names: dict[str, str] = {}
    for code, name, geometry in zip(frame["ADM0_A3"], frame["NAME"], frame.geometry, strict=True):
        shape = clipped(geometry, BOUNDS)
        if not shape.is_empty:
            shapes[code] = shapely.union(shapes[code], shape) if code in shapes else shape
            names[code] = name
    return shapes, names


def _rann(datasets: Datasets) -> Any:
    frame = pyogrio.read_dataframe(datasets.shapefile("playas"), columns=["name"], bbox=BOUNDS)
    found = [
        geometry for name, geometry in zip(frame["name"], frame.geometry, strict=True) if name == RANN_NAME
    ]
    if not found:
        raise ValueError(f"{RANN_NAME} is not in the playas dataset")
    return clipped(shapely.unary_union(found), BOUNDS)


def build(datasets: Datasets, india_source: str) -> tuple[Basemap, dict[str, str]]:
    countries, names = _countries(datasets)
    india = india_outline(india_payload(india_source))
    return basemap(countries, india, _rann(datasets), TOLERANCE), names


def _source(datasets: Datasets) -> list[dict[str, str]]:
    return [
        {
            "dataset": name,
            "version": datasets.version(key),
            "url": f"{DOWNLOADS}/{theme}/{name}.zip",
            "sha256": datasets.digest(key),
        }
        for key, (theme, name) in DATASETS.items()
    ]


def _countries_body(built: Basemap, names: dict[str, str]) -> list[dict[str, Any]]:
    countries = []
    for code, shape in sorted(built.countries.items()):
        rings = [encode_ring(ring) for ring in polygon_rings(shape)]
        if rings:
            countries.append({"iso": code, "name": names[code], "rings": rings})
    return countries


def rann_module(rings: list[str], version: str) -> str:
    name = DATASETS["playas"][1]
    entries = [f"  {json.dumps(ring)}{',' if at < len(rings) - 1 else ''}" for at, ring in enumerate(rings)]
    lines = [
        f'export const RANN_SOURCE = "Natural Earth 1:10m {name} {version}, {RANN_NAME}";',
        "",
        "export const RANN_RINGS: readonly string[] = [",
        *entries,
        "];",
    ]
    return "\n".join(lines) + "\n"


def render(datasets: Datasets, india_source: str) -> tuple[str, str]:
    built, names = build(datasets, india_source)
    body = {
        "source": "Natural Earth 1:10m admin-0 countries from India's point of view, fitted to the Survey of India outline",
        "site": SITE,
        "licence": "Public domain",
        "datasets": _source(datasets),
        "scale": 1000,
        "tolerance": TOLERANCE,
        "bounds": list(BOUNDS),
        "countries": _countries_body(built, names),
        "coast": encode_records(list(line_parts(built.coast, BOUNDS))),
        "borders": encode_records(list(line_parts(built.borders, BOUNDS))),
    }
    rann = [encode_ring(ring) for ring in polygon_rings(built.rann)]
    text = json.dumps(body, ensure_ascii=False, separators=(",", ":")) + "\n"
    return text, rann_module(rann, datasets.version("playas"))
