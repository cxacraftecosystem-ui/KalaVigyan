from __future__ import annotations

from datetime import datetime
from typing import Any
from xml.etree.ElementTree import Element

import httpx

from app.core.errors import ExternalFailure
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
from .publishers import PublisherText
from .xml_text import PARAGRAPH_BREAK, body_with_abstract, first_named, paragraphs, text_of, xml_root

__all__ = [
    "SPRINGER_NATURE_DOI_PREFIXES",
    "SPRINGER_NATURE_LIMITS",
    "SPRINGER_NATURE_TDM_LICENCE",
    "SpringerNatureAdapter",
    "SpringerNatureFullText",
    "check_key",
    "springer_abstract",
]

SPRINGER_NATURE_API = "https://api.springernature.com/openaccess/json"
SPRINGER_NATURE_FULL_TEXT_API = "https://api.springernature.com/xmldata/jats"
SPRINGER_NATURE_DOI_PREFIXES: tuple[str, ...] = ("10.1007", "10.1038", "10.1186", "10.1057")
SPRINGER_NATURE_TDM_LICENCE = "https://www.springer.com/tdm"
XLINK_HREF = "{http://www.w3.org/1999/xlink}href"
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
            container_title=journal_of(record.get("publicationName")),
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


class SpringerNatureFullText:
    name = "springer_nature"
    doi_prefixes = SPRINGER_NATURE_DOI_PREFIXES

    def __init__(self, http: SourceHttp, *, api_key: str) -> None:
        if not api_key:
            raise ValueError("Springer Nature full text needs SPRINGER_NATURE_API_KEY")
        self.http = http
        self._secret = {"api_key": api_key}

    async def full_text(self, doi: str) -> PublisherText:
        response = await self.http.get(
            SPRINGER_NATURE_FULL_TEXT_API, params={"q": f"doi:{doi}", "p": "1"}, secret_params=self._secret
        )
        document = _first_record(xml_root(response.body, self.name))
        text = None if document is None else _jats_text(document)
        if document is None or text is None:
            raise ExternalFailure(
                f"springer_nature sent no full text for {doi} to this key",
                kind="not_found",
                service=self.name,
            )
        return PublisherText(text=text, licence=_jats_licence(document) or SPRINGER_NATURE_TDM_LICENCE)


async def check_key(client: httpx.AsyncClient, value: str) -> KeyVerdict:
    return await checked_get(client, SPRINGER_NATURE_API, params={"q": "dye", "p": "1", "api_key": value})


def springer_abstract(value: Any) -> str | None:
    if isinstance(value, dict):
        body = value.get("p")
        value = " ".join(str(part) for part in body) if isinstance(body, list) else body
    return markup_text(value)


def _authors(creators: list[Any]) -> list[str]:
    names = [clean_text(entry.get("creator")) for entry in creators if isinstance(entry, dict)]
    return [name for name in names if name][:AUTHORS_MAX]


def _first_record(root: Element) -> Element | None:
    records = first_named(root, "records")
    return None if records is None else next(iter(records), None)


def _jats_text(document: Element) -> str | None:
    abstract = PARAGRAPH_BREAK.join(paragraphs(first_named(document, "abstract"))) or None
    return body_with_abstract(abstract, paragraphs(first_named(document, "body")))


def _jats_licence(document: Element) -> str | None:
    licence = first_named(document, "license")
    if licence is None:
        return None
    return text_of(licence, "license_ref") or clean_text(licence.get(XLINK_HREF))
