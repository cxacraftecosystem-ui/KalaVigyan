from __future__ import annotations

from datetime import datetime
from typing import Any

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
    https_or_none,
    markup_text,
    partial_date_of,
    title_of,
)
from .pacing import ServiceLimits, SourceLimit

__all__ = ["SEMANTIC_SCHOLAR_LIMITS", "SemanticScholarAdapter"]

SEMANTIC_SCHOLAR_API = "https://api.semanticscholar.org/graph/v1"
SEMANTIC_SCHOLAR_LIMITS = ServiceLimits(search=SourceLimit(requests=1, concurrency=1))
PAPER_FIELDS = (
    "paperId,title,abstract,authors,year,publicationDate,externalIds,url,venue,publicationTypes,"
    "openAccessPdf,journal"
)
TYPE_KINDS = (
    ("Book", "book"),
    ("BookSection", "chapter"),
    ("Dataset", "dataset"),
    ("JournalArticle", "article"),
    ("Review", "article"),
    ("Conference", "article"),
    ("MetaAnalysis", "article"),
    ("CaseReport", "article"),
    ("ClinicalTrial", "article"),
    ("Study", "article"),
)


class SemanticScholarAdapter(HttpSourceAdapter):
    name = "semantic_scholar"

    def __init__(self, http: SourceHttp, *, api_key: str | None = None, clock: Clock = utc_now) -> None:
        super().__init__(http, clock=clock)
        self._secret = {"x-api-key": api_key} if api_key else {}

    async def _search_records(self, query: SearchQuery, k: int) -> list[Any]:
        params = {"query": query.text, "limit": str(k), "fields": PAPER_FIELDS}
        response = await self.http.get(
            f"{SEMANTIC_SCHOLAR_API}/paper/search", params=params, secret_headers=self._secret
        )
        return list(response.json(self.name).get("data") or [])

    def _item(self, record: Any, retrieved_at: datetime) -> EvidenceItem:
        paper_id = clean_text(record.get("paperId"))
        if paper_id is None:
            raise UnusableRecord("no paper id")
        external = record.get("externalIds") or {}
        doi = doi_of(external.get("DOI"))
        source_type, trust = classify(_work_kind(record))
        journal = record.get("journal") or {}
        return EvidenceItem(
            id=f"{self.name}:{paper_id}",
            adapter=self.name,
            tier=self.tier,
            source_type=source_type,
            url=doi_url(doi) if doi else https_or_none(record.get("url")) or _paper_url(paper_id),
            title=title_of(record.get("title")),
            authors=[n for n in (clean_text(a.get("name")) for a in record.get("authors") or []) if n][
                :AUTHORS_MAX
            ],
            published=partial_date_of(record.get("publicationDate") or record.get("year")),
            retrieved_at=retrieved_at,
            licence=clean_text((record.get("openAccessPdf") or {}).get("license")),
            doi=doi,
            publisher=clean_text(journal.get("name")) or clean_text(record.get("venue")),
            trust=trust,
            external_ids={"semantic_scholar": paper_id},
        )

    async def _fetch_document(self, native: str, retrieved_at: datetime) -> SourceDocument:
        response = await self.http.get(
            f"{SEMANTIC_SCHOLAR_API}/paper/{native}",
            params={"fields": PAPER_FIELDS},
            secret_headers=self._secret,
        )
        record = response.json(self.name)
        abstract = markup_text(record.get("abstract"))
        if abstract is None:
            raise self._not_found(native, "no abstract")
        return build_document(self._item(record, retrieved_at), abstract, "ABSTRACT")


def _work_kind(record: dict[str, Any]) -> str:
    types = set(record.get("publicationTypes") or [])
    for native, kind in TYPE_KINDS:
        if native in types:
            return kind
    if clean_text((record.get("journal") or {}).get("name")):
        return "article"
    if "ArXiv" in (record.get("externalIds") or {}):
        return "preprint"
    return "other"


def _paper_url(paper_id: str) -> str:
    return f"https://www.semanticscholar.org/paper/{paper_id}"
