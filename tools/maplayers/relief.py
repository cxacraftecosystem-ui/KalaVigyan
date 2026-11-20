from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

import numpy as np
import pyogrio
import rasterio
import shapely
from rasterio.features import geometry_mask, shapes
from rasterio.transform import Affine
from shapely.geometry import shape
from shapely.geometry.base import BaseGeometry

from .geo import encoded_rings, screen
from .labels import PEAKS_HELD_BACK, RANGES, label_angle, peak_text
from .sources import BOUNDS, BREAKS, ETOPO, Downloads

__all__ = ["Grid", "hillshade", "read_grid", "relief_body", "shade_webp"]

BAND_TOLERANCE = 0.018
PEAK_FLOOR = 1000
SHADE_QUALITY = 70
SUN_AZIMUTH = 315.0
SUN_ALTITUDE = 45.0
EXAGGERATION = 4.0
METRES_PER_DEGREE = 111_320.0
PEAK_REACH = 0.05
ELONGATED = 2.2


@dataclass(frozen=True)
class Grid:
    values: np.ndarray
    transform: Affine

    @property
    def bounds(self) -> tuple[float, float, float, float]:
        rows, columns = self.values.shape
        west, north = self.transform * (0, 0)
        east, south = self.transform * (columns, rows)
        return west, south, east, north


def read_grid(downloads: Downloads) -> Grid:
    with rasterio.open(downloads.folder / ETOPO.file) as source:
        values = source.read(1).astype("float32")
        nodata = source.nodata
        transform = source.transform
    if nodata is not None:
        values[values == nodata] = np.nan
    return Grid(values, transform)


def _smoothed(values: np.ndarray) -> np.ndarray:
    padded = np.pad(values, 1, mode="edge")
    total = sum(padded[r : r + values.shape[0], c : c + values.shape[1]] for r in range(3) for c in range(3))
    return total / 9.0


def _halved(grid: Grid) -> Grid:
    rows, columns = (size // 2 * 2 for size in grid.values.shape)
    cut = grid.values[:rows, :columns]
    blocks = cut.reshape(rows // 2, 2, columns // 2, 2).mean(axis=(1, 3))
    return Grid(blocks, grid.transform * Affine.scale(2))


def _band(grid: Grid, threshold: float, india: BaseGeometry) -> list[str]:
    mask = np.nan_to_num(grid.values, nan=-1e9) >= threshold
    pieces = [
        shape(geometry)
        for geometry, value in shapes(mask.astype("uint8"), mask=mask, transform=grid.transform)
        if value
    ]
    if not pieces:
        return []
    merged = shapely.simplify(shapely.union_all(pieces), BAND_TOLERANCE)
    return encoded_rings(shapely.make_valid(shapely.intersection(merged, india)))


def hillshade(values: np.ndarray, cell: float, latitudes: np.ndarray) -> np.ndarray:
    surface = np.nan_to_num(values, nan=0.0) * EXAGGERATION
    spacing_y = cell * METRES_PER_DEGREE
    spacing_x = spacing_y * np.cos(np.radians(latitudes))[:, None]
    along_rows, along_columns = np.gradient(surface)
    rows = along_rows / spacing_y
    columns = along_columns / spacing_x
    slope = np.pi / 2 - np.arctan(np.hypot(rows, columns))
    aspect = np.arctan2(-rows, columns)
    altitude = math.radians(SUN_ALTITUDE)
    azimuth = math.radians(SUN_AZIMUTH)
    lit = math.sin(altitude) * np.sin(slope) + math.cos(altitude) * np.cos(slope) * np.cos(azimuth - aspect)
    flat = math.sin(altitude)
    return np.clip((flat - lit) / flat, 0.0, 1.0)


def shade_webp(grid: Grid, india: BaseGeometry, path: Any) -> None:
    rows = grid.values.shape[0]
    latitudes = np.array([(grid.transform * (0, row + 0.5))[1] for row in range(rows)])
    shade = hillshade(_smoothed(grid.values), abs(grid.transform.e), latitudes)
    outside = geometry_mask([india], out_shape=grid.values.shape, transform=grid.transform)
    shade[outside] = 0.0
    scaled = np.round(np.power(shade, 0.85) * 255).astype("uint8")
    rows, columns = scaled.shape
    profile = {
        "driver": "WEBP",
        "width": columns,
        "height": rows,
        "count": 3,
        "dtype": "uint8",
        "QUALITY": SHADE_QUALITY,
    }
    with rasterio.open(path, "w", **profile) as target:
        target.write(np.stack([scaled, scaled, scaled]))


def _range_angle(geometry: BaseGeometry) -> float:
    corners = [screen(x, y) for x, y in shapely.minimum_rotated_rectangle(geometry).exterior.coords][:4]
    sides = [(corners[i + 1][0] - corners[i][0], corners[i + 1][1] - corners[i][1]) for i in range(2)]
    long, short = sorted(sides, key=lambda side: -math.hypot(*side))
    if math.hypot(*long) < ELONGATED * math.hypot(*short):
        return 0.0
    return label_angle(*long)


def _ranges(downloads: Downloads) -> list[dict[str, Any]]:
    frame = pyogrio.read_dataframe(
        downloads.shapefile("regions"), columns=["NAME_EN", "SCALERANK"], bbox=BOUNDS
    )
    found: dict[str, dict[str, Any]] = {}
    for name, rank, geometry in zip(frame["NAME_EN"], frame["SCALERANK"], frame.geometry, strict=True):
        if name not in RANGES or (name in found and found[name]["rank"] <= int(rank)):
            continue
        point = geometry.representative_point()
        text, tier, placed = RANGES[name]
        longitude, latitude, angle = placed or (round(point.x, 3), round(point.y, 3), _range_angle(geometry))
        found[name] = {
            "text": text,
            "tier": tier,
            "rank": int(rank),
            "longitude": longitude,
            "latitude": latitude,
            "angle": angle,
        }
    return sorted(
        ({key: value for key, value in item.items() if key != "rank"} for item in found.values()),
        key=lambda item: (item["tier"], item["text"]),
    )


def _peaks(downloads: Downloads, india: BaseGeometry) -> list[dict[str, Any]]:
    frame = pyogrio.read_dataframe(
        downloads.shapefile("peaks"),
        columns=["name", "name_en", "featurecla", "elevation", "scalerank"],
        bbox=BOUNDS,
    )
    reach = shapely.buffer(india, PEAK_REACH)
    peaks = []
    for name, english, kind, elevation, rank, point in zip(
        frame["name"],
        frame["name_en"],
        frame["featurecla"],
        frame["elevation"],
        frame["scalerank"],
        frame.geometry,
        strict=True,
    ):
        held = name in PEAKS_HELD_BACK or float(elevation) < PEAK_FLOOR
        if kind != "mountain" or not isinstance(english, str) or held or not reach.contains(point):
            continue
        peaks.append(
            {
                "name": english,
                "elevation": round(float(elevation)),
                "text": peak_text(english, float(elevation)),
                "rank": int(rank),
                "longitude": round(point.x, 3),
                "latitude": round(point.y, 3),
            }
        )
    return sorted(peaks, key=lambda peak: -peak["elevation"])


def relief_body(
    downloads: Downloads, grid: Grid, india: BaseGeometry, shade: dict[str, Any]
) -> dict[str, Any]:
    coarse = _halved(Grid(_smoothed(_smoothed(grid.values)), grid.transform))
    return {
        "source": "ETOPO1 elevations in hypsometric bands and shaded relief, clipped to the Survey of India outline; range names and spot heights from Natural Earth",
        "licence": "Public domain",
        "datasets": [
            downloads.source(ETOPO),
            downloads.natural_earth("regions"),
            downloads.natural_earth("peaks"),
        ],
        "breaks": list(BREAKS),
        "bands": [{"min": threshold, "rings": _band(coarse, threshold, india)} for threshold in BREAKS],
        "shade": shade,
        "ranges": _ranges(downloads),
        "peaks": _peaks(downloads, india),
    }
