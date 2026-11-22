from __future__ import annotations

import json
import logging
import math
from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass, replace
from typing import Any

from app.data.district_register import load_district_codes
from app.research.blocks_journey import ZoomStoryBlock
from app.research.blocks_place import MapLayerBlock, RegionStoryBlock

from .district_seed import SHAPES_PATH, decode_rings
from .export_pdf_styles import CELL_BOLD, FIGURE_GAP_MM, KICKER, NOTE
from .export_pdf_text import compound_text
from .pdf_writer import ACCENT, RULE, SUNK, PdfWriter, Point

__all__ = [
    "MAP_MAX_MM",
    "DistrictOutlines",
    "DistrictShape",
    "MapProjection",
    "district_names",
    "district_outlines",
    "map_layer_figure",
    "map_projection",
    "region_story_figure",
    "zoom_story_figure",
]

logger = logging.getLogger(__name__)

MAP_MAX_MM = 75.0
MAP_GAP_MM = 1.5
REGION_KICKER = "Region"
RIVER_LABEL = "River"


@dataclass(frozen=True)
class DistrictShape:
    lgd: int
    state_lgd: int
    rings: tuple[tuple[Point, ...], ...]


@dataclass(frozen=True)
class DistrictOutlines:
    context: tuple[DistrictShape, ...]
    filled: tuple[DistrictShape, ...]

    def points(self) -> list[Point]:
        return [point for shape in self.context for ring in shape.rings for point in ring]


@dataclass(frozen=True)
class MapProjection:
    west: float
    north: float
    squeeze: float
    scale: float
    width: float
    height: float
    left: float = 0.0
    top: float = 0.0

    def place(self, point: Point) -> Point:
        lon, lat = point
        return self.left + (lon - self.west) * self.squeeze * self.scale, self.top + (
            self.north - lat
        ) * self.scale


def district_outlines(filled: Collection[int]) -> DistrictOutlines:
    rows = {int(row["lgd"]): row for row in json.loads(SHAPES_PATH.read_text(encoding="utf-8"))["districts"]}
    missing = sorted(lgd for lgd in filled if lgd not in rows)
    if missing:
        logger.warning("districts %s have no outline to draw in the export", missing)
    states = {int(rows[lgd]["stateLgd"]) for lgd in filled if lgd in rows}
    shapes = {lgd: _shape(row) for lgd, row in rows.items() if int(row["stateLgd"]) in states}
    return DistrictOutlines(
        context=tuple(shapes.values()), filled=tuple(shapes[lgd] for lgd in filled if lgd in shapes)
    )


def district_names(lgds: Sequence[int]) -> list[str]:
    named = {
        lgd: f"{district}, {state}" for (state, district), lgd in load_district_codes().districts.items()
    }
    return [named[lgd] for lgd in lgds if lgd in named]


def map_layer_figure(writer: PdfWriter, block: MapLayerBlock) -> None:
    writer.text(block.title, KICKER)
    _outlines(writer, district_outlines(block.highlighted))
    names = district_names(block.highlighted)
    if names:
        writer.text("; ".join(names), CELL_BOLD)
    writer.text(block.boundary_caption, NOTE)
    writer.go_to(writer.y + FIGURE_GAP_MM)


def region_story_figure(writer: PdfWriter, block: RegionStoryBlock) -> None:
    writer.text(REGION_KICKER, KICKER)
    _outlines(writer, district_outlines([district.district_lgd for district in block.districts]))
    writer.text("; ".join(f"{d.name}, {d.state_name}" for d in block.districts), CELL_BOLD)
    if block.river is not None and block.river.name is not None:
        writer.text(f"{RIVER_LABEL}: {block.river.name}", NOTE)
    writer.text(block.boundary_caption, NOTE)
    writer.go_to(writer.y + FIGURE_GAP_MM)


def zoom_story_figure(writer: PdfWriter, block: ZoomStoryBlock) -> None:
    districts = {level.district.district_lgd: level.district for level in block.levels if level.district}
    compounds = [level.compound for level in block.levels if level.compound is not None]
    if not districts and not compounds:
        return
    if districts:
        _outlines(writer, district_outlines(list(districts)))
        writer.text("; ".join(f"{d.name}, {d.state_name}" for d in districts.values()), CELL_BOLD)
        if block.boundary_caption:
            writer.text(block.boundary_caption, NOTE)
    for compound in compounds:
        writer.text(compound_text(compound.name, compound.formula, compound.pubchem_cid), CELL_BOLD)
    writer.go_to(writer.y + FIGURE_GAP_MM)


def _shape(row: Mapping[str, Any]) -> DistrictShape:
    return DistrictShape(
        lgd=int(row["lgd"]),
        state_lgd=int(row["stateLgd"]),
        rings=tuple(tuple(ring) for encoded in row["rings"] for ring in decode_rings(encoded)),
    )


def _outlines(writer: PdfWriter, outlines: DistrictOutlines) -> None:
    fitted = map_projection(outlines.points(), writer.width, MAP_MAX_MM)
    if fitted is None:
        return
    top = writer.room(fitted.height)
    projection = replace(fitted, left=writer.left + (writer.width - fitted.width) / 2, top=top)
    for shape in outlines.context:
        for ring in shape.rings:
            writer.shape([projection.place(point) for point in ring], fill=SUNK, line=RULE)
    for shape in outlines.filled:
        for ring in shape.rings:
            writer.shape([projection.place(point) for point in ring], fill=ACCENT, line=ACCENT)
    writer.go_to(top + fitted.height + MAP_GAP_MM)


def map_projection(points: Sequence[Point], width: float, max_height: float) -> MapProjection | None:
    if not points:
        return None
    lons, lats = [lon for lon, _ in points], [lat for _, lat in points]
    squeeze = math.cos(math.radians((min(lats) + max(lats)) / 2))
    span_x, span_y = (max(lons) - min(lons)) * squeeze, max(lats) - min(lats)
    if span_x <= 0 or span_y <= 0:
        return None
    scale = min(width / span_x, max_height / span_y)
    return MapProjection(
        west=min(lons),
        north=max(lats),
        squeeze=squeeze,
        scale=scale,
        width=span_x * scale,
        height=span_y * scale,
    )
