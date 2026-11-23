from __future__ import annotations

import re
from datetime import datetime
from typing import Any
from urllib.parse import quote

from app.research.evidence import EvidenceItem, SearchQuery, SourceDocument

from ..adapter import HttpSourceAdapter, build_document
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
    query_terms,
    title_of,
)
from .pacing import ServiceLimits, SourceLimit

__all__ = ["DOAJ_LIMITS", "DoajAdapter"]

DOAJ_API = "https://doaj.org/api/v4"
DOAJ_LIMITS = ServiceLimits(search=SourceLimit(requests=2))
ARTICLE_ID = re.compile(r"^[0-9a-f]{32}$")


class DoajAdapter(HttpSourceAdapter):
    name = "doaj"

    async def _search_records(self, query: SearchQuery, k: int) -> list[Any]:
        terms = query_terms(query.text)
        if not terms:
            return []
        response = await self.http.get(
            f"{DOAJ_API}/search/articles/{quote(' '.join(terms), safe='')}",
            params={"page": "1", "pageSize": str(k)},
        )
        return list(response.json(self.name).get("results") or [])

    def _item(self, record: Any, retrieved_at: datetime) -> EvidenceItem:
        article_id = clean_text(record.get("id")) or ""
        if not ARTICLE_ID.match(article_id):
            raise UnusableRecord("no DOAJ article id")
        bibjson = record.get("bibjson") or {}
        journal = bibjson.get("journal") or {}
        doi = _doi(bibjson)
        source_type, trust = classify("article")
        return EvidenceItem(
            id=f"{self.name}:{article_id}",
            adapter=self.name,
            tier=self.tier,
            source_type=source_type,
            url=doi_url(doi) if doi else f"https://doaj.org/article/{article_id}",
            title=title_of(bibjson.get("title")),
            authors=[n for n in (clean_text(a.get("name")) for a in bibjson.get("author") or []) if n][
                :AUTHORS_MAX
            ],
            published=_published(bibjson),
            retrieved_at=retrieved_at,
            doi=doi,
            publisher=clean_text(journal.get("publisher")),
            container_title=journal_of(journal.get("title")),
            trust=trust,
            external_ids={"doaj": article_id},
        )

    async def _fetch_document(self, native: str, retrieved_at: datetime) -> SourceDocument:
        if not ARTICLE_ID.match(native):
            raise self._not_found(native, "no article with this id")
        record = (await self.http.get(f"{DOAJ_API}/articles/{native}")).json(self.name)
        abstract = markup_text((record.get("bibjson") or {}).get("abstract"))
        if abstract is None:
            raise self._not_found(native, "no abstract")
        return build_document(self._item(record, retrieved_at), abstract, "ABSTRACT")


def _doi(bibjson: dict[str, Any]) -> str | None:
    for identifier in bibjson.get("identifier") or []:
        if str(identifier.get("type") or "").lower() == "doi":
            return doi_of(identifier.get("id"))
    return None


def _published(bibjson: dict[str, Any]) -> str | None:
    year, month = clean_text(bibjson.get("year")), clean_text(bibjson.get("month"))
    if year is None:
        return None
    if month and month.isdigit():
        return partial_date_of(f"{year}-{int(month):02d}")
    return partial_date_of(year)
