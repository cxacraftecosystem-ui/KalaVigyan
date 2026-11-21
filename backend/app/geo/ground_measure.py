from __future__ import annotations

import math
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from itertools import pairwise

from .ground_layers import Band, Deposit, Line

__all__ = [
    "EARTH_RADIUS_KM",
    "KM_PER_DEGREE",
    "Nearest",
    "elevation_band",
    "haversine_km",
    "inside",
    "nearest_lake",
    "nearest_line",
    "within",
]

EARTH_RADIUS_KM = 6371.0088
KM_PER_DEGREE = math.pi * EARTH_RADIUS_KM / 180

Point = tuple[float, float]


@dataclass(frozen=True)
class Nearest:
    distance_km: float
    at: Point
    rank: int


def haversine_km(a: Point, b: Point) -> float:
    lon1, lat1, lon2, lat2 = (math.radians(value) for value in (*a, *b))
    rise = math.sin((lat2 - lat1) / 2) ** 2
    turn = math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
    return 2 * EARTH_RADIUS_KM * math.asin(min(1.0, math.sqrt(rise + turn)))


def _xy(origin: Point, point: Point) -> tuple[float, float]:
    squeeze = math.cos(math.radians(origin[1]))
    return (point[0] - origin[0]) * squeeze * KM_PER_DEGREE, (point[1] - origin[1]) * KM_PER_DEGREE


def _closest(origin: Point, a: Point, b: Point) -> Point:
    ax, ay = _xy(origin, a)
    bx, by = _xy(origin, b)
    dx, dy = bx - ax, by - ay
    length = dx * dx + dy * dy
    share = 0.0 if length == 0 else max(0.0, min(1.0, -(ax * dx + ay * dy) / length))
    return a[0] + (b[0] - a[0]) * share, a[1] + (b[1] - a[1]) * share


def _box_km(origin: Point, line: Line) -> float:
    west, south, east, north = line.box
    longitude = min(max(origin[0], west), east)
    latitude = min(max(origin[1], south), north)
    return math.hypot(*_xy(origin, (longitude, latitude)))


def _segments(line: Line, closed: bool) -> Iterable[tuple[Point, Point]]:
    points = line.points
    yield from pairwise(points)
    if closed and len(points) > 2:
        yield points[-1], points[0]


def _nearest(origin: Point, lines: Sequence[Line], closed: bool) -> Nearest | None:
    best: Nearest | None = None
    for line in lines:
        if best is not None and _box_km(origin, line) >= best.distance_km:
            continue
        for a, b in _segments(line, closed):
            at = _closest(origin, a, b)
            distance = math.hypot(*_xy(origin, at))
            if best is None or distance < best.distance_km:
                best = Nearest(distance_km=distance, at=at, rank=line.rank)
    if best is None:
        return None
    return Nearest(distance_km=haversine_km(origin, best.at), at=best.at, rank=best.rank)


def nearest_line(origin: Point, lines: Sequence[Line]) -> Nearest | None:
    return _nearest(origin, lines, closed=False)


def _crosses(origin: Point, ring: Line) -> int:
    west, south, _, north = ring.box
    x, y = origin
    if not (south <= y <= north) or x < west:
        return 0
    found = 0
    for (x1, y1), (x2, y2) in _segments(ring, closed=True):
        if (y1 > y) != (y2 > y) and x < x1 + (y - y1) * (x2 - x1) / (y2 - y1):
            found += 1
    return found


def inside(origin: Point, rings: Iterable[Line]) -> bool:
    return sum(_crosses(origin, ring) for ring in rings) % 2 == 1


def nearest_lake(origin: Point, lakes: Sequence[Line]) -> Nearest | None:
    if inside(origin, lakes):
        return Nearest(distance_km=0.0, at=origin, rank=0)
    return _nearest(origin, lakes, closed=True)


def elevation_band(
    origin: Point, bands: Sequence[Band], breaks: Sequence[int]
) -> tuple[int | None, int | None]:
    reached = [band.low_m for band in bands if inside(origin, band.rings)]
    if not reached:
        return None, breaks[0]
    low = max(reached)
    above = [value for value in breaks if value > low]
    return low, (above[0] if above else None)


def within(origin: Point, deposits: Iterable[Deposit], radius_km: float) -> list[tuple[Deposit, float]]:
    reach = radius_km / KM_PER_DEGREE
    squeeze = max(math.cos(math.radians(origin[1])), 1e-6)
    found = []
    for deposit in deposits:
        if abs(deposit.latitude - origin[1]) > reach or abs(deposit.longitude - origin[0]) > reach / squeeze:
            continue
        distance = haversine_km(origin, (deposit.longitude, deposit.latitude))
        if distance <= radius_km:
            found.append((deposit, distance))
    return sorted(found, key=lambda item: (item[1], item[0].dep_id))
