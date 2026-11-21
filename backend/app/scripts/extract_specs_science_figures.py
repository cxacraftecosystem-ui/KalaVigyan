from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any

from app.core.errors import InvalidInput
from app.research.monograph_page import CitedSource

from .extract_specs_markup import Element as MarkupElement, Node as MarkupNode
from .extract_specs_parts import held_cite
from .extract_specs_science_chem import equation_line, figure_head, grouped_line, tick_count
from .extract_specs_science_dom import Element
from .extract_specs_science_read import drawing, expect, kids, only, rich, styled_unit, text_of, unit_of

__all__ = ["diagram", "equation_card", "molecule_3d", "structure_diagram"]

PUBCHEM_RECORD = re.compile(r"PubChem CID (\d+)")
SWATCH_STYLE = re.compile(r"background(?:-color)?:var\((--[a-z0-9-]+)\)")


def equation_card(element: Element) -> dict[str, Any]:
    inner, box = kids(expect(element, "div", "kv-hyp", "wrap"))
    kicker, title = kids(expect(inner, "div", "kv-hyp-in"))
    mark, line, why = kids(expect(only(expect(box, "div", "bn-spec")), "div", "hyp"))
    return {
        "kicker": unit_of(expect(kicker, "p", "kicker")),
        "title": unit_of(expect(title, "p", "kv-hyp-t")),
        "mark": unit_of(expect(mark, "p", "hyp-mark")),
        "line": equation_line(only(expect(line, "div", "eq", "hyp-eq"))),
        "why": unit_of(expect(why, "p", "hyp-why")),
    }


def diagram(element: Element) -> dict[str, Any]:
    if element.tag == "svg":
        return {"drawing": drawing(element), "chain": None}
    heading, steps = kids(expect(element, "section", "chain"))
    expect(heading, "h2", "chain-h")
    links = [_chain_link(link) for link in kids(expect(steps, "ol", "ch-ol"))]
    return {
        "drawing": None,
        "chain": {"headingId": heading.attrs["id"], "heading": unit_of(heading), "links": links},
    }


def structure_diagram(element: Element, sources: Mapping[str, CitedSource]) -> dict[str, Any]:
    head, grid = kids(expect(element, "figure", "fig", "chemfig", "redfig"))
    paragraphs = kids(expect(head, "figcaption", "fig-head"))
    dek_style = [name for name in paragraphs[-1].classes if name != "chart-dek"]
    column, side = kids(expect(grid, "div", "anth-grid"))
    scale, pair = kids(expect(column, "div", "anth-col"))
    return {
        "id": element.attrs["id"],
        "head": figure_head(paragraphs),
        "dekStyle": " ".join(dek_style) or None,
        "scale": unit_of(expect(scale, "p", "scale-k")),
        "molecules": [_structure(molecule, sources) for molecule in kids(expect(pair, "div", "anth-pair"))],
        **_structure_side(expect(side, "div", "anth-side")),
    }


def molecule_3d(element: Element) -> dict[str, Any]:
    *paragraphs, body, key = kids(element)
    side: list[dict[str, Any]] = []
    if body.has_class("mol-split"):
        body, notes = kids(expect(body, "div", "mol-split"))
        side = [styled_unit(note) for note in kids(expect(notes, "div", "mol-side"))]
    molecules = [_model(model) for model in kids(body)]
    expect(body, "div", "mol-grid", f"n{len(molecules)}")
    expect(element, "figure", *(["mols", "mol-two"] if side else ["mols"]))
    return {
        "head": figure_head(paragraphs),
        "molecules": molecules,
        "side": side,
        "key": [_key_item(item) for item in kids(expect(key, "p", "atomkey"))],
    }


def _chain_link(link: Element) -> dict[str, Any]:
    kicker, *parts = kids(link)
    styles = [name for name in link.classes if name != "ch"]
    expect(link, "li", "ch", *styles)
    return {
        "style": " ".join(styles) or None,
        "kicker": unit_of(expect(kicker, "p", "ch-k")),
        "parts": [_chain_part(part) for part in parts],
    }


def _chain_part(part: Element) -> dict[str, Any]:
    if part.tag == "svg":
        return {"part": "drawing", "drawing": drawing(part)}
    if part.tag == "div":
        return _chain_equation(part)
    inner = part.elements
    if len(inner) == 1 and inner[0].tag == "a":
        return _step_link(expect(part, "p", "ch-t"), inner[0])
    return {"part": "text", "text": styled_unit(part)}


def _step_link(paragraph: Element, link: Element) -> dict[str, Any]:
    expect(link, "a", "inline")
    figure, *rest = link.children
    player, step = link.attrs["data-rp-step"].split(":")
    if not isinstance(figure, Element) or rest != [f", step {step}"] or link.attrs["href"] != f"#{player}":
        raise InvalidInput(f"a step link names its player and step: {link.attrs}")
    expect(figure, "span", "kv-figref")
    return {
        "part": "step",
        "player": player,
        "step": int(step),
        "figure": figure.attrs["data-figref"],
        "figureLabel": text_of(figure),
    }


def _chain_equation(box: Element) -> dict[str, Any]:
    styles = [name for name in box.classes if name != "ch-eq"]
    label, line, count = kids(expect(box, "div", "ch-eq", *styles))
    expect(line, "div", "eq-line", "eq-sm")
    return {
        "part": "equation",
        "style": " ".join(styles),
        "label": unit_of(expect(label, "p", "kv-eq-k")),
        "lineLabel": line.attrs["aria-label"],
        **grouped_line(line),
        "count": tick_count(count),
    }


def _structure(molecule: Element, sources: Mapping[str, CitedSource]) -> dict[str, Any]:
    picture, caption = kids(expect(molecule, "figure", "m", "anth"))
    name, formula, note, facts = kids(expect(caption, "figcaption"))
    atoms_term, atoms, record_term, record = kids(expect(facts, "dl", "m-dl"))
    identifier, cite = kids(expect(record, "dd"))
    expect(cite, "button", "kcite")
    return {
        "drawing": drawing(picture),
        "name": text_of(expect(name, "b")),
        "formula": rich(expect(formula, "span", "m-f").children),
        "note": text_of(expect(note, "span", "m-s")),
        "atomsTerm": unit_of(expect(atoms_term, "dt")),
        "atoms": unit_of(expect(atoms, "dd")),
        "recordTerm": unit_of(expect(record_term, "dt")),
        "cid": int(_match(PUBCHEM_RECORD, text_of(expect(identifier, "span")))),
        "recordCite": held_cite(MarkupElement("span", {}, [_markup(cite)]), sources),
    }


def _markup(node: Element | str) -> MarkupNode:
    if isinstance(node, str):
        return node
    return MarkupElement(node.tag, dict(node.attrs), [_markup(child) for child in node.children])


def _structure_side(side: Element) -> dict[str, Any]:
    found: dict[str, Any] = {"notes": [], "key": None, "swatches": [], "swatchNote": None}
    for part in kids(side):
        if part.has_class("m-key"):
            expect(part.children[0], "span", "m-sw")
            found["key"] = "".join(str(piece) for piece in part.children[1:])
        elif part.has_class("whites"):
            *swatches, note = kids(expect(part, "div", "whites"))
            found["swatches"] = [_key_swatch(swatch) for swatch in swatches]
            found["swatchNote"] = styled_unit(note)
        else:
            found["notes"].append(styled_unit(part))
    return found


def _key_swatch(item: Element) -> dict[str, Any]:
    swatch, name = kids(expect(item, "div", "wh"))
    fill = only(expect(swatch, "span", "swatch"))
    return {
        "colour": _match(SWATCH_STYLE, expect(fill, "span", "sw-in").attrs["style"]),
        "label": text_of(name),
    }


def _model(model: Element) -> dict[str, Any]:
    stage, caption = kids(expect(model, "figure", "mol"))
    dial, _tag, _turn = kids(expect(stage, "div", "mol-stage"))
    name, formula, atoms, note = kids(expect(caption, "figcaption"))
    described, _record = kids(expect(atoms, "span", "mc"))
    expect(dial, "div", "mol-dial")
    return {
        "key": name.attrs["id"].removesuffix("-n"),
        "cid": int(model.attrs["data-cid"]),
        "yaw": float(model.attrs["data-yaw"]),
        "pitch": float(model.attrs["data-pitch"]),
        "name": text_of(expect(name, "span", "mn")),
        "dialLabel": dial.attrs["aria-label"],
        "formula": rich(expect(formula, "span", "mf").children),
        "atoms": text_of(described),
        "note": text_of(expect(note, "span", "ms")),
        "drawing": drawing(only(dial)),
    }


def _key_item(item: Element) -> dict[str, Any]:
    marks = item.elements
    swatch = None
    if marks:
        mark = expect(marks[0], "i", *marks[0].classes)
        swatch = "ring" if mark.has_class("ring") else _match(SWATCH_STYLE, mark.attrs["style"])
    return {
        "swatch": swatch,
        "label": "".join(str(piece) for piece in item.children if isinstance(piece, str)),
    }


def _match(pattern: re.Pattern[str], text: str) -> str:
    found = pattern.fullmatch(text)
    if found is None:
        raise InvalidInput(f"{text!r} does not read as {pattern.pattern}")
    return found.group(1)
