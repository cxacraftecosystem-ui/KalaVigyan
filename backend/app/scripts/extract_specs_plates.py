from __future__ import annotations

import re
from typing import Any

from app.core.errors import InvalidInput
from app.research.component_specs_plates import SPEC_MODELS_PLATES

from .extract_specs_files import Found, SpecGroup, run_group
from .extract_specs_markup import Element, has_classes, is_tag
from .extract_specs_parts import (
    drawing,
    dye_variable,
    held_or_unit,
    held_text,
    held_text_or_unit,
    picture,
    shown_day,
    slot_unit,
    url_reference,
)
from .extract_specs_plates_media import MEDIA_EXTRACTORS

__all__ = ["PLATES", "main"]

PLATE_CLASS = "plate"
MASTHEAD_CLASS = "kv-open-photo"
ROW_CLASS = "plate-row"
PULL_BOX = "kv-banni-q"
SOURCES_LINE = re.compile(r"Monograph drawn from (\d+) sources")
CURATED_LINE = re.compile(r"Curated (?P<day>\d{1,2} [A-Z][a-z]{2} \d{4})")
JOINS = {"→": "becomes", "or": "or"}


def picture_plate(found: Found) -> dict[str, Any]:
    element = found.element
    if element.has_class("opener"):
        return {
            "setting": "opener",
            "picture": picture(element.first(is_tag("img"))),
            "opener": _opener(element),
        }
    figure = element if element.name == "figure" else element.first(is_tag("figure", PLATE_CLASS))
    spec: dict[str, Any] = {"picture": picture(figure.first(is_tag("img"))), "figure": _plate_figure(figure)}
    if figure.has_class(MASTHEAD_CLASS):
        return {**spec, "setting": "masthead", "masthead": _masthead(figure, found)}
    if element.has_class(ROW_CLASS):
        row = {
            "classes": _other_classes(element, ROW_CLASS),
            "note": slot_unit(element.first(is_tag("p", "note-p"))),
        }
        return {**spec, "setting": "row", "row": row}
    if element is not figure:
        quote = element.first(has_classes(PULL_BOX)).first(is_tag("blockquote"))
        pull = {
            "classes": element.classes,
            "box": PULL_BOX,
            "quote": slot_unit(quote.first(is_tag("p"))),
            "attribution": held_text_or_unit(quote.first(is_tag("footer")), found.sources),
        }
        return {**spec, "setting": "pull", "pull": pull}
    return {**spec, "setting": "figure"}


def _plate_figure(figure: Element) -> dict[str, Any]:
    frame = figure.first(has_classes("ph"))
    crops = _other_classes(frame, "ph")
    caption = figure.first(is_tag("figcaption"))
    lines = caption.elements()
    if not lines or not lines[-1].has_class("credit"):
        raise InvalidInput("A plate's caption ends with its credit")
    return {
        "classes": _other_classes(figure, PLATE_CLASS, MASTHEAD_CLASS),
        "crop": crops[0] if crops else None,
        "captions": [{"unit": slot_unit(line), "look": line.has_class("kv-look")} for line in lines[:-1]],
        "credit": slot_unit(lines[-1]),
    }


def _opener(element: Element) -> dict[str, Any]:
    label = element.first(has_classes("op-label"))
    title = label.first(is_tag("h2"))
    return {
        "chapterNo": slot_unit(label.first(has_classes("chapter-no"))),
        "kicker": slot_unit(label.first(has_classes("op-kicker"))),
        "title": slot_unit(title),
        "titleId": title.attrs["id"],
        "dek": slot_unit(label.first(has_classes("op-dek"))),
        "credit": slot_unit(element.first(has_classes("op-credit"))),
    }


def _masthead(figure: Element, found: Found) -> dict[str, Any]:
    label = figure.first(has_classes("mast-label"))
    seal = label.first(has_classes("seal"))
    meta = label.first(has_classes("lc-meta")).elements()
    provenance = label.first(has_classes("lc-prov")).elements()
    sources = SOURCES_LINE.fullmatch(provenance[0].text())
    if sources is None:
        raise InvalidInput("The masthead's provenance names how many sources the monograph draws from")
    grades = [
        {
            "grade": " ".join(_other_classes(group.first(has_classes("rel")), "rel")),
            "count": int(group.text().split()[-1]),
        }
        for group in provenance[1].all(has_classes("rs-g"))
    ]
    graded = ", ".join(f"{grade['count']} graded {grade['grade']}" for grade in grades)
    if provenance[1].attrs["aria-label"] != f"Reliability of the {sources.group(1)} sources: {graded}":
        raise InvalidInput("The reliability strip names other counts than its groups show")
    return {
        "kicker": slot_unit(label.first(has_classes("lc-k"))),
        "title": slot_unit(label.first(has_classes("lc-title"))),
        "seal": drawing(seal.first(is_tag("svg"))),
        "registration": held_or_unit(
            [child for child in seal.children if not _is_drawing(child)], found.sources
        ),
        "place": meta[1].text(),
        "sources": int(sources.group(1)),
        "grades": grades,
        "curated": shown_day(provenance[2].text(), CURATED_LINE),
    }


def specimen_plate(found: Found) -> dict[str, Any]:
    hero = found.element
    label = hero.first(is_tag("aside"))
    name = label.first(has_classes("lc-name"))
    button = label.first(is_tag("button"))
    status = label.first(has_classes("vh"))
    return {
        "picture": picture(hero.first(is_tag("img"))),
        "phase": hero.attrs["data-phase"],
        "kicker": slot_unit(label.first(has_classes("lc-k"))),
        "name": slot_unit(name),
        "nameId": name.attrs["id"],
        "sentence": slot_unit(label.first(has_classes("lc-s"))),
        "replay": {"label": button.text(), "statusId": status.attrs["id"], "status": slot_unit(status)},
        "credit": slot_unit(label.first(has_classes("lc-credit"))),
    }


def label_card(found: Found) -> dict[str, Any]:
    card = found.element
    variant = " ".join(_other_classes(card, "label-card"))
    seal = card.first(has_classes(f"{variant}-seal"))
    facts = card.first(has_classes(f"{variant}-facts")).elements()
    insets = [label for part in card.elements() if (label := found.component_at(part))]
    return {
        "variant": variant,
        "kicker": slot_unit(card.first(has_classes("lc-k", f"{variant}-k"))),
        "seal": drawing(seal.first(is_tag("svg"))),
        "sentence": slot_unit(seal.first(has_classes("lc-s"))),
        "inset": insets[0] if insets else None,
        "facts": [
            {"term": slot_unit(fact.first(is_tag("dt"))), "value": slot_unit(fact.first(is_tag("dd")))}
            for fact in facts
        ],
    }


def swatch_cards(found: Found) -> dict[str, Any]:
    section = found.element
    title = section.first(is_tag("h2"))
    colours = section.all(is_tag("li", "colour"))
    return {
        "chapterNo": slot_unit(section.first(has_classes("chapter-no"))),
        "title": slot_unit(title),
        "titleId": title.attrs["id"],
        "intro": slot_unit(section.first(has_classes("four-intro"))),
        "weave": url_reference(colours[0].all(is_tag("rect"))[1].attrs["fill"]),
        "colours": [_colour(colour) for colour in colours],
    }


def _colour(colour: Element) -> dict[str, Any]:
    pair = colour.first(has_classes("pair")).elements()
    return {
        "before": _swatch(pair[0]),
        "join": JOINS[pair[1].text()],
        "after": _swatch(pair[2]),
        "name": slot_unit(colour.first(is_tag("h3"))),
        "agent": slot_unit(colour.first(has_classes("agent"))),
        "text": slot_unit(colour.first(has_classes("ctext"))),
    }


def _swatch(figure: Element) -> dict[str, Any]:
    ground = figure.first(is_tag("rect"))
    return {
        "dye": dye_variable(ground.attrs["fill"]),
        "caption": slot_unit(figure.first(is_tag("figcaption"))),
    }


def swatch_pair(found: Found) -> dict[str, Any]:
    card = found.element
    pair = card.first(has_classes("ws-vis")).elements()[0]
    frames = pair.all(has_classes("sw-frame"))
    button = card.first(has_classes("ws-go")).first(is_tag("button"))
    return {
        "id": card.attrs["id"],
        "wide": card.has_class("wide"),
        "pairClass": " ".join(pair.classes),
        "description": pair.attrs["aria-label"],
        "weave": url_reference(frames[0].first(is_tag("svg")).elements()[-1].attrs["fill"]),
        "swatches": [_pair_swatch(frame) for frame in frames],
        "when": slot_unit(card.first(has_classes("when"))),
        "title": slot_unit(card.first(is_tag("h3"))),
        "texts": [slot_unit(text) for text in card.all(has_classes("ws-t"))],
        "go": {"stage": int(button.attrs["data-goto-stage"]), "label": held_text(button, found.sources)},
    }


def _pair_swatch(frame: Element) -> dict[str, Any]:
    shapes = frame.first(is_tag("svg")).elements()
    return {
        "ground": dye_variable(shapes[0].attrs["fill"]),
        "motif": [drawing(shape) for shape in shapes[1:-1]],
        "label": frame.first(is_tag("b")).text(),
    }


def credits(found: Found) -> dict[str, Any]:
    parts = found.element.elements()
    groups = []
    for title, listed in zip(parts[::2], parts[1::2], strict=True):
        lines = [_credit_line(item, found) for item in listed.elements()]
        groups.append(
            {"title": slot_unit(title), "listClass": listed.attrs.get("class") or None, "lines": lines}
        )
    return {"groups": groups}


def _credit_line(item: Element, found: Found) -> dict[str, Any]:
    try:
        return {"unit": slot_unit(item)}
    except InvalidInput:
        return {"text": held_text(item, found.sources)}


def _other_classes(element: Element, *known: str) -> list[str]:
    return [cls for cls in element.classes if cls not in known]


def _is_drawing(node: object) -> bool:
    return isinstance(node, Element) and node.name == "svg"


PLATES = SpecGroup(
    name="plates",
    models=SPEC_MODELS_PLATES,
    extractors={
        "picture_plate": picture_plate,
        "specimen_plate": specimen_plate,
        "label_card": label_card,
        "swatch_cards": swatch_cards,
        "swatch_pair": swatch_pair,
        "credits": credits,
        **MEDIA_EXTRACTORS,
    },
)


def main(argv: list[str] | None = None) -> int:
    return run_group(PLATES, argv)


if __name__ == "__main__":
    raise SystemExit(main())
