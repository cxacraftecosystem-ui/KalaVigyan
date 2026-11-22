from __future__ import annotations

import re
from dataclasses import dataclass
from xml.etree import ElementTree

from app.core.errors import InvalidInput

from .drawing_rules import drawing_problems, listed

__all__ = [
    "SVG",
    "SVG_BYTES_MAX",
    "SVG_KEPT_ELEMENTS",
    "SVG_POLICY",
    "CleanSvg",
    "clean_svg",
    "looks_like_svg",
]

SVG = "image/svg+xml"
SVG_BYTES_MAX = 2 * 1024 * 1024
SVG_POLICY = "default-src 'none'; style-src 'unsafe-inline'; sandbox"
SVG_NS = "http://www.w3.org/2000/svg"
XLINK_NS = "http://www.w3.org/1999/xlink"
XML_NS = "http://www.w3.org/XML/1998/namespace"
SVG_KEPT_ELEMENTS = frozenset(
    {
        "svg",
        "g",
        "defs",
        "symbol",
        "use",
        "path",
        "rect",
        "circle",
        "ellipse",
        "line",
        "polyline",
        "polygon",
        "text",
        "tspan",
        "textPath",
        "title",
        "desc",
        "linearGradient",
        "radialGradient",
        "stop",
        "pattern",
        "clipPath",
        "mask",
        "marker",
        "style",
        "filter",
        "feBlend",
        "feColorMatrix",
        "feComponentTransfer",
        "feComposite",
        "feDisplacementMap",
        "feDropShadow",
        "feFlood",
        "feFuncA",
        "feFuncB",
        "feFuncG",
        "feFuncR",
        "feGaussianBlur",
        "feMerge",
        "feMergeNode",
        "feMorphology",
        "feOffset",
        "feTurbulence",
    }
)
KEPT_FOREIGN_ATTRIBUTES = frozenset({f"{{{XML_NS}}}space", f"{{{XML_NS}}}lang"})
LINK_ATTRIBUTES = frozenset({"href", f"{{{XLINK_NS}}}href"})
DECLARED_TYPES = re.compile(rb"<!\s*(DOCTYPE|ENTITY)", re.IGNORECASE)
OPENING = re.compile(rb"^\s*(<\?xml[^>]*\?>\s*)?(<!--.*?-->\s*)*<svg[\s>]", re.DOTALL)
OUTSIDE_URL = re.compile(r"url\(\s*(?![\"']?\s*#)[^)]*\)", re.IGNORECASE)
IMPORTS = re.compile(r"@import[^;]*;?", re.IGNORECASE)
SCRIPTED = re.compile(r"(javascript|vbscript|data)\s*:|expression\s*\(", re.IGNORECASE)
LENGTH = re.compile(r"^\s*(\d+(?:\.\d+)?)\s*(px)?\s*$")
UTF8_MARK = b"\xef\xbb\xbf"

ElementTree.register_namespace("", SVG_NS)
ElementTree.register_namespace("xlink", XLINK_NS)


@dataclass(frozen=True)
class CleanSvg:
    data: bytes
    width: int
    height: int


def looks_like_svg(data: bytes) -> bool:
    return bool(OPENING.match(data.removeprefix(UTF8_MARK)[:4096]))


def clean_svg(data: bytes) -> CleanSvg:
    if len(data) > SVG_BYTES_MAX:
        raise InvalidInput(f"A contributed SVG is at most {SVG_BYTES_MAX // (1024 * 1024)} MB")
    if DECLARED_TYPES.search(data):
        raise InvalidInput("An SVG with a document type or entities is refused")
    try:
        root = ElementTree.fromstring(data.removeprefix(UTF8_MARK))
    except ElementTree.ParseError:
        raise InvalidInput("The SVG is not well-formed XML") from None
    if root.tag != f"{{{SVG_NS}}}svg":
        raise InvalidInput("The file is not an SVG drawing")
    _clean(root)
    width, height = _size(root)
    problems = drawing_problems(root, float(width))
    if problems:
        raise InvalidInput(f"A contributed SVG speaks only the design's vocabulary: {listed(problems)}")
    return CleanSvg(ElementTree.tostring(root, encoding="utf-8", xml_declaration=False), width, height)


def _clean(element: ElementTree.Element) -> None:
    for child in list(element):
        if not _kept(child):
            element.remove(child)
            continue
        _clean(child)
    _clean_attributes(element)
    if _local(element.tag) == "style" and element.text:
        element.text = _clean_css(element.text)


def _kept(element: ElementTree.Element) -> bool:
    tag = element.tag
    return isinstance(tag, str) and tag.startswith(f"{{{SVG_NS}}}") and _local(tag) in SVG_KEPT_ELEMENTS


def _clean_attributes(element: ElementTree.Element) -> None:
    for name, value in list(element.attrib.items()):
        if not _kept_attribute(name, value):
            del element.attrib[name]
        elif name == "style":
            element.attrib[name] = _clean_css(value)


def _kept_attribute(name: str, value: str) -> bool:
    if name in LINK_ATTRIBUTES:
        return value.strip().startswith("#")
    if name.startswith("{"):
        return name in KEPT_FOREIGN_ATTRIBUTES
    if name.lower().startswith("on") or SCRIPTED.search(value):
        return False
    return name == "style" or not OUTSIDE_URL.search(value)


def _size(root: ElementTree.Element) -> tuple[int, int]:
    box = _numbers(root.attrib.get("viewBox", "").replace(",", " ").split())
    if len(box) == 4 and box[2] > 0 and box[3] > 0:
        return round(box[2]), round(box[3])
    sides = [LENGTH.match(root.attrib.get(side, "")) for side in ("width", "height")]
    width, height = (float(side.group(1)) if side else 0.0 for side in sides)
    if width > 0 and height > 0:
        return round(width), round(height)
    raise InvalidInput("An SVG names its size in a viewBox or in its width and height")


def _numbers(words: list[str]) -> list[float]:
    try:
        return [float(word) for word in words]
    except ValueError:
        return []


def _clean_css(text: str) -> str:
    return IMPORTS.sub("", OUTSIDE_URL.sub("none", text))


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]
