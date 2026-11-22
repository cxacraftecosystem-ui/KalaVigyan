from __future__ import annotations

import re
from collections.abc import Iterator
from xml.etree import ElementTree
from xml.sax.saxutils import escape

from .drawing_rules import drawing_problems, listed

__all__ = [
    "DRAWING_MAX_CHARS",
    "KEPT_DRAWING_TAGS",
    "cleaned_svg",
    "drawing_tags",
    "sanitised_svg",
    "svg_view_box",
]

DRAWING_MAX_CHARS = 200_000
SVG_NS = "http://www.w3.org/2000/svg"
XLINK_NS = "http://www.w3.org/1999/xlink"
KEPT_DRAWING_TAGS = frozenset(
    {
        "svg",
        "g",
        "defs",
        "title",
        "desc",
        "path",
        "rect",
        "circle",
        "ellipse",
        "line",
        "polyline",
        "polygon",
        "text",
        "tspan",
        "use",
        "symbol",
        "marker",
        "linearGradient",
        "radialGradient",
        "stop",
        "pattern",
        "mask",
        "clipPath",
    }
)
DECLARATIONS = re.compile(r"<!(DOCTYPE|ENTITY)", re.IGNORECASE)
PROCESSING = re.compile(r"<\?(?!xml\s)", re.IGNORECASE)
ATTRIBUTE_NAME = re.compile(r"^[A-Za-z][A-Za-z0-9:_.-]*$")
VIEW_BOX = re.compile(
    r"^\s*(-?\d+(?:\.\d+)?)[\s,]+(-?\d+(?:\.\d+)?)[\s,]+(\d+(?:\.\d+)?)[\s,]+(\d+(?:\.\d+)?)\s*$"
)
EXTERNAL_URL = re.compile(r"url\(\s*['\"]?(?!#)", re.IGNORECASE)
SCRIPTED = re.compile(r"javascript:|expression\(|@import", re.IGNORECASE)
REFERENCES = frozenset({"href", f"{{{XLINK_NS}}}href"})
SIZE_ATTRIBUTES = frozenset({"width", "height"})
EVENT_PREFIX = "on"
QUOTED = {'"': "&quot;"}


def cleaned_svg(markup: str) -> str:
    clean = sanitised_svg(markup)
    root = ElementTree.fromstring(clean)
    box = svg_view_box(root.get("viewBox"))
    problems = drawing_problems(root, box[2] if box else 0.0)
    if problems:
        raise ValueError(f"A drawing speaks only the design's vocabulary: {listed(problems)}")
    return clean


def sanitised_svg(markup: str) -> str:
    if len(markup) > DRAWING_MAX_CHARS:
        raise ValueError(f"A drawing is at most {DRAWING_MAX_CHARS} characters of SVG")
    if DECLARATIONS.search(markup) or PROCESSING.search(markup):
        raise ValueError("A drawing declares no document type, entity or processing instruction")
    try:
        root = ElementTree.fromstring(markup)
    except ElementTree.ParseError as wrong:
        raise ValueError(f"A drawing is well-formed SVG: {wrong}") from None
    if _local(root.tag) != "svg" or _namespace(root.tag) != SVG_NS:
        raise ValueError("A drawing is one svg element in the SVG namespace")
    if svg_view_box(root.get("viewBox")) is None:
        raise ValueError("A drawing's svg element has a viewBox of four numbers with a positive size")
    _clean(root)
    for name in SIZE_ATTRIBUTES:
        root.attrib.pop(name, None)
    linked = any(_namespace(key) == XLINK_NS for element in root.iter() for key in element.attrib)
    declared = f' xmlns="{SVG_NS}"' + (f' xmlns:xlink="{XLINK_NS}"' if linked else "")
    return _markup(root, declared)


def svg_view_box(value: str | None) -> tuple[float, float, float, float] | None:
    found = VIEW_BOX.match(value or "")
    if found is None:
        return None
    x, y, width, height = (float(part) for part in found.groups())
    return (x, y, width, height) if width > 0 and height > 0 else None


def _clean(element: ElementTree.Element) -> None:
    for child in list(element):
        if not _kept(child):
            element.remove(child)
            continue
        _clean(child)
    for name, value in list(element.attrib.items()):
        if not _safe_attribute(name, value):
            del element.attrib[name]


def _kept(element: ElementTree.Element) -> bool:
    return (
        isinstance(element.tag, str)
        and _namespace(element.tag) == SVG_NS
        and _local(element.tag) in KEPT_DRAWING_TAGS
    )


def _safe_attribute(name: str, value: str) -> bool:
    local = _local(name)
    if not ATTRIBUTE_NAME.match(local) or local.lower().startswith(EVENT_PREFIX):
        return False
    if _namespace(name) not in ("", XLINK_NS):
        return False
    if name in REFERENCES:
        return value.strip().startswith("#")
    folded = "".join(value.split())
    return not (EXTERNAL_URL.search(folded) or SCRIPTED.search(folded))


def _markup(element: ElementTree.Element, declared: str = "") -> str:
    name = _local(element.tag)
    attributes = "".join(
        f' {_attribute_name(key)}="{escape(value, QUOTED)}"' for key, value in element.attrib.items()
    )
    inner = escape(element.text or "") + "".join(
        _markup(child) + escape(child.tail or "") for child in element
    )
    if not inner:
        return f"<{name}{declared}{attributes} />"
    return f"<{name}{declared}{attributes}>{inner}</{name}>"


def _attribute_name(key: str) -> str:
    return f"xlink:{_local(key)}" if _namespace(key) == XLINK_NS else key


def _namespace(name: str) -> str:
    return name[1:].split("}", 1)[0] if name.startswith("{") else ""


def _local(name: str) -> str:
    return name.split("}", 1)[1] if name.startswith("{") else name


def drawing_tags(markup: str) -> Iterator[str]:
    for element in ElementTree.fromstring(markup).iter():
        yield _local(element.tag)
