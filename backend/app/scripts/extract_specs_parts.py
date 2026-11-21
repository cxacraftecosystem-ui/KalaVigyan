from __future__ import annotations

import datetime
import re
from collections.abc import Iterable, Mapping
from typing import Any

from app.core.errors import InvalidInput
from app.research.monograph_page import ITALIC_ROLES, MARK_TAGS, CitedSource

from .extract_specs_markup import Element, Node

__all__ = [
    "SLOT_TAG",
    "child_with",
    "drawing",
    "dye_variable",
    "figure_head",
    "held_cite",
    "held_nodes",
    "held_or_unit",
    "held_text",
    "held_text_or_unit",
    "picture",
    "placed",
    "shown_day",
    "slot_unit",
    "slot_units",
    "style_of",
    "text_line",
    "texts",
    "url_reference",
]

URL_REFERENCE = re.compile(r"url\(#([A-Za-z][A-Za-z0-9_:.-]*)\)")
DYE_VARIABLE = re.compile(r"var\(--dye-([a-z-]+)\)")
DAY_FORMAT = "%d %b %Y"
SLOT_TAG = "kv-slot"
SLOT_KIND = "unit"
TEXT_HOLDING_TAGS = frozenset({"text", "tspan", "title", "desc"})
PICTURE_FIELDS = (("loading", "loading"), ("fetchpriority", "fetchPriority"), ("decoding", "decoding"))
SENTENCE_FIELDS = (("data-src", "src"), ("data-sid", "sid"), ("data-pair", "pair"))
LINK_FIELDS = (("rel", "rel"), ("target", "target"), ("data-ask", "ask"), ("lang", "lang"))
SENTENCE_CLASS = "s"
UNBROKEN_CLASS = "nw"
CITE_CLASS = "kcite"
FIGREF_CLASS = "kv-figref"


def slot_unit(element: Element) -> str:
    content = _content(element)
    if len(content) != 1 or not isinstance(content[0], Element) or content[0].name != SLOT_TAG:
        raise InvalidInput(f"<{element.tag} class={element.attrs.get('class')!r}> holds more than one unit")
    return content[0].attrs[SLOT_KIND]


def slot_units(element: Element) -> list[str]:
    return [found.attrs[SLOT_KIND] for found in element.walk() if found.name == SLOT_TAG]


def texts(element: Element) -> list[str]:
    return [child.strip() for child in element.children if isinstance(child, str) and child.strip()]


def picture(image: Element) -> dict[str, Any]:
    shown: dict[str, Any] = {
        "src": image.attrs["src"],
        "width": int(image.attrs["width"]),
        "height": int(image.attrs["height"]),
        "alt": image.attrs["alt"],
    }
    shown.update({field: image.attrs[name] for name, field in PICTURE_FIELDS if name in image.attrs})
    return shown


def drawing(element: Element) -> dict[str, Any]:
    keeps_text = element.tag in TEXT_HOLDING_TAGS
    children = [
        drawing(child) if isinstance(child, Element) else child
        for child in element.children
        if isinstance(child, Element) or keeps_text or child.strip()
    ]
    return {"tag": element.tag, "attrs": dict(element.attrs), "children": children}


def held_text(element: Element, sources: Mapping[str, CitedSource]) -> list[Any]:
    return held_nodes(element.children, sources)


def text_line(element: Element, sources: Mapping[str, CitedSource]) -> dict[str, Any]:
    line: dict[str, Any] = {"tag": element.name, "classes": element.classes}
    content = _content(element)
    if not content:
        return line
    if len(content) == 1 and isinstance(content[0], Element) and content[0].name == SLOT_TAG:
        return {**line, "unit": content[0].attrs[SLOT_KIND]}
    return {**line, "text": held_text(element, sources)}


def _content(element: Element) -> list[Node]:
    return [child for child in element.children if not (isinstance(child, str) and not child.strip())]


def child_with(element: Element, cls: str) -> Element | None:
    return next((child for child in element.elements() if child.has_class(cls)), None)


def figure_head(figure: Element) -> dict[str, Any]:
    number, title, dek = (child_with(figure, cls) for cls in ("fig-no", "chart-title", "chart-dek"))
    if title is None:
        raise InvalidInput(f"<{figure.tag} class={figure.attrs.get('class')!r}> has no chart title")
    return {
        "number": {"unit": slot_unit(number), "ref": number.attrs["data-fig"]} if number else None,
        "title": slot_unit(title),
        "titleId": title.attrs.get("id"),
        "dek": slot_unit(dek) if dek else None,
        "dekId": dek.attrs.get("id") if dek else None,
    }


def style_of(element: Element) -> dict[str, str]:
    rules = (rule.split(":", 1) for rule in element.attrs.get("style", "").split(";") if ":" in rule)
    return {name.strip(): value.strip() for name, value in rules}


def placed(element: Element, sources: Mapping[str, CitedSource]) -> dict[str, Any]:
    style = style_of(element)
    return {
        "classes": element.classes,
        "left": style.get("left"),
        "width": style.get("width"),
        "top": style.get("top"),
        "hidden": element.attrs.get("aria-hidden") == "true",
        "text": held_text(element, sources) if element.children else None,
    }


def held_nodes(nodes: Iterable[Node], sources: Mapping[str, CitedSource]) -> list[Any]:
    return [_held(node, sources) for node in nodes]


def held_or_unit(nodes: Iterable[Node], sources: Mapping[str, CitedSource]) -> str | list[Any]:
    found = [node for node in nodes if not (isinstance(node, str) and not node.strip())]
    if len(found) == 1 and isinstance(found[0], Element) and found[0].name == SLOT_TAG:
        return found[0].attrs[SLOT_KIND]
    return held_nodes(nodes, sources)


def held_text_or_unit(element: Element, sources: Mapping[str, CitedSource]) -> str | list[Any]:
    return held_or_unit(element.children, sources)


def url_reference(value: str) -> str:
    found = URL_REFERENCE.fullmatch(value)
    if not found:
        raise InvalidInput(f"{value!r} is not a reference to an element of the page")
    return found.group(1)


def dye_variable(value: str) -> str:
    found = DYE_VARIABLE.fullmatch(value)
    if not found:
        raise InvalidInput(f"{value!r} is not a dye specimen variable")
    return found.group(1)


def shown_day(text: str, pattern: re.Pattern[str]) -> datetime.date:
    found = pattern.fullmatch(text.strip())
    if not found:
        raise InvalidInput(f"{text!r} names no day in the form {pattern.pattern}")
    return datetime.datetime.strptime(found.group("day"), DAY_FORMAT).replace(tzinfo=datetime.UTC).date()


def _held(node: Node, sources: Mapping[str, CitedSource]) -> Any:
    if isinstance(node, str):
        return node
    if node.name == "span":
        return _held_span(node, sources)
    if node.name == "i":
        role = " ".join(node.classes)
        if role and role not in ITALIC_ROLES:
            raise InvalidInput(f"No italic role {role!r}")
        return _mark("i", node, sources, role=role or None)
    if node.name in MARK_TAGS:
        return _mark(node.name, node, sources)
    if node.name == "a":
        return _held_link(node, sources)
    raise InvalidInput(f"Held text has no mark for <{node.tag}>")


def _held_span(span: Element, sources: Mapping[str, CitedSource]) -> Any:
    if span.has_class(UNBROKEN_CLASS):
        return held_cite(span, sources)
    if span.has_class(FIGREF_CLASS):
        return _mark("figref", span, sources, ref=span.attrs["data-figref"])
    if span.has_class(SENTENCE_CLASS):
        extra = " ".join(cls for cls in span.classes if cls != SENTENCE_CLASS)
        fields = {field: span.attrs[name] for name, field in SENTENCE_FIELDS if name in span.attrs}
        return _mark("s", span, sources, cls=extra or None, **fields)
    return _mark("span", span, sources, cls=span.attrs.get("class") or None)


def _held_link(link: Element, sources: Mapping[str, CitedSource]) -> Any:
    if link.attrs.get("class"):
        return _mark("link", link, sources, cls=link.attrs["class"], href=link.attrs["href"])
    fields = {field: link.attrs[name] for name, field in LINK_FIELDS if name in link.attrs}
    return _mark("link", link, sources, href=link.attrs["href"], **fields)


def held_cite(span: Element, sources: Mapping[str, CitedSource]) -> Any:
    button = span.elements()[-1]
    if not button.has_class(CITE_CLASS):
        raise InvalidInput("An unbroken span in held text ends in its citation button")
    keys = button.attrs["data-g"].split()
    missing = [key for key in keys if key not in sources]
    if missing:
        raise InvalidInput(f"Citation {button.attrs['data-c']} names unknown sources {missing}")
    shown = sorted({sources[key].number: sources[key].title for key in keys}.items())
    if ",".join(str(number) for number, _ in shown) != button.text():
        raise InvalidInput(f"Citation {button.attrs['data-c']} shows other numbers than its sources")
    inner = [_held(child, sources) for child in span.children if child is not button]
    return {
        "m": "cite",
        "key": button.attrs["data-c"],
        "g": keys,
        "shown": [{"number": number, "title": title} for number, title in shown],
        "c": inner,
    }


def _mark(mark: str, element: Element, sources: Mapping[str, CitedSource], **fields: str | None) -> Any:
    node: dict[str, Any] = {"m": mark}
    node.update({name: value for name, value in fields.items() if value is not None})
    node["c"] = [_held(child, sources) for child in element.children]
    return node
