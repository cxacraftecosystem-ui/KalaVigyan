from __future__ import annotations

import math
from collections.abc import Iterable

import shapely
from shapely.geometry import LineString, MultiLineString, box
from shapely.geometry.base import BaseGeometry

from basemap.geometry import india_outline, polygon_rings
from basemap.polyline import encode_records, encode_ring, india_payload

__all__ = [
    "MID_LATITUDE",
    "encoded_lines",
    "encoded_rings",
    "geographic",
    "india",
    "lines_of",
    "rings_of",
    "screen",
]

MID_LATITUDE = (6.756 + 37.082) / 2
LONGITUDE_SCALE = math.cos(math.radians(MID_LATITUDE))


def screen(longitude: float, latitude: float) -> tuple[float, float]:
    return longitude * LONGITUDE_SCALE, -latitude


def geographic(x: float, y: float) -> tuple[float, float]:
    return round(x / LONGITUDE_SCALE, 3), round(-y, 3)


def india(source: str) -> BaseGeometry:
    return india_outline(india_payload(source))


def lines_of(geometry: BaseGeometry) -> list[LineString]:
    if geometry.is_empty:
        return []
    if isinstance(geometry, LineString):
        return [geometry]
    if isinstance(geometry, MultiLineString):
        return list(geometry.geoms)
    return [part for item in getattr(geometry, "geoms", []) for part in lines_of(item)]


def rings_of(geometry: BaseGeometry) -> list[list[tuple[float, float]]]:
    return list(polygon_rings(geometry))


def encoded_lines(
    lines: Iterable[LineString], bounds: tuple[float, float, float, float], tolerance: float
) -> str:
    frame = box(*bounds)
    kept: list[list[tuple[float, float]]] = []
    for line in lines:
        clipped = shapely.intersection(shapely.simplify(line, tolerance), frame)
        kept.extend(list(part.coords) for part in lines_of(clipped) if len(part.coords) >= 2)
    return encode_records(kept)


def encoded_rings(geometry: BaseGeometry) -> list[str]:
    return [encode_ring(ring) for ring in rings_of(geometry)]
