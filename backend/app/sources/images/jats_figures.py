from __future__ import annotations

import re
from collections.abc import Iterator
from dataclasses import dataclass
from xml.etree import ElementTree
from xml.etree.ElementTree import Element

from app.core.errors import ExternalFailure

from ..records import clean_text
from ..scholarly.xml_text import first_named, local_name

__all__ = [
    "CDN_BUCKET",
    "THIRD_PARTY_WORDS",
    "JatsFigure",
    "article_licence_url",
    "jats_figures",
    "jats_root",
]

XLINK_HREF = "{http://www.w3.org/1999/xlink}href"
CDN_BUCKET = "cdn"
IMAGE_CONTENT = "image"
CITATION = "bibr"
LICENCE_REF = "license_ref"
LICENCE_URL = re.compile(r"https?://(?:www\.)?creativecommons\.org/[^\s\"'<>]+")
URL_END = ".,;:)]}>"
THIRD_PARTY_WORDS = re.compile(
    r"\b(?:reprinted|reproduced|adapted|permission|permissions|copyright|courtesy)\b", re.IGNORECASE
)


@dataclass(frozen=True)
class JatsFigure:
    label: str | None
    heading: str
    caption: str
    image_path: str
    width: int | None
    height: int | None


def jats_root(body: bytes, service: str) -> Element:
    parser = ElementTree.XMLParser(target=ElementTree.TreeBuilder(insert_pis=True))
    try:
        return ElementTree.fromstring(body, parser=parser)
    except ElementTree.ParseError:
        raise ExternalFailure(f"{service} answered with full text that is not XML", service=service) from None


def article_licence_url(root: Element) -> str | None:
    licence = first_named(root, "license")
    if licence is None:
        return None
    for element in licence.iter():
        named = "".join(element.itertext()) if local_name(element.tag) == LICENCE_REF else None
        for text in (element.get(XLINK_HREF), named):
            found = LICENCE_URL.search(text or "")
            if found is not None:
                return "https://" + found.group(0).rstrip(URL_END).split("://", 1)[1]
    return None


def jats_figures(root: Element) -> Iterator[JatsFigure]:
    for figure in root.iter():
        if local_name(figure.tag) == "fig":
            shown = _figure(figure)
            if shown is not None:
                yield shown


def _figure(figure: Element) -> JatsFigure | None:
    caption = _child(figure, "caption")
    if caption is None or _third_party(figure, caption):
        return None
    image = _cdn_image(figure)
    heading = _text(_child(caption, "title")) or _text(_child(caption, "p"))
    if image is None or heading is None:
        return None
    path, width, height = image
    text = clean_text(" ".join(filter(None, (_text(part) for part in caption)))) or heading
    return JatsFigure(_text(_child(figure, "label")), heading, text, path, width, height)


def _third_party(figure: Element, caption: Element) -> bool:
    if _child(figure, "permissions") is not None:
        return True
    cited = any(
        local_name(element.tag) == "xref" and element.get("ref-type") == CITATION
        for element in caption.iter()
    )
    return cited or THIRD_PARTY_WORDS.search(" ".join(caption.itertext())) is not None


def _cdn_image(figure: Element) -> tuple[str, int | None, int | None] | None:
    for graphic in figure.iter():
        if local_name(graphic.tag) != "graphic" or graphic.get("content-type") not in (None, IMAGE_CONTENT):
            continue
        marks = _instructions(graphic)
        path = marks.get("cloudpmc-path")
        if path and marks.get("cloudpmc-bucket") == CDN_BUCKET:
            return path, _size(marks.get("scaled-width")), _size(marks.get("scaled-height"))
    return None


def _instructions(element: Element) -> dict[str, str]:
    marks: dict[str, str] = {}
    for child in element:
        if child.tag is ElementTree.ProcessingInstruction and child.text:
            target, _, value = child.text.partition(" ")
            marks[target] = value.strip()
    return marks


def _size(value: str | None) -> int | None:
    return int(value) if value and value.isdigit() and int(value) > 0 else None


def _child(element: Element | None, name: str) -> Element | None:
    if element is None:
        return None
    return next((child for child in element if local_name(child.tag) == name), None)


def _text(element: Element | None) -> str | None:
    return None if element is None else clean_text("".join(element.itertext()))
