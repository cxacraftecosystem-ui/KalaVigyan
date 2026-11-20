from __future__ import annotations

from collections import defaultdict
from typing import Any

import pyogrio
import shapely
from shapely.geometry import box
from shapely.geometry.base import BaseGeometry

from .geo import encoded_lines, encoded_rings, geographic, lines_of, screen
from .labels import RIVERS, line_label
from .sources import BOUNDS, Downloads

__all__ = ["rivers_body"]

TOLERANCE = 0.01
LAKE_TOLERANCE = 0.006
LAKE_MIN_AREA = 0.004
LABEL_REACH = 0.6


def _frame(downloads: Downloads, key: str, columns: list[str]) -> Any:
    return pyogrio.read_dataframe(downloads.shapefile(key), columns=columns, bbox=BOUNDS)


def _by_rank(frame: Any) -> list[dict[str, Any]]:
    groups: dict[int, list[Any]] = defaultdict(list)
    for rank, geometry in zip(frame["scalerank"], frame.geometry, strict=True):
        groups[int(rank)].extend(lines_of(geometry))
    return [
        {"rank": rank, "lines": encoded_lines(lines, BOUNDS, TOLERANCE)}
        for rank, lines in sorted(groups.items())
    ]


def _label(name: str, geometry: BaseGeometry, india: BaseGeometry) -> dict[str, Any] | None:
    text, tier, share = RIVERS[name]
    inside = lines_of(shapely.intersection(geometry, india)) or lines_of(geometry)
    parts = lines_of(shapely.line_merge(shapely.union_all(inside)))
    if not parts:
        return None
    longest = max(parts, key=lambda part: part.length)
    points = [screen(x, y) for x, y in longest.coords]
    x, y, angle = line_label(points, share, LABEL_REACH)
    longitude, latitude = geographic(x, y)
    return {"text": text, "tier": tier, "longitude": longitude, "latitude": latitude, "angle": angle}


def _labels(frame: Any, india: BaseGeometry) -> list[dict[str, Any]]:
    named: dict[str, list[Any]] = defaultdict(list)
    for name, geometry in zip(frame["name_en"], frame.geometry, strict=True):
        if isinstance(name, str) and name in RIVERS:
            named[name].extend(lines_of(geometry))
    labels = [_label(name, shapely.union_all(lines), india) for name, lines in named.items()]
    return sorted((label for label in labels if label), key=lambda label: (label["tier"], label["text"]))


def _lakes(downloads: Downloads) -> list[str]:
    frame = _frame(downloads, "lakes", ["name", "scalerank"])
    shapes = [shapely.intersection(geometry, box(*BOUNDS)) for geometry in frame.geometry]
    kept = [shapely.simplify(shape, LAKE_TOLERANCE) for shape in shapes if shape.area >= LAKE_MIN_AREA]
    return encoded_rings(shapely.union_all(kept)) if kept else []


def rivers_body(downloads: Downloads, india: BaseGeometry) -> dict[str, Any]:
    frame = _frame(downloads, "rivers", ["name_en", "scalerank", "featurecla"])
    return {
        "source": "Natural Earth 1:10m rivers and lake centrelines, with its lakes and reservoirs",
        "site": "https://www.naturalearthdata.com",
        "licence": "Public domain",
        "datasets": [downloads.natural_earth("rivers"), downloads.natural_earth("lakes")],
        "bounds": list(BOUNDS),
        "ranks": _by_rank(frame),
        "lakes": _lakes(downloads),
        "labels": _labels(frame, india),
    }
