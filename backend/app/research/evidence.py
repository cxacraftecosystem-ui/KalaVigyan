from __future__ import annotations

import hashlib
import re
from collections.abc import Callable
from typing import Literal, Protocol, Self, runtime_checkable
from urllib.parse import urlsplit, urlunsplit

from pydantic import AwareDatetime, Field, field_validator, model_validator

from app.models.knowledge import CONTAINER_TITLE_CHARS, QUOTE_MAX_CHARS

from .base import ContractModel, HttpsUrl, PartialDate
from .quotes import quote_occurs
from .vocabulary import FacetType, LiveTier, SourceType, TrustTier

__all__ = [
    "ADAPTER_NAME_PATTERN",
    "DOI_PATTERN",
    "EVIDENCE_ID_MAX_CHARS",
    "OPEN_ACCESS_STATUSES",
    "SEARCH_MAX_K",
    "SEARCH_QUERY_MAX_CHARS",
    "EvidenceItem",
    "OpenAccessLocation",
    "OpenAccessLocator",
    "Quote",
    "ReferenceLister",
    "SearchQuery",
    "SourceAdapter",
    "SourceDocument",
    "canonical_url",
    "personal_data_in",
    "without_personal_data",
]

SEARCH_MAX_K = 50
EVIDENCE_ID_MAX_CHARS = 500
SEARCH_QUERY_MAX_CHARS = 300
ADAPTER_NAME_PATTERN = r"^[a-z][a-z0-9_]{1,39}$"
DOI_PATTERN = r"^10\.\d{4,9}/\S+$"
OPEN_ACCESS_STATUSES = ("GOLD", "DIAMOND", "HYBRID", "BRONZE", "GREEN", "CLOSED")
PERSONAL_DATA = {
    "email address": re.compile(r"[^\s@]+@[^\s@]+\.[^\s@]+"),
    "spoken email address": re.compile(r"\b[\w.+-]+\s+at\s+[\w-]+(?:\s+dot\s+[a-z]{2,})+\b", re.IGNORECASE),
    "Aadhaar-like number": re.compile(r"(?<!\d)\d{4}[ -]?\d{4}[ -]?\d{4}(?!\d)"),
    "phone-like number": re.compile(r"(?<!\d)(?:\+?\d[ -]?){10,}(?!\d)"),
}
PERSONAL_DATA_PLACEHOLDERS = {
    "email address": "[email]",
    "spoken email address": "[email]",
    "Aadhaar-like number": "[number]",
    "phone-like number": "[number]",
}


class Quote(ContractModel):
    text: str = Field(min_length=1, max_length=QUOTE_MAX_CHARS)
    locator: str | None = Field(default=None, max_length=300)


class EvidenceItem(ContractModel):
    id: str = Field(min_length=3, max_length=EVIDENCE_ID_MAX_CHARS)
    adapter: str = Field(pattern=ADAPTER_NAME_PATTERN)
    tier: LiveTier
    source_type: SourceType
    url: HttpsUrl
    title: str = Field(min_length=1, max_length=1000)
    authors: list[str] = Field(default_factory=list)
    published: PartialDate | None = None
    retrieved_at: AwareDatetime
    licence: str | None = Field(default=None, max_length=200)
    attribution: str | None = None
    doi: str | None = Field(default=None, pattern=DOI_PATTERN, max_length=255)
    publisher: str | None = Field(default=None, max_length=300)
    container_title: str | None = Field(default=None, min_length=1, max_length=CONTAINER_TITLE_CHARS)
    trust: TrustTier
    quotes: list[Quote] = Field(default_factory=list)
    external_ids: dict[str, str] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _id_names_the_adapter(self) -> Self:
        if not self.id.startswith(f"{self.adapter}:") or self.id == f"{self.adapter}:":
            raise ValueError("an evidence id is '<adapter>:<id at the service>'")
        return self

    @property
    def source_key(self) -> str:
        if self.doi:
            return f"doi:{self.doi.lower()}"
        return f"url:{canonical_url(self.url)}"


class SearchQuery(ContractModel):
    text: str = Field(min_length=2, max_length=SEARCH_QUERY_MAX_CHARS)
    facet: FacetType | None = None
    language: str = Field(default="en", min_length=2, max_length=16)
    freshness_days: int | None = Field(default=None, ge=1)

    @field_validator("text")
    @classmethod
    def _no_personal_data(cls, value: str) -> str:
        found = personal_data_in(value)
        if found:
            raise ValueError(f"a search query never carries personal data ({', '.join(found)})")
        return value


class SourceDocument(ContractModel):
    item: EvidenceItem
    text: str = Field(min_length=1)
    text_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    truncated: bool
    content: Literal["FULL_TEXT", "ABSTRACT", "EXCERPT"]

    @model_validator(mode="after")
    def _text_backs_the_quotes(self) -> Self:
        if hashlib.sha256(self.text.encode("utf-8")).hexdigest() != self.text_sha256:
            raise ValueError("text_sha256 is the SHA-256 of text in UTF-8")
        missing = [q.text for q in self.item.quotes if not quote_occurs(q.text, self.text)]
        if missing:
            raise ValueError(f"{len(missing)} quote(s) do not occur in the document text")
        return self


class OpenAccessLocation(ContractModel):
    doi: str = Field(pattern=DOI_PATTERN, max_length=255)
    status: Literal[*OPEN_ACCESS_STATUSES]
    landing_url: HttpsUrl | None = None
    pdf_url: HttpsUrl | None = None
    licence: str | None = Field(default=None, max_length=200)
    version: str | None = Field(default=None, max_length=100)
    host_type: Literal["PUBLISHER", "REPOSITORY"] | None = None
    checked_at: AwareDatetime

    @property
    def is_open(self) -> bool:
        return self.status != "CLOSED"

    @model_validator(mode="after")
    def _closed_has_no_copy(self) -> Self:
        if not self.is_open and (self.landing_url or self.pdf_url or self.host_type):
            raise ValueError("a CLOSED work has no open-access copy")
        return self


def personal_data_in(text: str) -> list[str]:
    return [label for label, pattern in PERSONAL_DATA.items() if pattern.search(text)]


def without_personal_data(text: str) -> str:
    for label, pattern in PERSONAL_DATA.items():
        text = pattern.sub(_replacement(PERSONAL_DATA_PLACEHOLDERS[label]), text)
    return text


def _replacement(placeholder: str) -> Callable[[re.Match[str]], str]:
    def replace(found: re.Match[str]) -> str:
        return placeholder + (" " if found.group()[-1] in " -" else "")

    return replace


def canonical_url(url: str) -> str:
    parts = urlsplit(url)
    host = (parts.hostname or "").lower()
    port = f":{parts.port}" if parts.port and parts.port != 443 else ""
    path = parts.path.rstrip("/") or "/"
    return urlunsplit((parts.scheme.lower(), host + port, path, parts.query, ""))


@runtime_checkable
class SourceAdapter(Protocol):
    name: str
    tier: LiveTier

    async def search(self, query: SearchQuery, k: int) -> list[EvidenceItem]: ...

    async def fetch(self, item_id: str) -> SourceDocument: ...


@runtime_checkable
class OpenAccessLocator(Protocol):
    name: str

    async def locate(self, doi: str) -> OpenAccessLocation: ...


@runtime_checkable
class ReferenceLister(Protocol):
    name: str

    def lists(self, item: EvidenceItem) -> bool: ...

    async def references(self, item: EvidenceItem, k: int) -> list[SourceDocument]: ...
