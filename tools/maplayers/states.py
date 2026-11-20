from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path

import shapely
from shapely.geometry import Point, Polygon
from shapely.geometry.base import BaseGeometry
from shapely.strtree import STRtree

from basemap.polyline import decode_records

__all__ = ["state_locator"]


def _district(rings: list[str]) -> BaseGeometry:
    shape: BaseGeometry = Polygon()
    for ring in rings:
        records = decode_records(ring, False)
        if records and len(records[0][1]) >= 3:
            shape = shapely.symmetric_difference(shape, shapely.make_valid(Polygon(records[0][1])))
    return shape


def state_locator(shapes_file: Path, register_file: Path) -> Callable[[float, float], str]:
    shapes = json.loads(shapes_file.read_text(encoding="utf-8"))
    register = json.loads(register_file.read_text(encoding="utf-8"))
    names = {state["lgd"]: state["name"] for state in register["states"]}
    districts = [
        (_district(district["rings"]), names.get(district["stateLgd"], ""))
        for district in shapes["districts"]
    ]
    kept = [(shape, name) for shape, name in districts if not shape.is_empty]
    tree = STRtree([shape for shape, _ in kept])

    def locate(longitude: float, latitude: float) -> str:
        point = Point(longitude, latitude)
        for index in tree.query(point, predicate="intersects"):
            return kept[int(index)][1]
        return ""

    return locate
