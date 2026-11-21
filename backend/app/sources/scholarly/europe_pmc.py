from __future__ import annotations

import re
from datetime import datetime
from typing import Any

from app.research.evidence import EvidenceItem, SearchQuery, SourceDocument

from ..adapter import HttpSourceAdapter, build_document
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

__all__ = ["EUROPE_PMC_LIMITS", "EuropePmcAdapter"]

EUROPE_PMC_API = "https://www.ebi.ac.uk/europepmc/webservices/rest"
EUROPE_PMC_LIMITS = ServiceLimits(search=SourceLimit(requests=5))
RECORD_ID = re.compile(r"^([A-Z]{3}):([A-Za-z0-9]+)$")
ARTICLE_TYPES = frozenset({"journal article", "research-article", "review-article", "review", "article"})


class EuropePmcAdapter(HttpSourceAdapter):
    name = "europe_pmc"

    async def _search_records(self, query: SearchQuery, k: int) -> list[Any]:
        return await self._records(query.text, page_size=k)

    def _item(self, record: Any, retrieved_at: datetime) -> EvidenceItem:
        source, record_id = clean_text(record.get("source")), clean_text(record.get("id"))
        if not source or not record_id or not RECORD_ID.match(f"{source}:{record_id}"):
            raise UnusableRecord("no Europe PMC source and id")
        doi = doi_of(record.get("doi"))
        source_type, trust = classify(_work_kind(record))
        journal = ((record.get("journalInfo") or {}).get("journal")) or {}
        return EvidenceItem(
            id=f"{self.name}:{source}:{record_id}",
            adapter=self.name,
            tier=self.tier,
            source_type=source_type,
            url=doi_url(doi) if doi else f"https://europepmc.org/article/{source}/{record_id}",
            title=title_of(record.get("title")),
            authors=_authors(record),
            published=partial_date_of(record.get("firstPublicationDate") or record.get("pubYear")),
            retrieved_at=retrieved_at,
            licence=clean_text(record.get("license")),
            doi=doi,
            publisher=clean_text(journal.get("title")),
            trust=trust,
            external_ids={"europe_pmc": f"{source}:{record_id}"},
        )

    async def _fetch_document(self, native: str, retrieved_at: datetime) -> SourceDocument:
        match = RECORD_ID.match(native)
        if match is None:
            raise self._not_found(native, "no record with this id")
        records = await self._records(f"EXT_ID:{match.group(2)} AND SRC:{match.group(1)}", page_size=1)
        if not records:
            raise self._not_found(native, "no record")
        abstract = markup_text(records[0].get("abstractText"))
        if abstract is None:
            raise self._not_found(native, "no abstract")
        return build_document(self._item(records[0], retrieved_at), abstract, "ABSTRACT")

    async def _records(self, text: str, *, page_size: int) -> list[Any]:
        params = {"query": text, "format": "json", "pageSize": str(page_size), "resultType": "core"}
        response = await self.http.get(f"{EUROPE_PMC_API}/search", params=params)
        return list(((response.json(self.name).get("resultList")) or {}).get("result") or [])


def _work_kind(record: dict[str, Any]) -> str:
    types = {str(t).lower() for t in ((record.get("pubTypeList") or {}).get("pubType") or [])}
    if record.get("source") == "PPR" or "preprint" in types:
        return "preprint"
    if types & ARTICLE_TYPES:
        return "article"
    return "other"


def _authors(record: dict[str, Any]) -> list[str]:
    listed = ((record.get("authorList") or {}).get("author")) or []
    names = [clean_text(author.get("fullName")) for author in listed]
    if not listed:
        names = [clean_text(name) for name in (record.get("authorString") or "").rstrip(".").split(",")]
    return [name for name in names if name][:AUTHORS_MAX]
