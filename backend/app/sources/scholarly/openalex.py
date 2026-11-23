from __future__ import annotations

from datetime import datetime
from typing import Any

import httpx

from app.core.errors import ExternalFailure
from app.core.key_checks import KeyVerdict, checked_get
from app.research.evidence import EvidenceItem, SearchQuery, SourceDocument

from ..adapter import Clock, HttpSourceAdapter, build_document, checked_k, usable_records, utc_now
from ..http import SourceHttp
from ..records import (
    AUTHORS_MAX,
    UnusableRecord,
    classify,
    clean_text,
    doi_of,
    doi_url,
    journal_of,
    partial_date_of,
    title_of,
)
from .pacing import ServiceLimits, SourceLimit

__all__ = [
    "OPENALEX_KEYED_LIMITS",
    "OPENALEX_LIMITS",
    "REFERENCE_ORDER",
    "OpenAlexAdapter",
    "abstract_from_index",
    "check_key",
]

OPENALEX_API = "https://api.openalex.org"
OPENALEX_LIMITS = ServiceLimits(search=SourceLimit(requests=10))
OPENALEX_KEYED_LIMITS = ServiceLimits(search=SourceLimit(requests=30))
WORK_FIELDS = (
    "id,doi,display_name,publication_date,publication_year,type,authorships,primary_location,best_oa_location"
)
DOCUMENT_FIELDS = f"{WORK_FIELDS},abstract_inverted_index"
REFERENCE_ORDER = "cited_by_count:desc"
CONTAINER_SOURCE_TYPES = frozenset({"journal", "conference", "book series"})
TYPE_KINDS = {
    "article": "article",
    "review": "article",
    "letter": "article",
    "book": "book",
    "book-chapter": "chapter",
    "preprint": "preprint",
    "dataset": "dataset",
    "dissertation": "thesis",
    "report": "report",
}


class OpenAlexAdapter(HttpSourceAdapter):
    name = "openalex"

    def __init__(
        self, http: SourceHttp, *, contact_email: str, api_key: str | None = None, clock: Clock = utc_now
    ) -> None:
        super().__init__(http, clock=clock)
        self._params = {"mailto": contact_email}
        self._secret = {"api_key": api_key} if api_key else {}

    async def _search_records(self, query: SearchQuery, k: int) -> list[Any]:
        params = self._params | {"search": query.text, "per-page": str(k), "select": WORK_FIELDS}
        response = await self.http.get(f"{OPENALEX_API}/works", params=params, secret_params=self._secret)
        return list(response.json(self.name).get("results") or [])

    def _item(self, record: Any, retrieved_at: datetime) -> EvidenceItem:
        work_id = _work_id(record.get("id"))
        doi = doi_of(record.get("doi"))
        source_type, trust = classify(TYPE_KINDS.get(record.get("type") or "", "other"))
        primary = record.get("primary_location") or {}
        best = record.get("best_oa_location") or {}
        return EvidenceItem(
            id=f"{self.name}:{work_id}",
            adapter=self.name,
            tier=self.tier,
            source_type=source_type,
            url=doi_url(doi) if doi else f"https://openalex.org/{work_id}",
            title=title_of(record.get("display_name")),
            authors=_authors(record.get("authorships") or []),
            published=partial_date_of(record.get("publication_date") or record.get("publication_year")),
            retrieved_at=retrieved_at,
            licence=clean_text(best.get("license") or primary.get("license")),
            doi=doi,
            publisher=clean_text((primary.get("source") or {}).get("host_organization_name")),
            container_title=_container(primary.get("source") or {}),
            trust=trust,
            external_ids={"openalex": work_id},
        )

    def lists(self, item: EvidenceItem) -> bool:
        return bool(item.external_ids.get(self.name))

    async def references(self, item: EvidenceItem, k: int) -> list[SourceDocument]:
        work_id = item.external_ids.get(self.name)
        if not work_id:
            return []
        wanted = checked_k(k)
        params = self._params | {
            "filter": f"cited_by:{work_id},has_abstract:true",
            "sort": REFERENCE_ORDER,
            "per-page": str(wanted),
            "select": DOCUMENT_FIELDS,
        }
        response = await self.http.get(f"{OPENALEX_API}/works", params=params, secret_params=self._secret)
        records = list(response.json(self.name).get("results") or [])
        retrieved_at = self.clock()
        return usable_records(self.name, records, lambda record: self._listed(record, retrieved_at))[:wanted]

    def _listed(self, record: Any, retrieved_at: datetime) -> SourceDocument:
        abstract = abstract_from_index(record.get("abstract_inverted_index"))
        if abstract is None:
            raise UnusableRecord("no abstract")
        try:
            return build_document(self._item(record, retrieved_at), abstract, "ABSTRACT")
        except ExternalFailure as failure:
            raise UnusableRecord(str(failure)) from failure

    async def _fetch_document(self, native: str, retrieved_at: datetime) -> SourceDocument:
        params = self._params | {"select": DOCUMENT_FIELDS}
        response = await self.http.get(
            f"{OPENALEX_API}/works/{native}", params=params, secret_params=self._secret
        )
        record = response.json(self.name)
        abstract = abstract_from_index(record.get("abstract_inverted_index"))
        if abstract is None:
            raise self._not_found(native, "no abstract")
        return build_document(self._item(record, retrieved_at), abstract, "ABSTRACT")


async def check_key(client: httpx.AsyncClient, value: str) -> KeyVerdict:
    return await checked_get(client, f"{OPENALEX_API}/works", params={"per-page": "1", "api_key": value})


def abstract_from_index(index: Any) -> str | None:
    if not isinstance(index, dict) or not index:
        return None
    placed = sorted((position, word) for word, positions in index.items() for position in positions)
    return clean_text(" ".join(word for _position, word in placed))


def _container(source: dict[str, Any]) -> str | None:
    if source.get("type") not in CONTAINER_SOURCE_TYPES:
        return None
    return journal_of(source.get("display_name"))


def _work_id(value: Any) -> str:
    text = clean_text(value) or ""
    work_id = text.rsplit("/", 1)[-1]
    if not work_id.startswith("W"):
        raise UnusableRecord("no OpenAlex work id")
    return work_id


def _authors(authorships: list[Any]) -> list[str]:
    names = [clean_text((entry.get("author") or {}).get("display_name")) for entry in authorships]
    return [name for name in names if name][:AUTHORS_MAX]
