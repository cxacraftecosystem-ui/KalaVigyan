from __future__ import annotations

import re

import trafilatura
from app.curation.matching import match_key, quote_found
from app.fetcher.extract import HIDDEN_STYLE, HIDDEN_XPATH
from lxml import html as lxml_html

__all__ = [
    "CELL_CHARS_MAX",
    "CELL_SEPARATOR",
    "DATA_ROWS_MIN",
    "missing_table_rows",
    "table_rows",
    "with_table_rows",
]

CELL_CHARS_MAX = 1000
DATA_ROWS_MIN = 2
CELL_SEPARATOR = " | "
BREAKING_TAGS = frozenset(
    {
        "br",
        "p",
        "div",
        "li",
        "ul",
        "ol",
        "dl",
        "dt",
        "dd",
        "h1",
        "h2",
        "h3",
        "h4",
        "h5",
        "h6",
        "pre",
        "blockquote",
    }
)
WHITESPACE = re.compile(r"\s+")


def with_table_rows(body: bytes, text: str, truncated: bool, *, max_chars: int) -> tuple[str, bool]:
    rows = missing_table_rows(body, text)
    if not rows:
        return text, truncated
    joined = "\n".join([text, *rows])
    return joined[:max_chars], truncated or len(joined) > max_chars


def missing_table_rows(body: bytes, text: str) -> list[str]:
    key = match_key(text)
    return [
        _line(cells)
        for cells in dict.fromkeys(table_rows(body))
        if not quote_found(CELL_SEPARATOR.join(cells).strip(), key)
    ]


def table_rows(body: bytes) -> list[tuple[str, ...]]:
    tree = trafilatura.load_html(body)
    if tree is None:
        return []
    _drop_hidden(tree)
    rows = []
    for table in tree.iter("table"):
        if next(table.iterdescendants("table"), None) is None:
            rows += _data_rows(table)
    return rows


def _data_rows(table: lxml_html.HtmlElement) -> list[tuple[str, ...]]:
    rows = [tuple(_cell_text(cell) for cell in row.xpath("./th|./td")) for row in table.iter("tr")]
    filled = [row for row in rows if any(row)]
    paired = sum(1 for row in filled if sum(1 for cell in row if cell) >= 2)
    short = all(len(cell) <= CELL_CHARS_MAX for row in filled for cell in row)
    return filled if paired >= DATA_ROWS_MIN and short else []


def _cell_text(cell: lxml_html.HtmlElement) -> str:
    parts: list[str] = []
    _collect(cell, parts)
    return WHITESPACE.sub(" ", "".join(parts)).strip()


def _collect(element: lxml_html.HtmlElement, parts: list[str]) -> None:
    breaking = element.tag in BREAKING_TAGS
    parts.append(" " if breaking else "")
    parts.append(element.text or "")
    for child in element:
        if isinstance(child.tag, str):
            _collect(child, parts)
        parts.append(child.tail or "")
    parts.append(" " if breaking else "")


def _line(cells: tuple[str, ...]) -> str:
    return "| " + CELL_SEPARATOR.join(cells) + " |"


def _drop_hidden(tree: lxml_html.HtmlElement) -> None:
    hidden = list(tree.xpath(HIDDEN_XPATH))
    hidden += [node for node in tree.xpath("//*[@style]") if HIDDEN_STYLE.search(node.get("style", ""))]
    for node in hidden:
        if node.getparent() is not None:
            node.drop_tree()
