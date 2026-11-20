from __future__ import annotations

import json
import re
from collections.abc import Mapping
from typing import Any

from app.core.errors import InvalidInput

from .extract_specs_files import Extractor, Found
from .extract_specs_markup import Element, has_classes, is_tag
from .extract_specs_parts import (
    drawing,
    figure_head,
    held_text,
    held_text_or_unit,
    slot_unit,
    style_of,
    text_line,
)

__all__ = ["MAP_EXTRACTORS", "axis_event_label", "pick_label"]

ROW_CLASS = re.compile(r"r(\d+)")


def axis_event_label(when: str, title: str) -> str:
    return f"{when}, {title}"


def pick_label(title: str) -> str:
    return f"Show {title} on the map"


def map_layer(found: Found) -> dict[str, Any]:
    element = found.element
    if element.name == "svg":
        return {"setting": "drawing", "drawing": drawing(element)}
    return {"setting": "explorer", "explorer": _explorer(element, found)}


def _explorer(figure: Element, found: Found) -> dict[str, Any]:
    widget = figure.first(lambda part: "data-comp" in part.attrs)
    area = widget.first(has_classes("rs-map"))
    inset = area.first(has_classes("rs-inset"))
    key = widget.first(lambda part: part.attrs.get("id") == area.attrs["aria-describedby"])
    side = widget.first(has_classes("rs-side"))
    told = [
        part for part in side.elements() if part.name in ("h3", "p") and "data-rank-cap" not in part.attrs
    ]
    told = [part for part in told if not part.has_class("src-note")]
    return {
        "head": figure_head(figure),
        "id": widget.attrs["id"],
        "comp": widget.attrs["data-comp"],
        "controls": [_toggles(group) for group in widget.all(has_classes("seg"))],
        "mapLabel": area.attrs["aria-label"],
        "drawing": drawing(area.first(is_tag("svg"))),
        "inset": {
            "drawing": drawing(inset.first(is_tag("svg"))),
            "caption": slot_unit(inset.first(is_tag("p"))),
        },
        "key": {"id": key.attrs["id"], "unit": slot_unit(key)},
        "caption": slot_unit(widget.first(has_classes("rs-cap"))),
        "side": [text_line(part, found.sources) for part in told],
        "rank": {
            "caption": slot_unit(side.first(lambda part: "data-rank-cap" in part.attrs)),
            "more": side.first(lambda part: "data-rank-all" in part.attrs).text(),
        },
    }


def _toggles(group: Element) -> dict[str, Any]:
    marker = "layers" if "data-layers" in group.attrs else "zooms"
    key = "layer" if marker == "layers" else "z"
    return {
        "classes": group.classes,
        "label": group.attrs["aria-label"],
        "marker": marker,
        "optionKey": key,
        "options": [
            {
                "value": button.attrs[f"data-{key}"],
                "label": button.text(),
                "pressed": button.attrs["aria-pressed"] == "true",
            }
            for button in group.elements()
        ],
    }


def map_sequence(found: Found) -> dict[str, Any]:
    figure = found.element
    lists = [part for part in figure.elements() if part.name == "ol"]
    return {
        "head": figure_head(figure),
        "first": [_sequence_item(item, found) for item in lists[0].elements()],
        "source": text_line(figure.first(has_classes("src-line")), found.sources),
        "more": [_sequence_item(item, found) for item in lists[1].elements()] if len(lists) > 1 else [],
    }


def _sequence_item(item: Element, found: Found) -> dict[str, Any]:
    label = found.component_at(item)
    if label:
        return {"component": label}
    shown = item.first(has_classes("ws-vis")).elements()
    visual = found.component_at(shown[0]) if shown else None
    if shown and visual is None:
        raise InvalidInput(f"{found.component.label}: a card's picture is not a component")
    differs = item.all(is_tag("details"))
    lines = [part for part in item.elements() if part.name == "p" and not part.has_class("when")]
    card = {
        "visual": visual,
        "when": slot_unit(item.first(has_classes("when"))),
        "title": slot_unit(item.first(is_tag("h3"))),
        "lines": [text_line(line, found.sources) for line in lines],
        "differs": _differs(differs[0], found) if differs else None,
    }
    return {"card": card}


def _differs(details: Element, found: Found) -> dict[str, Any]:
    return {
        "summary": held_text(details.first(is_tag("summary")), found.sources),
        "body": held_text_or_unit(details.first(has_classes("differs-body")), found.sources),
    }


def timeline_map(found: Found) -> dict[str, Any]:
    figure = found.element
    widget = figure.first(lambda part: part.attrs.get("data-comp") == "time")
    events = json.loads(widget.attrs["data-events"])
    rest = int(widget.attrs["data-rest"])
    play = widget.first(lambda part: "data-play" in part.attrs)
    switch_label = widget.first(has_classes("sw-label"))
    places = widget.first(has_classes("tl-map"))
    return {
        "head": figure_head(figure),
        "id": widget.attrs["id"],
        "comp": widget.attrs["data-comp"],
        "rest": rest,
        "events": events,
        "play": play.attrs["aria-label"],
        "status": slot_unit(widget.first(has_classes("tl-status"))),
        "supply": {
            "labelId": switch_label.attrs["id"],
            "label": switch_label.text(),
            "description": widget.first(has_classes("sw-desc")).text(),
        },
        "views": json.loads(places.attrs["data-views"]),
        "drawing": drawing(places.first(is_tag("svg"))),
        "legend": [_legend_item(item) for item in widget.first(has_classes("tl-legend")).elements()],
        "caption": slot_unit(widget.first(has_classes("tl-cap"))),
        "cards": [_event_card(card, found) for card in widget.first(has_classes("tl-card")).elements()],
        "supplyNote": [
            text_line(line, found.sources) for line in widget.first(has_classes("tl-supply")).elements()
        ],
        "axis": _axis(widget.first(has_classes("tl-axis")), events, rest),
        "items": _items(widget.first(has_classes("tl-list")), events, rest, found),
    }


def _legend_item(item: Element) -> dict[str, Any]:
    return {"swatch": item.elements()[0].classes, "label": item.text()}


def _event_card(card: Element, found: Found) -> dict[str, Any]:
    lines = [part for part in card.elements() if part.name == "p" and not part.has_class("when")]
    return {
        "when": slot_unit(card.first(has_classes("when"))),
        "title": slot_unit(card.first(is_tag("h3"))),
        "lines": [text_line(line, found.sources) for line in lines],
    }


def _axis(axis: Element, events: list[dict[str, Any]], rest: int) -> dict[str, Any]:
    row = axis.first(lambda part: part.attrs.get("role") == "toolbar")
    marks = []
    for index, button in enumerate(row.elements()):
        expected = axis_event_label(events[index]["when"], events[index]["title"])
        if button.attrs["aria-label"] != expected or (button.attrs["aria-pressed"] == "true") != (
            index == rest
        ):
            raise InvalidInput(f"The axis mark {index} does not name or press its event")
        found_row = next(ROW_CLASS.fullmatch(cls) for cls in button.classes if ROW_CLASS.fullmatch(cls))
        marks.append(
            {
                "row": int(found_row.group(1)),
                "left": style_of(button)["left"],
                "short": button.first(has_classes("ln")).text(),
            }
        )
    return {
        "label": row.attrs["aria-label"],
        "breaks": [style_of(part)["left"] for part in axis.all(has_classes("ax-break"))],
        "ticks": [
            {"left": style_of(tick)["left"], "text": tick.text()} for tick in axis.all(has_classes("tick"))
        ],
        "spans": [
            {"left": style_of(span)["left"], "width": style_of(span)["width"]}
            for span in axis.all(has_classes("span"))
        ],
        "events": marks,
    }


def _items(listing: Element, events: list[dict[str, Any]], rest: int, found: Found) -> list[dict[str, Any]]:
    items = []
    for index, item in enumerate(listing.elements()):
        pick = item.first(is_tag("button"))
        if pick.attrs["aria-label"] != pick_label(events[index]["title"]) or item.has_class("is-on") != (
            index == rest
        ):
            raise InvalidInput(f"The timeline item {index} does not name or mark its event")
        items.append(_event_card(item, found))
    return items


MAP_EXTRACTORS: Mapping[str, Extractor] = {
    "map_layer": map_layer,
    "map_sequence": map_sequence,
    "timeline_map": timeline_map,
}
