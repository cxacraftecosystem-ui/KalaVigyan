from __future__ import annotations

from datetime import datetime
from typing import Any
from urllib.parse import quote

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
    markup_text,
    partial_date_of,
    title_of,
)
from .pacing import ServiceLimits, SourceLimit

__all__ = ["CROSSREF_LIMITS", "CrossrefAdapter"]

CROSSREF_API = "https://api.crossref.org"
CROSSREF_LIMITS = ServiceLimits(
    search=SourceLimit(requests=3, concurrency=3),
    lookup=SourceLimit(requests=10, concurrency=3),
    search_path="/works",
)
WORK_FIELDS = "DOI,title,author,issued,type,publisher,abstract,license,container-title"
TYPE_KINDS = {
    "journal-article": "article",
    "proceedings-article": "article",
    "book": "book",
    "monograph": "book",
    "edited-book": "book",
    "reference-book": "book",
    "book-chapter": "chapter",
    "posted-content": "preprint",
    "dataset": "dataset",
    "dissertation": "thesis",
    "report": "report",
}


class CrossrefAdapter(HttpSourceAdapter):
    name = "crossref"

    def __init__(self, http: SourceHttp, *, contact_email: str, clock: Clock = utc_now) -> None:
        if not contact_email:
            raise ValueError("Crossref's polite pool needs RESEARCH_CONTACT_EMAIL")
        super().__init__(http, clock=clock)
        self._polite = {"mailto": contact_email}

    async def _search_records(self, query: SearchQuery, k: int) -> list[Any]:
        params = self._polite | {
            "query": query.text,
            "rows": str(k),
            "filter": "has-abstract:true",
            "select": WORK_FIELDS,
        }
        response = await self.http.get(f"{CROSSREF_API}/works", params=params)
        return list((response.json(self.name).get("message") or {}).get("items") or [])

    def _item(self, record: Any, retrieved_at: datetime) -> EvidenceItem:
        doi = doi_of(record.get("DOI"))
        if doi is None:
            raise UnusableRecord("no DOI")
        source_type, trust = classify(TYPE_KINDS.get(record.get("type") or "", "other"))
        licences = record.get("license") or [{}]
        return EvidenceItem(
            id=f"{self.name}:{doi}",
            adapter=self.name,
            tier=self.tier,
            source_type=source_type,
            url=doi_url(doi),
            title=title_of(record.get("title")),
            authors=_authors(record.get("author") or []),
            published=partial_date_of(((record.get("issued") or {}).get("date-parts") or [[]])[0]),
            retrieved_at=retrieved_at,
            licence=clean_text(licences[0].get("URL")),
            doi=doi,
            publisher=clean_text(record.get("publisher")),
            trust=trust,
            external_ids={"doi": doi},
        )

    async def _fetch_document(self, native: str, retrieved_at: datetime) -> SourceDocument:
        response = await self.http.get(f"{CROSSREF_API}/works/{quote(native, safe='/')}", params=self._polite)
        record = response.json(self.name).get("message") or {}
        abstract = markup_text(record.get("abstract"))
        if abstract is None:
            raise self._not_found(native, "no abstract")
        return build_document(self._item(record, retrieved_at), abstract, "ABSTRACT")


def _authors(authors: list[Any]) -> list[str]:
    names = [
        clean_text(author.get("name"))
        or clean_text(f"{author.get('given') or ''} {author.get('family') or ''}")
        for author in authors
    ]
    return [name for name in names if name][:AUTHORS_MAX]
