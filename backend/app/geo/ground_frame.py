from __future__ import annotations

import math
from collections.abc import Callable, Iterable, Sequence
from itertools import pairwise

from app.research.why_here import FrameBand, FrameLabel, FrameLine, GroundFrame

from .ground_layers import GroundLayers, Line
from .ground_measure import KM_PER_DEGREE

__all__ = [
    "ASPECT_MAX",
    "ASPECT_MIN",
    "clip_line",
    "clip_ring",
    "framed",
    "place_box",
    "thinned",
]

ASPECT_MIN = 1.0
ASPECT_MAX = 1.8
MARGIN_SHARE = 0.08
STEPS_ACROSS = 640
PLACES = 3

Point = tuple[float, float]
Box = tuple[float, float, float, float]
Edge = Callable[[Point], bool]


def _squeeze(latitude: float) -> float:
    return max(math.cos(math.radians(latitude)), 1e-6)


def place_box(points: Sequence[Point], reach_km: float) -> Box:
    middle = (min(p[1] for p in points) + max(p[1] for p in points)) / 2
    north_south = reach_km / KM_PER_DEGREE
    east_west = north_south / _squeeze(middle)
    west = min(p[0] for p in points) - east_west
    east = max(p[0] for p in points) + east_west
    south = min(p[1] for p in points) - north_south
    north = max(p[1] for p in points) + north_south
    return _shaped((west, south, east, north))


def _shaped(box: Box) -> Box:
    west, south, east, north = box
    squeeze = _squeeze((south + north) / 2)
    wide, tall = (east - west) * squeeze, north - south
    if wide < tall * ASPECT_MIN:
        grow = (tall * ASPECT_MIN - wide) / squeeze / 2
        west, east = west - grow, east + grow
    elif wide > tall * ASPECT_MAX:
        grow = (wide / ASPECT_MAX - tall) / 2
        south, north = south - grow, north + grow
    pad_x = (east - west) * MARGIN_SHARE
    pad_y = (north - south) * MARGIN_SHARE
    return (
        round(west - pad_x, PLACES),
        round(south - pad_y, PLACES),
        round(east + pad_x, PLACES),
        round(north + pad_y, PLACES),
    )


def _cut(a: Point, b: Point, axis: int, value: float) -> Point:
    share = (value - a[axis]) / (b[axis] - a[axis])
    other = 1 - axis
    found = [0.0, 0.0]
    found[axis] = value
    found[other] = a[other] + (b[other] - a[other]) * share
    return found[0], found[1]


def _edges(box: Box) -> list[tuple[int, float, Edge]]:
    west, south, east, north = box
    return [
        (0, west, lambda p: p[0] >= west),
        (0, east, lambda p: p[0] <= east),
        (1, south, lambda p: p[1] >= south),
        (1, north, lambda p: p[1] <= north),
    ]


def clip_ring(ring: Sequence[Point], box: Box) -> list[Point]:
    kept = list(ring)
    for axis, value, keeps in _edges(box):
        if not kept:
            break
        given, kept = kept, []
        for a, b in zip([given[-1], *given[:-1]], given, strict=True):
            if keeps(b):
                if not keeps(a):
                    kept.append(_cut(a, b, axis, value))
                kept.append(b)
            elif keeps(a):
                kept.append(_cut(a, b, axis, value))
    return kept


def _inside(point: Point, box: Box) -> bool:
    west, south, east, north = box
    return west <= point[0] <= east and south <= point[1] <= north


def _segment(a: Point, b: Point, box: Box) -> tuple[Point, Point] | None:
    low, high = 0.0, 1.0
    dx, dy = b[0] - a[0], b[1] - a[1]
    west, south, east, north = box
    for step, room in ((-dx, a[0] - west), (dx, east - a[0]), (-dy, a[1] - south), (dy, north - a[1])):
        if step == 0:
            if room < 0:
                return None
            continue
        share = room / step
        if step < 0:
            low = max(low, share)
        else:
            high = min(high, share)
        if low > high:
            return None
    return (a[0] + dx * low, a[1] + dy * low), (a[0] + dx * high, a[1] + dy * high)


def clip_line(points: Sequence[Point], box: Box) -> list[list[Point]]:
    runs: list[list[Point]] = []
    for a, b in pairwise(points):
        piece = _segment(a, b, box)
        if piece is None:
            continue
        start, end = piece
        if runs and runs[-1][-1] == start:
            runs[-1].append(end)
        else:
            runs.append([start, end])
    return runs


def thinned(points: Sequence[Point], step: float, closed: bool) -> list[Point]:
    if not points:
        return []
    kept = [points[0]]
    for point in points[1:-1]:
        if abs(point[0] - kept[-1][0]) >= step or abs(point[1] - kept[-1][1]) >= step:
            kept.append(point)
    if len(points) > 1:
        kept.append(points[-1])
    least = 3 if closed else 2
    return [(round(x, PLACES), round(y, PLACES)) for x, y in kept] if len(kept) >= least else []


def _touches(line: Line, box: Box) -> bool:
    west, south, east, north = box
    a, b, c, d = line.box
    return a <= east and c >= west and b <= north and d >= south


def _rings(rings: Iterable[Line], box: Box, step: float) -> list[list[Point]]:
    clipped = (
        thinned(clip_ring(ring.points, box), step, closed=True) for ring in rings if _touches(ring, box)
    )
    return [ring for ring in clipped if ring]


def _lines(lines: Iterable[Line], box: Box, step: float) -> list[FrameLine]:
    found = []
    for line in lines:
        if not _touches(line, box):
            continue
        for run in clip_line(line.points, box):
            points = thinned(run, step, closed=False)
            if points:
                found.append(FrameLine(rank=line.rank, points=points))
    return found


def framed(layers: GroundLayers, box: Box) -> GroundFrame:
    west, south, east, north = box
    step = max(east - west, north - south) / STEPS_ACROSS
    bands = [FrameBand(low_m=band.low_m, rings=_rings(band.rings, box, step)) for band in layers.bands]
    labels = [
        FrameLabel(text=label.text, longitude=label.longitude, latitude=label.latitude, angle=label.angle)
        for label in layers.labels
        if _inside((label.longitude, label.latitude), box)
    ]
    return GroundFrame(
        west=west,
        south=south,
        east=east,
        north=north,
        bands=[band for band in bands if band.rings],
        rivers=_lines(layers.rivers, box, step),
        lakes=_rings(layers.lakes, box, step),
        labels=labels,
    )
