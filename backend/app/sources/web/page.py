from __future__ import annotations

from datetime import datetime
from typing import Any
from urllib.parse import urlsplit, urlunsplit

from app.core.errors import ExternalFailure, InvalidInput
from app.research.evidence import EVIDENCE_ID_MAX_CHARS, EvidenceItem, SourceDocument
from app.research.fetcher import FetchedPage, Fetcher, FetchRequest
from app.research.front_page import FrontPage, front_page, producer_token
from app.research.images import without_tracking
from app.research.source_titles import usable_title
from app.research.web_trust import web_trust

from ..adapter import Clock, HttpSourceAdapter, build_document, utc_now
from ..http import SourceHttp
from ..records import UnusableRecord, clean_text, https_or_none, partial_date_of, title_of

__all__ = ["PDF_TYPE", "WebPageAdapter", "page_item", "readable_url", "stated_front"]

PDF_TYPE = "application/pdf"
PAPER_TYPE = "PAPER"
PAGE_SOURCE_TYPES = {"text/html": "WEB_PAGE", "text/plain": "WEB_PAGE", PDF_TYPE: "OTHER"}
PLAIN_HTTP = "http"
PLAIN_HTTP_PORT = 80


class WebPageAdapter(HttpSourceAdapter):
    tier = "T4"

    def __init__(self, http: SourceHttp, *, fetcher: Fetcher, clock: Clock = utc_now) -> None:
        super().__init__(http, clock=clock)
        self.fetcher = fetcher

    def _hit(
        self, *, url: Any, title: Any, published: Any, publisher: Any, retrieved_at: datetime
    ) -> EvidenceItem:
        page_url = readable_url(url)
        if page_url is None:
            raise UnusableRecord("not a URL that can be read over https")
        item_id = f"{self.name}:{page_url}"
        if len(item_id) > EVIDENCE_ID_MAX_CHARS:
            raise UnusableRecord(f"URL longer than an evidence id allows ({EVIDENCE_ID_MAX_CHARS})")
        return EvidenceItem(
            id=item_id,
            adapter=self.name,
            tier=self.tier,
            source_type="WEB_PAGE",
            url=page_url,
            title=title_of(title),
            published=partial_date_of(published),
            retrieved_at=retrieved_at,
            publisher=clean_text(publisher),
            trust=web_trust(page_url),
        )

    async def _fetch_document(self, native: str, retrieved_at: datetime) -> SourceDocument:
        url = https_or_none(native)
        if url is None:
            raise InvalidInput(f"{native!r} is not an https URL")
        page = await self.fetcher.fetch(FetchRequest(url=url))
        if not page.text.strip():
            raise ExternalFailure(
                f"{self.name} page {url} has no readable text", kind="not_found", service=self.name
            )
        item = page_item(self.name, url, page)
        return build_document(item, page.text, "FULL_TEXT", truncated=page.truncated)


def page_item(adapter: str, url: str, page: FetchedPage) -> EvidenceItem:
    metadata = page.metadata
    return EvidenceItem(
        id=f"{adapter}:{url}",
        adapter=adapter,
        tier="T4",
        url=page.final_url,
        retrieved_at=page.fetched_at,
        licence=metadata.licence,
        publisher=metadata.site_name,
        trust=web_trust(page.final_url),
        external_ids={"sha256": page.sha256},
        **_described(page),
    )


def stated_front(page: FetchedPage) -> FrontPage | None:
    return front_page(page.text) if page.content_type == PDF_TYPE else None


def _described(page: FetchedPage) -> dict[str, Any]:
    metadata = page.metadata
    described: dict[str, Any] = {
        "source_type": PAGE_SOURCE_TYPES[page.content_type],
        "title": metadata.title or page.final_url,
        "authors": metadata.authors,
        "published": metadata.published,
    }
    front = stated_front(page)
    if front is None:
        return described
    named = [author for author in metadata.authors if not producer_token(author)]
    described |= {
        "title": usable_title(metadata.title, front.title) or described["title"],
        "authors": named or list(front.authors),
        "published": front.published or metadata.published,
    }
    if front.journal is not None:
        described |= {"source_type": PAPER_TYPE, "container_title": front.journal}
    return described


def readable_url(value: Any) -> str | None:
    text = clean_text(value)
    if text is None:
        return None
    url = https_or_none(text) or https_or_none(_https_upgraded(text))
    return without_tracking(url) if url is not None else None


def _https_upgraded(url: str) -> str | None:
    try:
        parts = urlsplit(url)
        port = parts.port
    except ValueError:
        return None
    if parts.scheme.lower() != PLAIN_HTTP or port not in (None, PLAIN_HTTP_PORT) or "@" in parts.netloc:
        return None
    host = parts.netloc.rsplit(":", 1)[0] if port == PLAIN_HTTP_PORT else parts.netloc
    return urlunsplit(("https", host, parts.path or "/", parts.query, parts.fragment))
