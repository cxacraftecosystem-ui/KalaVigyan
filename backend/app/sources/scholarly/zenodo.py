from __future__ import annotations

import re
from datetime import datetime
from typing import Any

from app.core.errors import ExternalFailure, InvalidInput
from app.research.evidence import EvidenceItem, OpenAccessLocation, SearchQuery, SourceDocument
from app.research.licences import open_licence

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
    query_terms,
    title_of,
)
from .pacing import ServiceLimits, SourceLimit

__all__ = ["ZENODO_LIMITS", "ZENODO_SEARCH_MAX", "ZenodoAdapter", "ZenodoLocator", "zenodo_doi_record"]

ZENODO_API = "https://zenodo.org/api/records"
ZENODO_RECORDS = "https://zenodo.org/records"
ZENODO_LIMITS = ServiceLimits(search=SourceLimit(requests=30, seconds=60.0))
ZENODO_SEARCH_MAX = 25
ZENODO_DOI = re.compile(r"^10\.5281/zenodo\.(\d+)$", re.IGNORECASE)
RECORD_ID = re.compile(r"^\d+$")
OPEN_ACCESS_RIGHT = "open"
READABLE_SUFFIX = ".pdf"
REDIRECT_STATUSES = frozenset({301, 302, 303, 307, 308})
PUBLICATION_KINDS = {
    "thesis": "thesis",
    "report": "report",
    "technicalnote": "report",
    "deliverable": "report",
}


class ZenodoAdapter(HttpSourceAdapter):
    name = "zenodo"

    async def _search_records(self, query: SearchQuery, k: int) -> list[Any]:
        terms = query_terms(query.text)
        if not terms:
            return []
        params = {"q": " ".join(terms), "size": str(min(k, ZENODO_SEARCH_MAX))}
        response = await self.http.get(ZENODO_API, params=params)
        return _hits(response.json(self.name))

    def _item(self, record: Any, retrieved_at: datetime) -> EvidenceItem:
        record_id = record.get("id")
        if not isinstance(record_id, int) or isinstance(record_id, bool):
            raise UnusableRecord("no Zenodo record id")
        metadata = record.get("metadata") or {}
        doi = doi_of(metadata.get("doi")) or doi_of(record.get("doi"))
        source_type, trust = classify(_work_kind(metadata.get("resource_type") or {}))
        return EvidenceItem(
            id=f"{self.name}:{record_id}",
            adapter=self.name,
            tier=self.tier,
            source_type=source_type,
            url=doi_url(doi) if doi else _record_page(record),
            title=title_of(metadata.get("title")),
            authors=_authors(metadata.get("creators") or []),
            published=partial_date_of(metadata.get("publication_date")),
            retrieved_at=retrieved_at,
            licence=_licence(metadata),
            doi=doi,
            publisher=clean_text((metadata.get("journal") or {}).get("title")) or "Zenodo",
            trust=trust,
            external_ids={"zenodo": str(record_id)},
        )

    async def _fetch_document(self, native: str, retrieved_at: datetime) -> SourceDocument:
        if not RECORD_ID.match(native):
            raise self._not_found(native, "no record with this id")
        record = (await self.http.get(f"{ZENODO_API}/{native}")).json(self.name)
        description = markup_text((record.get("metadata") or {}).get("description"))
        if description is None:
            raise self._not_found(native, "no description")
        return build_document(self._item(record, retrieved_at), description, "ABSTRACT")


class ZenodoLocator:
    name = "zenodo"

    def __init__(self, http: SourceHttp, *, clock: Clock = utc_now) -> None:
        self.http = http
        self.clock = clock

    async def locate(self, doi: str) -> OpenAccessLocation:
        record_id = zenodo_doi_record(doi)
        checked = doi_of(doi)
        if record_id is None or checked is None:
            raise InvalidInput(f"{doi!r} is not a DOI Zenodo minted")
        record = await self._record(record_id)
        metadata = record.get("metadata") or {}
        if metadata.get("access_right") != OPEN_ACCESS_RIGHT:
            return OpenAccessLocation(doi=checked, status="CLOSED", checked_at=self.clock())
        licence = _licence(metadata)
        pdf_url = _readable_file(record) if open_licence(licence) else None
        return OpenAccessLocation(
            doi=checked,
            status="GREEN",
            landing_url=_record_page(record) if pdf_url else None,
            pdf_url=pdf_url,
            licence=licence,
            host_type="REPOSITORY",
            checked_at=self.clock(),
        )

    async def _record(self, record_id: str) -> dict[str, Any]:
        try:
            return (await self.http.get(f"{ZENODO_API}/{record_id}")).json(self.name)
        except ExternalFailure as failure:
            if failure.status not in REDIRECT_STATUSES:
                raise
        response = await self.http.get(ZENODO_API, params={"q": f"conceptrecid:{record_id}", "size": "1"})
        found = _hits(response.json(self.name))
        if not found:
            raise ExternalFailure(
                f"zenodo has no record for {record_id}", kind="not_found", service=self.name
            )
        return found[0]


def zenodo_doi_record(doi: str) -> str | None:
    match = ZENODO_DOI.match(doi_of(doi) or "")
    return match.group(1) if match else None


def _hits(body: dict[str, Any]) -> list[Any]:
    return list((body.get("hits") or {}).get("hits") or [])


def _work_kind(resource_type: dict[str, Any]) -> str:
    kind = str(resource_type.get("type") or "").lower()
    if kind == "publication":
        return PUBLICATION_KINDS.get(str(resource_type.get("subtype") or "").lower(), "repository")
    return "dataset" if kind == "dataset" else "other"


def _licence(metadata: dict[str, Any]) -> str | None:
    licence = metadata.get("license")
    return clean_text(licence.get("id")) if isinstance(licence, dict) else clean_text(licence)


def _readable_file(record: dict[str, Any]) -> str | None:
    for entry in record.get("files") or []:
        key = clean_text(entry.get("key")) or ""
        url = https_or_none((entry.get("links") or {}).get("self"))
        if key.lower().endswith(READABLE_SUFFIX) and url:
            return url
    return None


def _record_page(record: dict[str, Any]) -> str:
    return (
        https_or_none((record.get("links") or {}).get("self_html")) or f"{ZENODO_RECORDS}/{record.get('id')}"
    )


def _authors(creators: list[Any]) -> list[str]:
    names = [clean_text(entry.get("name")) for entry in creators if isinstance(entry, dict)]
    return [name for name in names if name][:AUTHORS_MAX]
