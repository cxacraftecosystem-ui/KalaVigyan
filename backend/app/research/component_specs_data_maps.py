from __future__ import annotations

from typing import Literal, Self

from pydantic import Field, model_validator

from .base import ContractModel
from .component_specs_data_parts import (
    ComponentLabel,
    CssLength,
    FigureHead,
    TextLine,
    ToggleGroup,
)
from .component_specs_plates_parts import ClassName, DomId, DrawingElement, HeldOrUnit, HeldText, UnitRef

__all__ = ["MAP_SETTINGS", "MapLayerSpec", "MapSequenceSpec", "TimelineMapSpec"]

MAP_SETTINGS = ("drawing", "explorer")


class MapInset(ContractModel):
    drawing: DrawingElement
    caption: UnitRef


class MapKey(ContractModel):
    id: DomId
    unit: UnitRef


class MapRank(ContractModel):
    caption: UnitRef
    more: str = Field(min_length=1)


class MapExplorer(ContractModel):
    head: FigureHead
    id: DomId
    comp: str = Field(pattern=r"^[a-z]+$")
    controls: list[ToggleGroup] = Field(min_length=1)
    map_label: str = Field(min_length=1)
    drawing: DrawingElement
    inset: MapInset
    key: MapKey
    caption: UnitRef
    side: list[TextLine] = Field(min_length=1)
    rank: MapRank


class MapLayerSpec(ContractModel):
    setting: Literal[*MAP_SETTINGS]
    drawing: DrawingElement | None = None
    explorer: MapExplorer | None = None

    @model_validator(mode="after")
    def _the_part_of_its_setting(self) -> Self:
        if (self.drawing is not None) != (self.setting == "drawing"):
            raise ValueError("A drawn map layer is its drawing")
        if (self.explorer is not None) != (self.setting == "explorer"):
            raise ValueError("A map explorer has its explorer part and no other")
        return self


class SourcesDiffer(ContractModel):
    summary: HeldText
    body: HeldOrUnit


class SequenceCard(ContractModel):
    visual: ComponentLabel | None = None
    when: UnitRef
    title: UnitRef
    lines: list[TextLine] = Field(min_length=1)
    differs: SourcesDiffer | None = None


class SequenceItem(ContractModel):
    card: SequenceCard | None = None
    component: ComponentLabel | None = None

    @model_validator(mode="after")
    def _a_card_or_a_component(self) -> Self:
        if (self.card is None) == (self.component is None):
            raise ValueError("A sequence item is its own card or another component, not both or neither")
        return self


class MapSequenceSpec(ContractModel):
    head: FigureHead
    first: list[SequenceItem] = Field(min_length=1)
    source: TextLine
    more: list[SequenceItem] = Field(default_factory=list)


class TimelineEvent(ContractModel):
    view: str = Field(min_length=1)
    routes: list[str]
    pins: list[str]
    when: str = Field(min_length=1)
    title: str = Field(min_length=1)


class LegendItem(ContractModel):
    swatch: list[ClassName] = Field(min_length=1)
    label: str = Field(min_length=1)


class EventCard(ContractModel):
    when: UnitRef
    title: UnitRef
    lines: list[TextLine] = Field(min_length=1)


class SupplySwitch(ContractModel):
    label_id: DomId
    label: str = Field(min_length=1)
    description: str = Field(min_length=1)


class AxisTick(ContractModel):
    left: CssLength
    text: str = Field(min_length=1)


class AxisSpan(ContractModel):
    left: CssLength
    width: CssLength


class AxisEvent(ContractModel):
    row: int = Field(ge=0)
    left: CssLength
    short: str = Field(min_length=1)


class TimelineAxis(ContractModel):
    label: str = Field(min_length=1)
    breaks: list[CssLength] = Field(default_factory=list)
    ticks: list[AxisTick] = Field(min_length=1)
    spans: list[AxisSpan] = Field(default_factory=list)
    events: list[AxisEvent] = Field(min_length=1)


class TimelineMapSpec(ContractModel):
    head: FigureHead
    id: DomId
    comp: str = Field(pattern=r"^[a-z]+$")
    rest: int = Field(ge=0)
    events: list[TimelineEvent] = Field(min_length=1)
    play: str = Field(min_length=1)
    status: UnitRef
    supply: SupplySwitch
    views: dict[str, list[int | float]]
    drawing: DrawingElement
    legend: list[LegendItem] = Field(min_length=1)
    caption: UnitRef
    cards: list[EventCard] = Field(min_length=1)
    supply_note: list[TextLine] = Field(min_length=1)
    axis: TimelineAxis
    items: list[EventCard] = Field(min_length=1)

    @model_validator(mode="after")
    def _one_card_and_mark_per_event(self) -> Self:
        count = len(self.events)
        if not (len(self.cards) == len(self.items) == len(self.axis.events) == count):
            raise ValueError("A timeline map has one card, list item and axis mark for each event")
        if self.rest >= count:
            raise ValueError("A timeline map rests on one of its events")
        return self
