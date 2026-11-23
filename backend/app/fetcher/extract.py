from __future__ import annotations

import codecs
import re
from dataclasses import dataclass, field
from typing import Any

import trafilatura
from lxml import html as lxml_html

from app.research.fetcher import FETCH_TEXT_MAX_CHARS, FetchRefused, PageMetadata
from app.research.untrusted import clean_untrusted_text
from app.sources.records import AUTHORS_MAX, clean_text, https_or_none, partial_date_of

from .pdf import pdf_text

__all__ = [
    "HTML_TYPES",
    "OCTET_STREAM_TYPES",
    "PDF_SIGNATURE",
    "PDF_TYPE",
    "PLAIN_TYPE",
    "Extracted",
    "content_type_of",
    "extract",
]

HTML_TYPES = frozenset({"text/html", "application/xhtml+xml"})
PDF_TYPE = "application/pdf"
PLAIN_TYPE = "text/plain"
OCTET_STREAM_TYPES = frozenset({"application/octet-stream", "binary/octet-stream"})
PDF_SIGNATURE = b"%PDF-"
HIDDEN_XPATH = (
    "//script|//style|//noscript|//template|//iframe|//object|//embed|//svg|//canvas"
    "|//*[@hidden]|//*[@aria-hidden='true']|//input[@type='hidden']"
)
HIDDEN_STYLE = re.compile(r"display\s*:\s*none|visibility\s*:\s*hidden", re.IGNORECASE)
AUTHOR_SPLIT = re.compile(r"\s*;\s*")


@dataclass(frozen=True)
class Extracted:
    text: str
    truncated: bool
    metadata: PageMetadata = field(default_factory=PageMetadata)


def content_type_of(url: str, media_type: str, body: bytes) -> str:
    if media_type in OCTET_STREAM_TYPES and body.startswith(PDF_SIGNATURE):
        return PDF_TYPE
    if media_type in HTML_TYPES:
        return "text/html"
    if media_type in (PDF_TYPE, PLAIN_TYPE):
        return media_type
    raise FetchRefused(url, "CONTENT_TYPE", f"{media_type or 'no content type'} is not fetched")


def extract(
    url: str, content_type: str, body: bytes, charset: str | None, *, max_chars: int = FETCH_TEXT_MAX_CHARS
) -> Extracted:
    if content_type == PDF_TYPE:
        text, pages_left_out, metadata = pdf_text(url, body)
        return _capped(text, metadata, truncated=pages_left_out, max_chars=max_chars)
    if content_type == PLAIN_TYPE:
        return _capped(_decoded(body, charset), PageMetadata(), truncated=False, max_chars=max_chars)
    return _html(url, body, max_chars=max_chars)


def _html(url: str, body: bytes, *, max_chars: int) -> Extracted:
    try:
        tree = trafilatura.load_html(body)
        if tree is None:
            raise ValueError("no document")
        _drop_hidden(tree)
        document = trafilatura.bare_extraction(
            tree,
            url=url,
            with_metadata=True,
            include_comments=False,
            include_tables=True,
            include_images=False,
            include_links=False,
            favor_precision=True,
        )
    except Exception as error:
        raise FetchRefused(url, "PARSE_FAILED", f"HTML could not be read ({type(error).__name__})") from None
    if document is None or not (document.text or "").strip():
        raise FetchRefused(url, "PARSE_FAILED", "no main text found")
    metadata = _html_metadata(document, tree.get("lang"))
    return _capped(document.text, metadata, truncated=False, max_chars=max_chars)


def _drop_hidden(tree: lxml_html.HtmlElement) -> None:
    hidden = list(tree.xpath(HIDDEN_XPATH))
    hidden += [node for node in tree.xpath("//*[@style]") if HIDDEN_STYLE.search(node.get("style", ""))]
    for node in hidden:
        if node.getparent() is not None:
            node.drop_tree()


def _html_metadata(document: Any, declared_language: str | None) -> PageMetadata:
    authors = [a for a in AUTHOR_SPLIT.split(_short(document.author, 2000) or "") if a][:AUTHORS_MAX]
    return PageMetadata(
        title=_short(document.title, 1000),
        authors=authors,
        published=partial_date_of(document.date),
        licence=_short(document.license, 200),
        canonical_url=https_or_none(document.url),
        site_name=_short(document.sitename, 300),
        language=_short(document.language or declared_language, 16),
    )


def _capped(text: str, metadata: PageMetadata, *, truncated: bool, max_chars: int) -> Extracted:
    cleaned = clean_untrusted_text(text)
    over = len(cleaned) > max_chars
    return Extracted(cleaned[:max_chars], truncated or over, metadata)


def _decoded(body: bytes, charset: str | None) -> str:
    encoding = "utf-8"
    if charset:
        try:
            encoding = codecs.lookup(charset).name
        except LookupError:
            encoding = "utf-8"
    return body.decode(encoding, errors="replace")


def _short(value: Any, limit: int) -> str | None:
    if not isinstance(value, str):
        return None
    text = clean_text(clean_untrusted_text(value))
    return text[:limit] if text else None
