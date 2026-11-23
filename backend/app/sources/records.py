from __future__ import annotations

import re
from collections.abc import Iterable
from datetime import date
from html import unescape
from html.parser import HTMLParser
from typing import Any

from app.models.knowledge import CONTAINER_TITLE_CHARS
from app.research.base import PARTIAL_DATE_PATTERN, https_url
from app.research.evidence import DOI_PATTERN

__all__ = [
    "AUTHORS_MAX",
    "WORK_KINDS",
    "UnusableRecord",
    "classify",
    "clean_text",
    "doi_of",
    "doi_url",
    "https_or_none",
    "journal_of",
    "markup_text",
    "partial_date_of",
    "published_since",
    "query_terms",
    "title_of",
]

AUTHORS_MAX = 50
QUERY_TERMS_MAX = 8
QUERY_TERM = re.compile(r"[^\W_]+")
WORK_KINDS: dict[str, tuple[str, str]] = {
    "article": ("PAPER", "A"),
    "book": ("BOOK", "A"),
    "chapter": ("BOOK_CHAPTER", "A"),
    "preprint": ("PAPER", "B"),
    "repository": ("PAPER", "B"),
    "dataset": ("DATASET", "B"),
    "thesis": ("OTHER", "B"),
    "report": ("OTHER", "B"),
    "other": ("OTHER", "C"),
}
DOI_PREFIXES = ("https://doi.org/", "http://doi.org/", "https://dx.doi.org/", "http://dx.doi.org/", "doi:")
ISO_DATE_PREFIX = re.compile(r"^(\d{4})(?:-(\d{2}))?(?:-(\d{2}))?")


class UnusableRecord(ValueError):
    pass


def classify(work_kind: str) -> tuple[str, str]:
    if work_kind not in WORK_KINDS:
        raise ValueError(f"Unknown work kind {work_kind!r}; use one of {sorted(WORK_KINDS)}")
    return WORK_KINDS[work_kind]


def clean_text(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    text = " ".join(value.split())
    return text or None


def query_terms(text: str) -> list[str]:
    return QUERY_TERM.findall(text)[:QUERY_TERMS_MAX]


def title_of(value: Any) -> str:
    if isinstance(value, list):
        value = next((entry for entry in value if clean_text(entry)), None)
    title = markup_text(value)
    if title is None:
        raise UnusableRecord("no title")
    return title


def journal_of(value: Any) -> str | None:
    names = value if isinstance(value, list | tuple) else [value]
    found = next((name for name in (markup_text(entry) for entry in names) if name), None)
    return found if found is not None and len(found) <= CONTAINER_TITLE_CHARS else None


def markup_text(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    reader = _TextReader()
    reader.feed(value)
    reader.close()
    return clean_text(unescape("".join(reader.parts)))


def doi_of(value: Any) -> str | None:
    text = clean_text(value)
    if text is None:
        return None
    lowered = text.lower()
    for prefix in DOI_PREFIXES:
        if lowered.startswith(prefix):
            text = text[len(prefix) :]
            break
    return text if re.fullmatch(DOI_PATTERN, text) else None


def doi_url(doi: str) -> str:
    return f"https://doi.org/{doi}"


def https_or_none(value: Any) -> str | None:
    text = clean_text(value)
    if text is None:
        return None
    try:
        return https_url(text)
    except ValueError:
        return None


def partial_date_of(value: Any) -> str | None:
    if isinstance(value, int) and not isinstance(value, bool):
        return _checked_date(f"{value:04d}")
    if isinstance(value, list | tuple):
        return _date_from_parts(value)
    text = clean_text(value)
    match = ISO_DATE_PREFIX.match(text or "")
    if match is None:
        return None
    return _checked_date("-".join(part for part in match.groups() if part))


def published_since(published: str | None, cutoff: date) -> bool:
    if published is None:
        return False
    parts = [int(part) for part in published.split("-")]
    latest = [*parts, 12, 31] if len(parts) == 1 else [*parts, 31]
    return tuple(latest[:3]) >= (cutoff.year, cutoff.month, cutoff.day)


def _date_from_parts(parts: Iterable[Any]) -> str | None:
    numbers = [part for part in parts if isinstance(part, int) and not isinstance(part, bool)]
    if not numbers:
        return None
    text = f"{numbers[0]:04d}" + "".join(f"-{part:02d}" for part in numbers[1:3])
    return _checked_date(text)


def _checked_date(text: str) -> str | None:
    return text if re.fullmatch(PARTIAL_DATE_PATTERN, text) else None


class _TextReader(HTMLParser):
    BLOCK_TAGS = frozenset({"p", "div", "br", "li", "title", "sec", "jats:p", "jats:title", "jats:sec"})
    HIDDEN_TAGS = frozenset({"script", "style"})
    VOID_TAGS = frozenset({"br", "hr", "img", "input", "meta", "link", "wbr", "source", "area", "col"})

    def __init__(self) -> None:
        super().__init__(convert_charrefs=False)
        self.parts: list[str] = []
        self._hidden_tag: str | None = None
        self._hidden_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if self._hidden_tag is not None:
            self._hidden_depth += tag == self._hidden_tag
            return
        if tag not in self.VOID_TAGS and (tag in self.HIDDEN_TAGS or _hides(attrs)):
            self._hidden_tag, self._hidden_depth = tag, 1
            return
        if tag in self.BLOCK_TAGS:
            self.parts.append(" ")

    def handle_endtag(self, tag: str) -> None:
        if self._hidden_tag is not None:
            self._hidden_depth -= tag == self._hidden_tag
            if self._hidden_depth == 0:
                self._hidden_tag = None
            return
        if tag in self.BLOCK_TAGS:
            self.parts.append(" ")

    def handle_data(self, data: str) -> None:
        self._keep(data)

    def handle_entityref(self, name: str) -> None:
        self._keep(f"&{name};")

    def handle_charref(self, name: str) -> None:
        self._keep(f"&#{name};")

    def _keep(self, text: str) -> None:
        if self._hidden_tag is None:
            self.parts.append(text)


def _hides(attrs: list[tuple[str, str | None]]) -> bool:
    for name, value in attrs:
        if name == "hidden":
            return True
        if name == "style" and value and "display:none" in "".join(value.lower().split()):
            return True
    return False
