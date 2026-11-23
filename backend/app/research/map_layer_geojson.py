from __future__ import annotations

import json
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal
from itertools import pairwise
from types import MappingProxyType
from typing import Any

from .map_layer_proposals import INDIA_FRAME, Frame, MapLayerPlan, decimals_allowed

__all__ = [
    "FEATURES_MAX",
    "GEOMETRY_TYPES",
    "LAYER_BYTES_MAX",
    "LayerRefused",
    "ParsedLayer",
    "layer_bounds",
    "parsed_layer",
    "ring_area",
]

LAYER_BYTES_MAX = 5 * 1024 * 1024
FEATURES_MAX = 5000
GEOMETRY_TYPES: Mapping[str, tuple[str, ...]] = MappingProxyType(
    {
        "POINT": ("Point", "MultiPoint"),
        "LINE": ("LineString", "MultiLineString"),
        "SHAPE": ("Polygon", "MultiPolygon"),
    }
)
NESTING: Mapping[str, int] = MappingProxyType(
    {"Point": 0, "MultiPoint": 1, "LineString": 1, "MultiLineString": 2, "Polygon": 2, "MultiPolygon": 3}
)
LINE_POSITIONS_MIN = 2
RING_POSITIONS_MIN = 4
SINGLE_PARTS = ("Point", "LineString", "Polygon")
NOT_NESTED = "feature {number} has coordinates that are not nested as its geometry needs"
OPEN_RING = "feature {number} has a ring that is not closed or has under {least} positions"
POSITION_SIZES = (2, 3)
WGS84_CRS_NAMES = ("CRS84", "4326")


class LayerRefused(ValueError):
    pass


@dataclass(frozen=True)
class ParsedLayer:
    layer: dict[str, Any]
    features: int
    bounds: Frame


def parsed_layer(data: bytes, plan: MapLayerPlan) -> ParsedLayer:
    exact = _loaded(data)
    features = _features(exact)
    _check_crs(exact.get("crs"))
    for number, feature in enumerate(features, start=1):
        _check_feature(feature, plan, number)
    layer = json.loads(data)
    return ParsedLayer(layer=layer, features=len(features), bounds=layer_bounds(layer))


def layer_bounds(layer: Mapping[str, Any]) -> Frame:
    found = [
        (float(position[0]), float(position[1]))
        for number, feature in enumerate(layer["features"], start=1)
        for position in _positions(
            feature["geometry"]["coordinates"], NESTING[feature["geometry"]["type"]], number
        )
    ]
    longitudes = [longitude for longitude, _ in found]
    latitudes = [latitude for _, latitude in found]
    return Frame(west=min(longitudes), south=min(latitudes), east=max(longitudes), north=max(latitudes))


def ring_area(ring: Sequence[Sequence[Any]]) -> float:
    twice = sum(
        float(first[0]) * float(second[1]) - float(second[0]) * float(first[1])
        for first, second in pairwise(ring)
    )
    return abs(twice) / 2


def _loaded(data: bytes) -> dict[str, Any]:
    if not data or len(data) > LAYER_BYTES_MAX:
        raise LayerRefused(f"a layer is 1 byte to {LAYER_BYTES_MAX // (1024 * 1024)} MB of GeoJSON")
    try:
        loaded = json.loads(data.decode("utf-8"), parse_float=Decimal)
    except UnicodeDecodeError, ValueError:
        raise LayerRefused("a layer is a GeoJSON FeatureCollection in UTF-8 JSON") from None
    if not isinstance(loaded, dict) or loaded.get("type") != "FeatureCollection":
        raise LayerRefused("a layer is a GeoJSON FeatureCollection in UTF-8 JSON")
    return loaded


def _features(collection: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    features = collection.get("features")
    if not isinstance(features, list) or not 1 <= len(features) <= FEATURES_MAX:
        raise LayerRefused(f"a layer holds 1 to {FEATURES_MAX} features")
    return features


def _check_crs(crs: Any) -> None:
    if crs is None:
        return
    properties = crs.get("properties") if isinstance(crs, dict) else None
    name = str(properties.get("name", "")) if isinstance(properties, dict) else ""
    if not any(name.endswith(found) for found in WGS84_CRS_NAMES):
        raise LayerRefused(f"a layer is in WGS 84 longitude and latitude, and its crs names {name or crs}")


def _check_feature(feature: Any, plan: MapLayerPlan, number: int) -> None:
    if not isinstance(feature, dict) or feature.get("type") != "Feature":
        raise LayerRefused(f"feature {number} is not a GeoJSON Feature")
    geometry = feature.get("geometry")
    kind = geometry.get("type") if isinstance(geometry, dict) else None
    allowed = GEOMETRY_TYPES[plan.kind.geometry]
    if kind not in allowed:
        held = " or ".join(allowed)
        raise LayerRefused(
            f"feature {number} is a {kind or 'missing geometry'}; {plan.layer_class} holds {held}"
        )
    _check_value(feature.get("properties"), plan, number)
    coordinates = geometry.get("coordinates")
    _check_parts(kind, coordinates, plan, number)
    for found in _positions(coordinates, NESTING[kind], number):
        _check_position(found, plan, number)


def _check_value(properties: Any, plan: MapLayerPlan, number: int) -> None:
    name = plan.value_property
    if name is None:
        return
    if not isinstance(properties, dict) or name not in properties:
        raise LayerRefused(f"feature {number} has no {name}: give its value, or null where it has no reading")
    value = properties[name]
    if value is not None and (isinstance(value, bool) or not isinstance(value, int | Decimal)):
        raise LayerRefused(f"feature {number} gives {name} as {value!r}; a value is a number, or null")


def _check_parts(kind: str, coordinates: Any, plan: MapLayerPlan, number: int) -> None:
    parts = [coordinates] if kind in SINGLE_PARTS else coordinates
    if not isinstance(parts, list) or not parts:
        raise LayerRefused(NOT_NESTED.format(number=number))
    short = any(not isinstance(line, list) or len(line) < LINE_POSITIONS_MIN for line in parts)
    if kind in ("LineString", "MultiLineString") and short:
        raise LayerRefused(f"feature {number} has a line of fewer than {LINE_POSITIONS_MIN} positions")
    if kind in ("Polygon", "MultiPolygon"):
        for shape in parts:
            _check_shape(shape, plan, number)


def _check_shape(shape: Any, plan: MapLayerPlan, number: int) -> None:
    rings = shape if isinstance(shape, list) and shape else None
    if rings is None or any(not _closed(ring) for ring in rings):
        raise LayerRefused(OPEN_RING.format(number=number, least=RING_POSITIONS_MIN))
    least = plan.kind.min_area
    if least is not None and ring_area(rings[0]) < least:
        raise LayerRefused(
            f"feature {number} is under {least:g} square degree, which a {plan.layer_class} layer leaves out"
        )


def _closed(ring: Any) -> bool:
    return isinstance(ring, list) and len(ring) >= RING_POSITIONS_MIN and ring[0] == ring[-1]


def _positions(coordinates: Any, depth: int, number: int) -> Iterator[Any]:
    if depth == 0:
        yield coordinates
        return
    if not isinstance(coordinates, list) or not coordinates:
        raise LayerRefused(NOT_NESTED.format(number=number))
    for inner in coordinates:
        yield from _positions(inner, depth - 1, number)


def _check_position(found: Any, plan: MapLayerPlan, number: int) -> None:
    shaped = isinstance(found, list) and len(found) in POSITION_SIZES
    if not shaped or not all(_is_number(value) for value in found):
        raise LayerRefused(f"feature {number} has a position that is not [longitude, latitude]")
    longitude, latitude = found[0], found[1]
    allowed = decimals_allowed(plan)
    if _decimals(longitude) > allowed or _decimals(latitude) > allowed:
        raise LayerRefused(
            f"feature {number} gives [{longitude}, {latitude}]; coordinates carry at most {allowed} decimals"
        )
    if not INDIA_FRAME.holds(float(longitude), float(latitude)):
        raise LayerRefused(
            f"feature {number} reaches [{longitude}, {latitude}], outside India's frame; clip the layer to the "
            "Survey of India outline or the map's frame"
        )


def _is_number(value: Any) -> bool:
    return not isinstance(value, bool) and isinstance(value, int | Decimal)


def _decimals(value: int | Decimal) -> int:
    if isinstance(value, int):
        return 0
    exponent = value.normalize().as_tuple().exponent
    return -exponent if isinstance(exponent, int) and exponent < 0 else 0
