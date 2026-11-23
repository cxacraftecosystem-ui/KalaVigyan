from __future__ import annotations

from datetime import datetime
from typing import Any

import httpx

from app.core.key_checks import KeyVerdict, checked_get
from app.research.evidence import EvidenceItem, SearchQuery, SourceDocument

from ..adapter import Clock, HttpSourceAdapter, build_document, utc_now
from ..http import SourceHttp
from ..records import (
    AUTHORS_MAX,
    UnusableRecord,
    classify,
    clean_text,
    doi_of,
    doi_url,
    journal_of,
    markup_text,
    partial_date_of,
    title_of,
)
from .pacing import ServiceLimits, SourceLimit

__all__ = ["CORE_LIMITS", "CoreAdapter", "check_key"]

CORE_API = "https://api.core.ac.uk/v3"
CORE_LIMITS = ServiceLimits(search=SourceLimit(requests=10, seconds=60.0))


class CoreAdapter(HttpSourceAdapter):
    name = "core"

    def __init__(self, http: SourceHttp, *, api_key: str, clock: Clock = utc_now) -> None:
        if not api_key:
            raise ValueError("The CORE adapter needs CORE_API_KEY")
        super().__init__(http, clock=clock)
        self._secret = {"Authorization": f"Bearer {api_key}"}

    async def _search_records(self, query: SearchQuery, k: int) -> list[Any]:
        response = await self.http.get(
            f"{CORE_API}/search/works/",
            params={"q": query.text, "limit": str(k)},
            secret_headers=self._secret,
        )
        return list(response.json(self.name).get("results") or [])

    def _item(self, record: Any, retrieved_at: datetime) -> EvidenceItem:
        work_id = record.get("id")
        if not isinstance(work_id, int) or isinstance(work_id, bool):
            raise UnusableRecord("no CORE work id")
        doi = doi_of(record.get("doi"))
        source_type, trust = classify("thesis" if record.get("documentType") == "thesis" else "repository")
        return EvidenceItem(
            id=f"{self.name}:{work_id}",
            adapter=self.name,
            tier=self.tier,
            source_type=source_type,
            url=doi_url(doi) if doi else f"https://core.ac.uk/works/{work_id}",
            title=title_of(record.get("title")),
            authors=[n for n in (clean_text(a.get("name")) for a in record.get("authors") or []) if n][
                :AUTHORS_MAX
            ],
            published=partial_date_of(record.get("publishedDate") or record.get("yearPublished")),
            retrieved_at=retrieved_at,
            doi=doi,
            publisher=clean_text(record.get("publisher")),
            container_title=journal_of(
                [j.get("title") for j in record.get("journals") or [] if isinstance(j, dict)]
            ),
            trust=trust,
            external_ids={"core": str(work_id)},
        )

    async def _fetch_document(self, native: str, retrieved_at: datetime) -> SourceDocument:
        if not native.isdigit():
            raise self._not_found(native, "no work with this id")
        response = await self.http.get(f"{CORE_API}/works/{native}", secret_headers=self._secret)
        record = response.json(self.name)
        item = self._item(record, retrieved_at)
        full_text = record.get("fullText")
        if isinstance(full_text, str) and full_text.strip():
            return build_document(item, full_text.strip(), "FULL_TEXT")
        abstract = markup_text(record.get("abstract"))
        if abstract is None:
            raise self._not_found(native, "no full text or abstract")
        return build_document(item, abstract, "ABSTRACT")


async def check_key(client: httpx.AsyncClient, value: str) -> KeyVerdict:
    return await checked_get(
        client,
        f"{CORE_API}/search/works",
        headers={"Authorization": f"Bearer {value}"},
        params={"q": "mordant", "limit": "1"},
    )
