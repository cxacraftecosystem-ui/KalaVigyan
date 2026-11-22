from __future__ import annotations

from collections.abc import Iterator, Sequence
from xml.etree import ElementTree
from xml.etree.ElementTree import Element

from app.core.errors import ExternalFailure

from ..records import clean_text

__all__ = [
    "BLOCK_NAMES",
    "PARAGRAPH_BREAK",
    "SKIPPED_NAMES",
    "body_with_abstract",
    "first_named",
    "local_name",
    "paragraphs",
    "text_of",
    "xml_root",
]

BLOCK_NAMES = frozenset({"p", "title", "para", "simple-para", "section-title"})
SKIPPED_NAMES = frozenset({"table", "ref-list", "bibliography", "fn-group", "math", "tex-math", "object-id"})
PARAGRAPH_BREAK = "\n\n"


def xml_root(body: bytes, service: str) -> Element:
    try:
        return ElementTree.fromstring(body)
    except ElementTree.ParseError:
        raise ExternalFailure(f"{service} answered with full text that is not XML", service=service) from None


def local_name(tag: object) -> str:
    return str(tag).rsplit("}", 1)[-1]


def first_named(element: Element, name: str) -> Element | None:
    return next((found for found in element.iter() if local_name(found.tag) == name), None)


def text_of(element: Element | None, name: str) -> str | None:
    found = None if element is None else first_named(element, name)
    return None if found is None else clean_text("".join(_texts(found)))


def paragraphs(element: Element | None) -> list[str]:
    found: list[str] = []
    if element is not None:
        _collect(element, found)
    return found


def body_with_abstract(abstract: str | None, body: Sequence[str]) -> str | None:
    if not body:
        return None
    return PARAGRAPH_BREAK.join([abstract, *body] if abstract else body)


def _collect(element: Element, found: list[str]) -> None:
    for child in element:
        name = local_name(child.tag)
        if name in SKIPPED_NAMES:
            continue
        if name not in BLOCK_NAMES:
            _collect(child, found)
            continue
        text = clean_text("".join(_texts(child)))
        if text:
            found.append(text)


def _texts(element: Element) -> Iterator[str]:
    if element.text:
        yield element.text
    for child in element:
        if local_name(child.tag) not in SKIPPED_NAMES:
            yield from _texts(child)
        if child.tail:
            yield child.tail
