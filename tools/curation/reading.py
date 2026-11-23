from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime

from app.curation.vocabulary import ReadRoute
from app.fetcher.extract import HTML_TYPES, PDF_TYPE, PLAIN_TYPE, extract
from app.fetcher.pdf import pdf_text
from app.research.fetcher import FetchRefused
from app.research.quotes import normalise_quote_lines
from app.research.untrusted import clean_untrusted_text

from .polite import Fetched, FetchFailed, PoliteHttp
from .tables import with_table_rows
from .wayback import SNAPSHOT, latest_snapshot, latest_snapshot_query, raw_snapshot_url

__all__ = [
    "PDF_DECOMPRESSED_MAX_BYTES",
    "PDF_PAGES_MAX",
    "TEXT_MAX_CHARS",
    "ReadFailed",
    "SourceText",
    "content_type_of",
    "read_source",
    "source_text",
]

PDF_PAGES_MAX = 2000
TEXT_MAX_CHARS = 8_000_000
PDF_DECOMPRESSED_MAX_BYTES = 400 * 1024 * 1024
PDF_MAGIC = b"%PDF-"
HTML_TYPE = "text/html"


@dataclass(frozen=True)
class SourceText:
    url: str
    route: ReadRoute
    read_url: str
    final_url: str
    fetched_at: datetime
    content_type: str
    text: str
    truncated: bool

    @property
    def sha256(self) -> str:
        return hashlib.sha256(self.text.encode("utf-8")).hexdigest()

    @property
    def lines(self) -> list[str]:
        return self.text.split("\n") if self.text else []


class ReadFailed(Exception):
    def __init__(self, url: str, reasons: list[str]) -> None:
        super().__init__(f"{url}: {'; '.join(reasons)}")
        self.url = url
        self.reasons = reasons


def source_text(fetched: Fetched) -> tuple[str, str, bool]:
    content_type = content_type_of(fetched)
    if content_type == PDF_TYPE:
        raw, truncated, _ = pdf_text(
            fetched.final_url,
            fetched.body,
            max_pages=PDF_PAGES_MAX,
            max_decompressed=PDF_DECOMPRESSED_MAX_BYTES,
        )
    else:
        page = extract(
            fetched.final_url, content_type, fetched.body, fetched.charset, max_chars=TEXT_MAX_CHARS
        )
        raw, truncated = page.text, page.truncated
        if content_type == HTML_TYPE:
            raw, truncated = with_table_rows(fetched.body, raw, truncated, max_chars=TEXT_MAX_CHARS)
    return content_type, "\n".join(normalise_quote_lines(clean_untrusted_text(raw))), truncated


def content_type_of(fetched: Fetched) -> str:
    if fetched.media_type in HTML_TYPES:
        return HTML_TYPE
    if fetched.media_type in (PDF_TYPE, PLAIN_TYPE):
        return fetched.media_type
    if fetched.body.startswith(PDF_MAGIC):
        return PDF_TYPE
    if fetched.body.lstrip()[:1] == b"<":
        return HTML_TYPE
    raise FetchRefused(
        fetched.final_url, "CONTENT_TYPE", f"{fetched.media_type or 'no content type'} is not read"
    )


def read_source(http: PoliteHttp, url: str, *, archived_url: str | None = None) -> SourceText:
    if SNAPSHOT.match(url):
        return _read_or_fail(http, url, raw_snapshot_url(url), "ARCHIVE")
    reasons = []
    try:
        return _read(http, url, url, "LIVE")
    except (FetchFailed, FetchRefused) as error:
        reasons.append(f"live page: {_reason(error)}")
    try:
        snapshot = archived_url or _latest_snapshot(http, url)
        if snapshot is not None:
            return _read(http, url, raw_snapshot_url(snapshot), "ARCHIVE")
        reasons.append("archive: the Wayback Machine has no snapshot")
    except (FetchFailed, FetchRefused) as error:
        reasons.append(f"archive: {_reason(error)}")
    raise ReadFailed(url, reasons)


def _read(http: PoliteHttp, url: str, read_url: str, route: ReadRoute) -> SourceText:
    fetched = http.get(read_url)
    content_type, text, truncated = source_text(fetched)
    if not text:
        raise FetchRefused(fetched.final_url, "PARSE_FAILED", "no text was extracted")
    return SourceText(
        url=url,
        route=route,
        read_url=read_url,
        final_url=fetched.final_url,
        fetched_at=fetched.fetched_at,
        content_type=content_type,
        text=text,
        truncated=truncated,
    )


def _read_or_fail(http: PoliteHttp, url: str, read_url: str, route: ReadRoute) -> SourceText:
    try:
        return _read(http, url, read_url, route)
    except (FetchFailed, FetchRefused) as error:
        raise ReadFailed(url, [f"{route.lower()}: {_reason(error)}"]) from None


def _latest_snapshot(http: PoliteHttp, url: str) -> str | None:
    answer = http.get(latest_snapshot_query(url))
    try:
        return latest_snapshot(answer.body.decode("utf-8"))
    except UnicodeDecodeError, json.JSONDecodeError, ValueError, IndexError:
        raise FetchFailed(answer.url, "the Wayback Machine's index answer could not be read") from None


def _reason(error: FetchFailed | FetchRefused) -> str:
    return error.reason if isinstance(error, FetchFailed) else error.message
