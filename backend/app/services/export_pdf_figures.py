from __future__ import annotations

from app.research.blocks import BlockBase
from app.research.blocks_climate import ClimateRiskBlock
from app.research.blocks_insight import MeasureBlock, MeasureRow
from app.research.blocks_journey import TimelineMapBlock, ZoomStoryBlock
from app.research.blocks_matter import MaterialCardBlock, Molecule3dBlock, ReactionPlayerBlock
from app.research.blocks_place import MapLayerBlock, RegionStoryBlock, SeasonsBlock, SupplyMapBlock
from app.research.blocks_play import SimulationBlock, SimulationValue
from app.research.sentence_names import upper_first

from .export_pdf_charts import climate_figure, seasons_figure
from .export_pdf_maps import map_layer_figure, region_story_figure, zoom_story_figure
from .export_pdf_styles import CELL, CELL_BOLD, FIGURE_GAP_MM, KICKER, NOTE
from .export_pdf_text import compound_text, measure_text, number_text, range_text, years_text
from .pdf_writer import PdfWriter

__all__ = [
    "MATERIALS_KICKER",
    "REACTIONS_KICKER",
    "TIMELINE_KICKER",
    "draw_figure",
    "measure_basis",
    "measure_line",
    "simulation_value_text",
]

REACTIONS_KICKER = "Reactions"
MATERIALS_KICKER = "Materials and where they come from"
TIMELINE_KICKER = "Timeline"
DEFINED_BASIS = "Exact definition"


def draw_figure(writer: PdfWriter, block: BlockBase) -> None:
    match block:
        case ClimateRiskBlock():
            climate_figure(writer, block)
        case SeasonsBlock():
            seasons_figure(writer, block)
        case MapLayerBlock():
            map_layer_figure(writer, block)
        case RegionStoryBlock():
            region_story_figure(writer, block)
        case ZoomStoryBlock():
            zoom_story_figure(writer, block)
        case ReactionPlayerBlock():
            _reactions(writer, block)
        case Molecule3dBlock():
            writer.text(compound_text(block.name, block.formula, block.pubchem_cid), CELL_BOLD)
        case MaterialCardBlock():
            _material(writer, block)
        case SupplyMapBlock():
            _supply(writer, block)
        case MeasureBlock():
            _measures(writer, block)
        case SimulationBlock():
            _simulation(writer, block)
        case TimelineMapBlock():
            _timeline(writer, block)


def measure_line(row: MeasureRow) -> str:
    return f"{row.stated} is {range_text(row.metric.low, row.metric.high, row.metric.unit)}"


def measure_basis(row: MeasureRow) -> str:
    conversion = row.conversion
    if conversion.basis == "DEFINED" or conversion.region is None:
        return DEFINED_BASIS
    region = conversion.region
    place = f"{region.district_name}, {region.state_name}" if region.district_name else region.state_name
    return f"As stated for {place}"


def simulation_value_text(value: SimulationValue) -> str:
    if value.stated:
        return f"{value.label}: {value.stated}"
    shown = measure_text(value.value, value.unit) if value.unit else number_text(value.value)
    return f"{value.label}: {shown}"


def _reactions(writer: PdfWriter, block: ReactionPlayerBlock) -> None:
    writer.text(REACTIONS_KICKER, KICKER)
    for step in block.steps:
        writer.text(step.label, CELL_BOLD)
        if step.equation:
            writer.text(step.equation, CELL)
        if step.stage:
            writer.text(step.stage, NOTE)
    writer.go_to(writer.y + FIGURE_GAP_MM)


def _material(writer: PdfWriter, block: MaterialCardBlock) -> None:
    writer.text(compound_text(block.name, block.formula, block.pubchem_cid), CELL_BOLD)
    if block.local_names:
        writer.text(", ".join(block.local_names), NOTE)


def _supply(writer: PdfWriter, block: SupplyMapBlock) -> None:
    writer.text(MATERIALS_KICKER, KICKER)
    origins: dict[str, list[str]] = {}
    for link in block.links:
        origins.setdefault(link.material, []).append(link.origin)
    for material, places in origins.items():
        writer.text(f"{upper_first(material)}: {', '.join(places)}", CELL)
    writer.go_to(writer.y + FIGURE_GAP_MM)


def _measures(writer: PdfWriter, block: MeasureBlock) -> None:
    for row in block.rows:
        writer.text(measure_line(row), CELL_BOLD)
        writer.text(measure_basis(row), NOTE)
    writer.go_to(writer.y + FIGURE_GAP_MM)


def _simulation(writer: PdfWriter, block: SimulationBlock) -> None:
    writer.text(block.title, KICKER)
    for value in block.values:
        writer.text(simulation_value_text(value), CELL)
    for reaction in block.reactions:
        writer.text(reaction.label, CELL_BOLD)
        if reaction.equation:
            writer.text(reaction.equation, CELL)
    writer.go_to(writer.y + FIGURE_GAP_MM)


def _timeline(writer: PdfWriter, block: TimelineMapBlock) -> None:
    writer.text(TIMELINE_KICKER, KICKER)
    for point in block.points:
        writer.text(f"{block.places[point.place].name} · {years_text(point.year_from, point.year_to)}", CELL)
    for route in block.routes:
        start, end = block.places[route.start].name, block.places[route.end].name
        writer.text(f"{start} to {end} · {years_text(route.year_from, route.year_to)}", CELL)
    writer.go_to(writer.y + FIGURE_GAP_MM)
