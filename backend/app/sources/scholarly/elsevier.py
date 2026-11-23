from __future__ import annotations

from datetime import datetime
from typing import Any
from urllib.parse import quote

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
    https_or_none,
    journal_of,
    markup_text,
    partial_date_of,
    query_terms,
    title_of,
)
from .pacing import ServiceLimits, SourceLimit
from .publishers import PublisherText
from .xml_text import body_with_abstract, first_named, paragraphs, text_of, xml_root

__all__ = [
    "ELSEVIER_DOI_PREFIXES",
    "ELSEVIER_LIMITS",
    "ELSEVIER_TDM_LICENCE",
    "ElsevierAdapter",
    "ElsevierFullText",
    "check_key",
]

ELSEVIER_API = "https://api.elsevier.com/content"
ELSEVIER_LIMITS = ServiceLimits(search=SourceLimit(requests=5))
SUBTYPE_KINDS = {
    "ar": "article",
    "re": "article",
    "cp": "article",
    "le": "article",
    "ch": "chapter",
    "bk": "book",
}
SCOPUS_PREFIX = "SCOPUS_ID:"
JSON_ACCEPT = {"Accept": "application/json"}
XML_ACCEPT = {"Accept": "text/xml"}
KEY_HEADER = "X-ELS-APIKey"
TOKEN_HEADER = "X-ELS-Insttoken"
FULL_VIEW = {"view": "FULL"}
ELSEVIER_DOI_PREFIXES: tuple[str, ...] = ("10.1016",)
ELSEVIER_TDM_LICENCE = "https://www.elsevier.com/tdm/userlicense/1.0/"
SCOPUS_RECORD = "https://www.scopus.com/record/display.uri?eid=2-s2.0-"


class ElsevierAdapter(HttpSourceAdapter):
    name = "elsevier"

    def __init__(
        self, http: SourceHttp, *, api_key: str, insttoken: str | None = None, clock: Clock = utc_now
    ) -> None:
        if not api_key:
            raise ValueError("The Elsevier adapter needs ELSEVIER_API_KEY")
        super().__init__(http, clock=clock)
        self._secret = {KEY_HEADER: api_key} | ({TOKEN_HEADER: insttoken} if insttoken else {})

    async def _search_records(self, query: SearchQuery, k: int) -> list[Any]:
        terms = query_terms(query.text)
        if not terms:
            return []
        response = await self.http.get(
            f"{ELSEVIER_API}/search/scopus",
            params={"query": f"TITLE-ABS-KEY({' '.join(terms)})", "count": str(k)},
            headers=JSON_ACCEPT,
            secret_headers=self._secret,
        )
        entries = (response.json(self.name).get("search-results") or {}).get("entry") or []
        return [entry for entry in entries if "error" not in entry]

    def _item(self, record: Any, retrieved_at: datetime) -> EvidenceItem:
        scopus_id = _scopus_id(record.get("dc:identifier"))
        doi = doi_of(record.get("prism:doi"))
        source_type, trust = classify(SUBTYPE_KINDS.get(record.get("subtype") or "", "other"))
        return EvidenceItem(
            id=f"{self.name}:{scopus_id}",
            adapter=self.name,
            tier=self.tier,
            source_type=source_type,
            url=doi_url(doi) if doi else _scopus_url(record) or f"{SCOPUS_RECORD}{scopus_id}",
            title=title_of(record.get("dc:title")),
            authors=_authors(record.get("dc:creator")),
            published=partial_date_of(record.get("prism:coverDate")),
            retrieved_at=retrieved_at,
            doi=doi,
            publisher=clean_text(record.get("dc:publisher"))
            or clean_text(record.get("prism:publicationName")),
            container_title=journal_of(record.get("prism:publicationName")),
            trust=trust,
            external_ids={"scopus": scopus_id},
        )

    async def _fetch_document(self, native: str, retrieved_at: datetime) -> SourceDocument:
        if not native.isdigit():
            raise self._not_found(native, "no record with this id")
        response = await self.http.get(
            _abstract_url(native), headers=JSON_ACCEPT, secret_headers=self._secret
        )
        coredata = (response.json(self.name).get("abstracts-retrieval-response") or {}).get("coredata") or {}
        abstract = markup_text(coredata.get("dc:description"))
        if abstract is None:
            raise self._not_found(native, "no abstract this key may read")
        return build_document(self._item(coredata, retrieved_at), abstract, "ABSTRACT")


class ElsevierFullText:
    name = "elsevier"
    doi_prefixes = ELSEVIER_DOI_PREFIXES

    def __init__(self, http: SourceHttp, *, api_key: str, insttoken: str) -> None:
        if not api_key or not insttoken:
            raise ValueError("Elsevier full text needs ELSEVIER_API_KEY and ELSEVIER_INSTTOKEN")
        self.http = http
        self._secret = {KEY_HEADER: api_key, TOKEN_HEADER: insttoken}

    async def full_text(self, doi: str) -> PublisherText:
        response = await self.http.get(
            f"{ELSEVIER_API}/article/doi/{quote(doi, safe='/')}",
            params=FULL_VIEW,
            headers=XML_ACCEPT,
            secret_headers=self._secret,
        )
        root = xml_root(response.body, self.name)
        coredata = first_named(root, "coredata")
        original = first_named(root, "originalText")
        body = paragraphs(None if original is None else first_named(original, "body"))
        text = body_with_abstract(text_of(coredata, "description"), body)
        if text is None:
            raise ExternalFailure(
                f"elsevier sent no full text for {doi} to this key and token",
                kind="not_found",
                service=self.name,
            )
        return PublisherText(
            text=text, licence=text_of(coredata, "openaccessUserLicense") or ELSEVIER_TDM_LICENCE
        )


async def check_key(client: httpx.AsyncClient, value: str) -> KeyVerdict:
    return await checked_get(
        client,
        f"{ELSEVIER_API}/search/scopus",
        headers={KEY_HEADER: value},
        params={"query": "mordant", "count": "1"},
    )


def _scopus_id(value: Any) -> str:
    text = clean_text(value) or ""
    scopus_id = text.removeprefix(SCOPUS_PREFIX)
    if not scopus_id.isdigit():
        raise UnusableRecord("no Scopus id")
    return scopus_id


def _abstract_url(scopus_id: str) -> str:
    return f"{ELSEVIER_API}/abstract/scopus_id/{scopus_id}"


def _scopus_url(record: dict[str, Any]) -> str | None:
    for link in record.get("link") or []:
        if link.get("@ref") == "scopus" or link.get("@rel") == "scopus":
            return https_or_none(link.get("@href"))
    return None


def _authors(creator: Any) -> list[str]:
    if isinstance(creator, dict):
        names = [clean_text(author.get("ce:indexed-name")) for author in creator.get("author") or []]
        return [name for name in names if name][:AUTHORS_MAX]
    name = clean_text(creator)
    return [name] if name else []
