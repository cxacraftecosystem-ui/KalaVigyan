from __future__ import annotations

import re
from datetime import datetime
from typing import Any
from xml.etree import ElementTree

from app.core.errors import ExternalFailure
from app.research.evidence import EvidenceItem, SearchQuery, SourceDocument

from ..adapter import HttpSourceAdapter, build_document
from ..http import SourceResponse
from ..records import (
    AUTHORS_MAX,
    UnusableRecord,
    classify,
    clean_text,
    doi_of,
    markup_text,
    partial_date_of,
    query_terms,
    title_of,
)
from .pacing import ServiceLimits, SourceLimit

__all__ = ["ARXIV_LIMITS", "ArxivAdapter", "arxiv_search_query"]

ARXIV_API = "https://export.arxiv.org/api/query"
ARXIV_LIMITS = ServiceLimits(search=SourceLimit(requests=1, seconds=3.0, concurrency=1))
ATOM = "{http://www.w3.org/2005/Atom}"
ARXIV = "{http://arxiv.org/schemas/atom}"
ARXIV_ID = re.compile(r"^(?:\d{4}\.\d{4,5}|[a-z-]+(?:\.[A-Z]{2})?/\d{7})(?:v\d+)?$")


class ArxivAdapter(HttpSourceAdapter):
    name = "arxiv"

    async def _search_records(self, query: SearchQuery, k: int) -> list[Any]:
        search_query = arxiv_search_query(query.text)
        if search_query is None:
            return []
        params = {"search_query": search_query, "max_results": str(k)}
        return self._entries(await self.http.get(ARXIV_API, params=params))

    def _item(self, record: Any, retrieved_at: datetime) -> EvidenceItem:
        arxiv_id = _arxiv_id(record.findtext(f"{ATOM}id"))
        source_type, trust = classify("preprint")
        return EvidenceItem(
            id=f"{self.name}:{arxiv_id}",
            adapter=self.name,
            tier=self.tier,
            source_type=source_type,
            url=f"https://arxiv.org/abs/{arxiv_id}",
            title=title_of(record.findtext(f"{ATOM}title")),
            authors=[
                name
                for name in (clean_text(a.findtext(f"{ATOM}name")) for a in record.findall(f"{ATOM}author"))
                if name
            ][:AUTHORS_MAX],
            published=partial_date_of(record.findtext(f"{ATOM}published")),
            retrieved_at=retrieved_at,
            doi=doi_of(record.findtext(f"{ARXIV}doi")),
            publisher="arXiv",
            trust=trust,
            external_ids={"arxiv": arxiv_id},
        )

    async def _fetch_document(self, native: str, retrieved_at: datetime) -> SourceDocument:
        if not ARXIV_ID.match(native):
            raise self._not_found(native, "no paper with this id")
        entries = self._entries(await self.http.get(ARXIV_API, params={"id_list": native}))
        if not entries:
            raise self._not_found(native, "no paper")
        abstract = markup_text(entries[0].findtext(f"{ATOM}summary"))
        if abstract is None:
            raise self._not_found(native, "no abstract")
        return build_document(self._item(entries[0], retrieved_at), abstract, "ABSTRACT")

    def _entries(self, response: SourceResponse) -> list[Any]:
        try:
            feed = ElementTree.fromstring(response.body)
        except ElementTree.ParseError:
            raise ExternalFailure("arxiv answered with a feed that is not XML", service=self.name) from None
        return [entry for entry in feed.findall(f"{ATOM}entry") if _is_paper(entry)]


def arxiv_search_query(text: str) -> str | None:
    terms = query_terms(text)
    if not terms:
        return None
    return " AND ".join(f"all:{term}" for term in terms)


def _is_paper(entry: Any) -> bool:
    return "/abs/" in (entry.findtext(f"{ATOM}id") or "")


def _arxiv_id(value: str | None) -> str:
    arxiv_id = (value or "").rsplit("/abs/", 1)[-1].strip()
    if not ARXIV_ID.match(arxiv_id):
        raise UnusableRecord("no arXiv id")
    return arxiv_id
