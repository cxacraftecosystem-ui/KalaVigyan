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
    markup_text,
    partial_date_of,
    title_of,
)
from .pacing import ServiceLimits, SourceLimit

__all__ = ["SPRINGER_NATURE_LIMITS", "SpringerNatureAdapter", "springer_abstract"]

SPRINGER_NATURE_API = "https://api.springernature.com/openaccess/json"
SPRINGER_NATURE_LIMITS = ServiceLimits(search=SourceLimit(requests=100, seconds=60.0))
CONTENT_KINDS = {"article": "article", "chapter": "chapter", "book": "book"}


class SpringerNatureAdapter(HttpSourceAdapter):
    name = "springer_nature"

    def __init__(self, http: SourceHttp, *, api_key: str, clock: Clock = utc_now) -> None:
        if not api_key:
            raise ValueError("The Springer Nature adapter needs SPRINGER_NATURE_API_KEY")
        super().__init__(http, clock=clock)
        self._secret = {"api_key": api_key}

    async def _search_records(self, query: SearchQuery, k: int) -> list[Any]:
        return await self._records(query.text, page_size=k)

    def _item(self, record: Any, retrieved_at: datetime) -> EvidenceItem:
        doi = doi_of(record.get("doi")) or doi_of(record.get("identifier"))
        if doi is None:
            raise UnusableRecord("no DOI")
        source_type, trust = classify(
            CONTENT_KINDS.get(str(record.get("contentType") or "").lower(), "other")
        )
        return EvidenceItem(
            id=f"{self.name}:{doi}",
            adapter=self.name,
            tier=self.tier,
            source_type=source_type,
            url=doi_url(doi),
            title=title_of(record.get("title")),
            authors=_authors(record.get("creators") or []),
            published=partial_date_of(record.get("publicationDate")),
            retrieved_at=retrieved_at,
            doi=doi,
            publisher=clean_text(record.get("publisher")),
            trust=trust,
            external_ids={"doi": doi},
        )

    async def _fetch_document(self, native: str, retrieved_at: datetime) -> SourceDocument:
        doi = doi_of(native)
        if doi is None:
            raise self._not_found(native, "no record with this id")
        records = await self._records(f"doi:{doi}", page_size=1)
        if not records:
            raise self._not_found(native, "no record")
        abstract = springer_abstract(records[0].get("abstract"))
        if abstract is None:
            raise self._not_found(native, "no abstract")
        return build_document(self._item(records[0], retrieved_at), abstract, "ABSTRACT")

    async def _records(self, text: str, *, page_size: int) -> list[Any]:
        response = await self.http.get(
            SPRINGER_NATURE_API, params={"q": text, "p": str(page_size)}, secret_params=self._secret
        )
        return list(response.json(self.name).get("records") or [])


def springer_abstract(value: Any) -> str | None:
    if isinstance(value, dict):
        body = value.get("p")
        value = " ".join(str(part) for part in body) if isinstance(body, list) else body
    return markup_text(value)


def _authors(creators: list[Any]) -> list[str]:
    names = [clean_text(entry.get("creator")) for entry in creators if isinstance(entry, dict)]
    return [name for name in names if name][:AUTHORS_MAX]
