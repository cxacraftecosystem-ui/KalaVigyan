from __future__ import annotations

import json
from typing import Any

from app.core.errors import InvalidInput

from .extract_specs_science_chem import figure_head
from .extract_specs_science_dom import Element
from .extract_specs_science_read import (
    drawing,
    expect,
    held,
    holds_unit,
    kids,
    note_differs,
    one_of,
    text_of,
    unit_of,
)

__all__ = ["stage_player", "stage_tile"]

TILE_SLICE = "xMidYMid slice"
WEAVE = "url(#pt-weave)"
RIBBON_BOX = "0 0 100 150"
LIST_BOX = "0 0 100 100"
SWATCH_BOX = "0 0 200 200"
CLOTH_AFTER = "Cloth after"


def stage_tile(style: str, view_box: str, stage: int) -> dict[str, Any]:
    fills = (f"url(#tile-{stage})", WEAVE)
    rects = [
        {"tag": "rect", "attrs": {"x": "-200", "y": "-200", "width": "800", "height": "800", "fill": fill}}
        for fill in fills
    ]
    attrs = {"class": style, "viewBox": view_box, "preserveAspectRatio": TILE_SLICE, "aria-hidden": "true"}
    return {"tag": "svg", "attrs": attrs, "children": rects}


def stage_player(element: Element) -> dict[str, Any]:
    number, title, dek, cloth = kids(expect(element, "figure", "fig", "lc-fig"))
    stagebox, ribbon, source, steps, finish = kids(expect(cloth, "div", "lc"))
    key = cloth.attrs["id"].removesuffix("-lc")
    entries = json.loads(cloth.attrs["data-stages"])
    if cloth.attrs["data-rest"] != str(len(entries)) or [entry["n"] for entry in entries] != _numbers(
        entries
    ):
        raise InvalidInput("a stage player numbers its stages in order and rests on the last")
    _check_ribbon(ribbon, key, entries)
    items = kids(expect(steps, "ol", "lc-steps"))
    heading, *paragraphs = kids(expect(finish, "div", "lc-fin"))
    return {
        "key": key,
        "head": figure_head([number, title, dek]),
        **_stage_box(stagebox, entries),
        "source": unit_of(expect(source, "p", "src-line", "lc-src")),
        "stages": [_stage(entry, item, key) for entry, item in zip(entries, items, strict=True)],
        "finish": {
            "heading": unit_of(expect(heading, "h3")),
            "paragraphs": [unit_of(expect(paragraph, "p")) for paragraph in paragraphs],
        },
    }


def _numbers(entries: list[dict[str, Any]]) -> list[int]:
    return list(range(1, len(entries) + 1))


def _stage_box(stagebox: Element, entries: list[dict[str, Any]]) -> dict[str, Any]:
    big, card = kids(expect(stagebox, "div", "lc-stagebox"))
    counter, name, now, play = kids(expect(card, "div", "label-card", "lc-label"))
    rest = len(entries)
    if text_of(one_of(kids(expect(counter, "p", "lc-k")))) != f"Stage {rest} of {rest}":
        raise InvalidInput("the label card counts the stage it rests on")
    label, after = kids(expect(now, "p", "lc-now"))
    if text_of(label) != CLOTH_AFTER or text_of(after) != entries[-1]["after"]:
        raise InvalidInput("the label card names the cloth after the stage it rests on")
    actions, _status = kids(expect(play, "div", "lc-play"))
    button = one_of(kids(expect(actions, "div", "actions", "start")))
    _icon, words = kids(expect(button, "button", "btn", "sm"))
    return {
        "drawing": drawing(expect(one_of(kids(expect(big, "div", "lc-big"))), "svg", "lc-bsvg")),
        "restName": unit_of(expect(name, "p", "lc-name")),
        "play": text_of(expect(words, "span")),
        "afterLabel": text_of(label),
    }


def _check_ribbon(ribbon: Element, key: str, entries: list[dict[str, Any]]) -> None:
    buttons = kids(expect(ribbon, "div", "lc-ribbon"))
    for stage, (entry, button) in enumerate(zip(entries, buttons, strict=True), start=1):
        picture, label = kids(expect(button, "button", "rb"))
        number, name = kids(expect(label, "span", "rb-l"))
        expected = (str(stage), f"{key}-st-{stage}", f"{stage} {entry['name']}")
        found = (button.attrs["data-go"], button.attrs["aria-controls"], button.attrs["aria-label"])
        if found != expected or text_of(number) != str(stage) or text_of(name) != entry["name"]:
            raise InvalidInput(f"ribbon button {stage} names its stage: {button.attrs}")
        expect(name, "i" if entry["local"] else "span")
        _check_tile(picture, "rb-svg", RIBBON_BOX, stage)


def _check_tile(picture: Element, style: str, view_box: str, stage: int) -> None:
    if drawing(picture) != stage_tile(style, view_box, stage):
        raise InvalidInput(f"the {style} of stage {stage} is not the cloth tile of stage {stage}")


def _stage(entry: dict[str, Any], item: Element, key: str) -> dict[str, Any]:
    stage = entry["n"]
    if item.attrs["id"] != f"{key}-st-{stage}" or item.attrs["data-stage"] != str(stage):
        raise InvalidInput(f"stage {stage} carries its id and number: {item.attrs}")
    head, *parts = kids(expect(item, "li", "lc-step"))
    tile, number, heading = kids(expect(head, "div", "lc-sh"))
    _check_tile(one_of(kids(expect(tile, "span", "lc-tile"))), "lc-tsvg", LIST_BOX, stage)
    found = {
        "name": entry["name"],
        "english": entry["eng"],
        "local": entry["local"],
        "after": entry["after"],
        "number": unit_of(expect(number, "p", "lc-no")),
        "heading": unit_of(expect(heading, "h3")),
        "texts": [],
        "why": None,
        "differs": None,
        "afterSentence": None,
        "materials": None,
    }
    for part in parts:
        _stage_part(part, found, stage)
    return found


def _stage_part(part: Element, found: dict[str, Any], stage: int) -> None:
    style = part.attrs.get("class", "")
    if part.tag == "p" and style == "lc-t":
        found["texts"].append(unit_of(part))
    elif part.tag == "p" and style == "lc-mats":
        found["materials"] = unit_of(part)
    elif part.tag == "p" and style == "lc-why":
        found["why"] = unit_of(part) if holds_unit(part) else held(part)
    elif part.tag == "p" and style == "lc-after":
        found["afterSentence"] = _after_sentence(part, stage)
    elif part.tag == "details" and style == "differs":
        found["differs"] = note_differs(part)
    else:
        raise InvalidInput(f"stage {stage} holds an unknown part <{part.tag} {part.attrs}>")


def _after_sentence(part: Element, stage: int) -> str | None:
    label, sentence = kids(expect(part, "p", "lc-after"))
    if text_of(expect(label, "span", "lk")) != CLOTH_AFTER:
        raise InvalidInput("the cloth-after line opens with its label")
    picture, *words = expect(sentence, "span", "lc-av").elements
    _check_tile(picture, "lc-sw", SWATCH_BOX, stage)
    if not holds_unit(sentence):
        return held(sentence)
    return one_of(words).attrs["unit"]
