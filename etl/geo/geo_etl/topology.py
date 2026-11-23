import json
from collections.abc import Mapping
from dataclasses import dataclass
from itertools import pairwise

import geopandas as gpd
import shapely

OBJECT = "reaches"
SIMPLIFY_DEGREES = 0.005
QUANTIZATION = 100_000
MIN_ARC_POSITIONS = 2


@dataclass(frozen=True)
class Quantizer:
    x0: float
    y0: float
    kx: float
    ky: float

    def position(self, x: float, y: float) -> tuple[int, int]:
        return round((x - self.x0) / self.kx), round((y - self.y0) / self.ky)

    def transform(self) -> dict:
        return {"scale": [self.kx, self.ky], "translate": [self.x0, self.y0]}


def quantizer(bounds: tuple[float, float, float, float], steps: int = QUANTIZATION) -> Quantizer:
    x0, y0, x1, y1 = bounds
    kx = (x1 - x0) / (steps - 1) if x1 > x0 else 1.0
    ky = (y1 - y0) / (steps - 1) if y1 > y0 else 1.0
    return Quantizer(x0=x0, y0=y0, kx=kx, ky=ky)


def quantized_arc(line: shapely.LineString, grid: Quantizer) -> list[list[int]]:
    points: list[tuple[int, int]] = []
    for x, y in line.coords:
        point = grid.position(x, y)
        if not points or point != points[-1]:
            points.append(point)
    if len(points) < MIN_ARC_POSITIONS:
        points.append(points[0])
    first = points[0]
    deltas = [[first[0], first[1]]]
    deltas.extend([b[0] - a[0], b[1] - a[1]] for a, b in pairwise(points))
    return deltas


def basin_topology(reaches: gpd.GeoDataFrame, districts_of: Mapping[int, list[list]]) -> dict:
    ordered = reaches.sort_values("hyrivId", kind="stable")
    lines = shapely.simplify(ordered.geometry.to_numpy(), SIMPLIFY_DEGREES, preserve_topology=True)
    bounds = tuple(float(v) for v in shapely.total_bounds(lines))
    grid = quantizer(bounds)
    arcs = [quantized_arc(line, grid) for line in lines]
    geometries = [
        {
            "type": "LineString",
            "id": int(hyriv_id),
            "arcs": [index],
            "properties": {
                "nextDown": int(next_down),
                "ordStra": int(ord_stra),
                "districts": districts_of.get(int(hyriv_id), []),
            },
        }
        for index, (hyriv_id, next_down, ord_stra) in enumerate(
            zip(ordered["hyrivId"], ordered["nextDown"], ordered["ordStra"], strict=True)
        )
    ]
    return {
        "type": "Topology",
        "bbox": list(bounds),
        "transform": grid.transform(),
        "objects": {OBJECT: {"type": "GeometryCollection", "geometries": geometries}},
        "arcs": arcs,
    }


def encoded(topology: dict) -> bytes:
    return json.dumps(topology, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
