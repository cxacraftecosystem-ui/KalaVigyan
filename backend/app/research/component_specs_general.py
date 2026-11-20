from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType
from typing import Annotated, Literal, Self

from pydantic import AfterValidator, Field, model_validator

from app.models.component_kinds import GENERAL_KINDS

from .base import ContractModel
from .component_specs_general_svg import cleaned_svg
from .component_specs_plates_parts import UnitRef

__all__ = [
    "BOUNDS",
    "GENERAL_CHART",
    "GENERAL_DRAWING",
    "GENERAL_KINDS",
    "GENERAL_MAP_LAYER",
    "GENERAL_TABLE",
    "GENERAL_TIMELINE",
    "SPEC_MODELS_GENERAL",
    "ChartPoint",
    "ChartSeries",
    "GeneralChartSpec",
    "GeneralDrawingSpec",
    "GeneralHead",
    "GeneralMapLayerSpec",
    "GeneralTableSpec",
    "GeneralTimelineSpec",
    "MapPlace",
    "TableColumn",
    "TableRow",
    "TimelineEvent",
]

GENERAL_DRAWING, GENERAL_CHART, GENERAL_TABLE, GENERAL_TIMELINE, GENERAL_MAP_LAYER = GENERAL_KINDS
CHART_FORMS = ("bars", "line")
SERIES_MAX = 3
POINTS_MAX = 60
COLUMNS_MAX = 8
ROWS_MAX = 100
EVENTS_MIN = 2
EVENTS_MAX = 40
PLACES_MAX = 60
YEAR_MIN = -3000
YEAR_MAX = 2100
BOUNDS = MappingProxyType({"west": 68.0, "east": 97.5, "south": 6.5, "north": 37.5})

CleanSvg = Annotated[str, AfterValidator(cleaned_svg)]


class GeneralHead(ContractModel):
    title: UnitRef
    caption: UnitRef | None = None


class GeneralDrawingSpec(ContractModel):
    head: GeneralHead
    svg: CleanSvg
    alt: UnitRef


class ChartPoint(ContractModel):
    label: UnitRef
    value: float
    reading: UnitRef


class ChartSeries(ContractModel):
    name: UnitRef
    points: list[ChartPoint] = Field(min_length=1, max_length=POINTS_MAX)


class GeneralChartSpec(ContractModel):
    head: GeneralHead
    form: Literal[*CHART_FORMS]
    value_label: UnitRef
    series: list[ChartSeries] = Field(min_length=1, max_length=SERIES_MAX)
    emphasis: int | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def _drawable(self) -> Self:
        lengths = {len(series.points) for series in self.series}
        if len(lengths) != 1:
            raise ValueError("Every series of a chart has one point per label")
        if self.emphasis is not None and self.emphasis >= len(self.series[0].points):
            raise ValueError("The emphasised point is one of the first series' points")
        if self.form == "bars" and any(point.value < 0 for series in self.series for point in series.points):
            raise ValueError("Bars start at zero, so a bar chart shows no negative value")
        if self.form == "line" and len(self.series[0].points) < 2:
            raise ValueError("A line joins two points or more")
        return self


class TableColumn(ContractModel):
    label: UnitRef
    numeric: bool = False


class TableRow(ContractModel):
    cells: list[UnitRef] = Field(min_length=1, max_length=COLUMNS_MAX)


class GeneralTableSpec(ContractModel):
    head: GeneralHead
    columns: list[TableColumn] = Field(min_length=1, max_length=COLUMNS_MAX)
    rows: list[TableRow] = Field(min_length=1, max_length=ROWS_MAX)

    @model_validator(mode="after")
    def _square(self) -> Self:
        if any(len(row.cells) != len(self.columns) for row in self.rows):
            raise ValueError("Every row of a table has one cell per column")
        return self


class TimelineEvent(ContractModel):
    year: int = Field(ge=YEAR_MIN, le=YEAR_MAX)
    when: UnitRef
    title: UnitRef
    text: UnitRef


class GeneralTimelineSpec(ContractModel):
    head: GeneralHead
    events: list[TimelineEvent] = Field(min_length=EVENTS_MIN, max_length=EVENTS_MAX)

    @model_validator(mode="after")
    def _in_order(self) -> Self:
        years = [event.year for event in self.events]
        if years != sorted(years):
            raise ValueError("A timeline's events come in the order of their years")
        return self


class MapPlace(ContractModel):
    longitude: float = Field(ge=BOUNDS["west"], le=BOUNDS["east"])
    latitude: float = Field(ge=BOUNDS["south"], le=BOUNDS["north"])
    name: UnitRef
    reading: UnitRef
    value: float | None = Field(default=None, ge=0)


class GeneralMapLayerSpec(ContractModel):
    head: GeneralHead
    places: list[MapPlace] = Field(min_length=1, max_length=PLACES_MAX)
    value_label: UnitRef | None = None

    @model_validator(mode="after")
    def _valued_together(self) -> Self:
        valued = {place.value is not None for place in self.places}
        if len(valued) != 1:
            raise ValueError("Either every place of a map layer has a value or none has")
        if (True in valued) != (self.value_label is not None):
            raise ValueError("A map layer with values names what they measure in valueLabel, and only then")
        return self


SPEC_MODELS_GENERAL: Mapping[str, type[ContractModel]] = MappingProxyType(
    {
        GENERAL_DRAWING: GeneralDrawingSpec,
        GENERAL_CHART: GeneralChartSpec,
        GENERAL_TABLE: GeneralTableSpec,
        GENERAL_TIMELINE: GeneralTimelineSpec,
        GENERAL_MAP_LAYER: GeneralMapLayerSpec,
    }
)
