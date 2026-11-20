from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass

import shapely
from shapely.geometry import LineString, MultiLineString, MultiPolygon, Polygon, box
from shapely.geometry.base import BaseGeometry

from .polyline import decode_records

__all__ = ["Basemap", "Bounds", "basemap", "india_outline", "line_parts", "polygon_rings"]

Bounds = tuple[float, float, float, float]

REACH = 0.25
TUCK = 0.02
EDGE = 1e-6
SPECK = 0.002
MARSH = 0.3


@dataclass(frozen=True)
class Basemap:
    countries: dict[str, BaseGeometry]
    coast: BaseGeometry
    borders: BaseGeometry
    rann: BaseGeometry
    india: BaseGeometry


def india_outline(payload: str) -> BaseGeometry:
    polygons: list[list[list[tuple[float, float]]]] = []
    for hole, points in decode_records(payload, True):
        if hole and polygons:
            polygons[-1].append(points)
        else:
            polygons.append([points])
    shapes = [shapely.make_valid(Polygon(rings[0], rings[1:])) for rings in polygons if len(rings[0]) >= 3]
    return _areal(shapely.make_valid(shapely.unary_union(shapes)))


def _areal(geometry: BaseGeometry) -> BaseGeometry:
    parts = [
        part for part in getattr(geometry, "geoms", [geometry]) if isinstance(part, Polygon | MultiPolygon)
    ]
    return shapely.unary_union(parts) if parts else Polygon()


def _linear(geometry: BaseGeometry) -> BaseGeometry:
    parts = [
        part
        for part in getattr(geometry, "geoms", [geometry])
        if isinstance(part, LineString | MultiLineString)
    ]
    return shapely.line_merge(shapely.unary_union(parts)) if parts else LineString()


def _simplified(countries: Mapping[str, BaseGeometry], tolerance: float) -> dict[str, BaseGeometry]:
    keys = list(countries)
    shapes = shapely.coverage_simplify([countries[key] for key in keys], tolerance)
    return {key: _areal(shapely.make_valid(shape)) for key, shape in zip(keys, shapes, strict=True)}


def _drawn(country: BaseGeometry, slack: BaseGeometry, india: BaseGeometry) -> BaseGeometry:
    filled = shapely.union(country, shapely.intersection(slack, shapely.buffer(country, REACH)))
    tucked = shapely.intersection(shapely.buffer(country, TUCK), india)
    return _areal(shapely.make_valid(shapely.union(filled, tucked)))


def _borders(
    coverage: Mapping[str, BaseGeometry],
    drawn: Mapping[str, BaseGeometry],
    india: BaseGeometry,
    salt: BaseGeometry,
) -> BaseGeometry:
    keys = sorted(coverage)
    shared = [_linear(shapely.intersection(drawn[key].boundary, salt.boundary)) for key in keys]
    for at, first in enumerate(keys):
        for second in keys[at + 1 :]:
            meet = shapely.intersection(coverage[first].boundary, coverage[second].boundary)
            shared.append(_linear(meet))
    return _linear(shapely.difference(shapely.unary_union(shared), shapely.buffer(india, EDGE)))


def basemap(
    countries: Mapping[str, BaseGeometry], india: BaseGeometry, rann: BaseGeometry, tolerance: float
) -> Basemap:
    simplified = _simplified(countries, tolerance)
    india_ne = simplified.pop("IND")
    rann_s = _areal(shapely.intersection(shapely.simplify(rann, tolerance), shapely.union(india_ne, india)))
    slack = shapely.difference(india_ne, india)
    marsh = _areal(shapely.intersection(slack, shapely.buffer(rann_s, MARSH)))
    drawn = {key: _drawn(shape, shapely.difference(slack, marsh), india) for key, shape in simplified.items()}
    salt = _areal(shapely.make_valid(shapely.union(rann_s, marsh)))
    land = shapely.unary_union([*drawn.values(), india, salt])
    coast = _linear(shapely.difference(shapely.boundary(land), shapely.buffer(india, EDGE)))
    borders = _borders(simplified, drawn, india, salt)
    return Basemap(countries=drawn, coast=coast, borders=borders, rann=salt, india=india)


def clipped(geometry: BaseGeometry, bounds: Bounds) -> BaseGeometry:
    return _areal(shapely.make_valid(shapely.intersection(shapely.make_valid(geometry), box(*bounds))))


def polygon_rings(geometry: BaseGeometry) -> Iterable[list[tuple[float, float]]]:
    for polygon in getattr(geometry, "geoms", [geometry]):
        if polygon.is_empty or polygon.area < SPECK:
            continue
        yield list(polygon.exterior.coords)
        for interior in polygon.interiors:
            if Polygon(interior).area >= SPECK:
                yield list(interior.coords)


def line_parts(geometry: BaseGeometry, bounds: Bounds) -> Iterable[list[tuple[float, float]]]:
    edge = shapely.buffer(box(*bounds).boundary, EDGE * 10)
    inside = _linear(shapely.difference(geometry, edge))
    for line in getattr(inside, "geoms", [inside]):
        if not line.is_empty and len(line.coords) >= 2:
            yield list(line.coords)
