from __future__ import annotations

import re
import uuid
from collections.abc import Mapping, Sequence
from datetime import date, datetime
from types import MappingProxyType
from typing import Literal, Self

from pydantic import Field, field_validator, model_validator

from .base import ContractModel, HttpsUrl
from .evidence import DOI_PATTERN, EvidenceItem, canonical_url, shares_an_author
from .fetcher import FETCH_TEXT_MAX_CHARS
from .monograph_document import LANGUAGE_TAG
from .vocabulary import TrustTier

__all__ = [
    "ACCESS_KINDS",
    "AWAITING_FILE",
    "IDENTITY_KINDS",
    "PASSAGES_MAX",
    "PASSAGE_SEPARATOR",
    "READY",
    "SUPPLIED_SCHEMA_VERSION",
    "SUPPLIED_STATES",
    "SUPPLIED_TEXT_MAX_CHARS",
    "UPLOAD_KINDS",
    "CiteAs",
    "Confirmation",
    "SourceAccess",
    "SourceIdentity",
    "SuppliedPassage",
    "SuppliedProvenance",
    "SuppliedSourceReply",
    "SuppliedSourceView",
    "SuppliedUpload",
    "SupplySource",
    "cite_key",
    "cite_url",
    "isbn13",
    "matching_work",
    "normal_doi",
    "supplied_grade",
    "supplied_note",
    "supplied_text",
]

SUPPLIED_SCHEMA_VERSION = 1
SUPPLIED_TEXT_MAX_CHARS = FETCH_TEXT_MAX_CHARS
TEXT_MIN_CHARS = 200
PASSAGES_MAX = 60
PASSAGE_MIN_CHARS = 20
PASSAGE_MAX_CHARS = 8000
LOCATOR_MAX_CHARS = 200
TITLE_MAX_CHARS = 500
AUTHORS_MAX = 20
YEAR_MIN, YEAR_MAX = 1000, 2100
PASSAGE_SEPARATOR = "\n\n¶\n\n"
READY, AWAITING_FILE = SUPPLIED_STATES = ("READY", "AWAITING_FILE")
UPLOAD_KINDS = ("pdf", "text")
ACCESS_KINDS = ("SUBSCRIPTION", "INSTITUTION", "OWN_COPY", "ARCHIVE", "BLOCKED_SITE")
ACCESS_WORDS: Mapping[str, str] = MappingProxyType(
    {
        "SUBSCRIPTION": "read through the proposer's own subscription",
        "INSTITUTION": "read through an institution's library access",
        "OWN_COPY": "read in a copy the proposer holds",
        "ARCHIVE": "read in an archive or collection",
        "BLOCKED_SITE": "read on a site that refuses KalaVigyan's fetcher",
    }
)
IDENTITY_KINDS = (
    "PAPER",
    "BOOK",
    "BOOK_CHAPTER",
    "WEB_PAGE",
    "ENCYCLOPEDIA",
    "DATASET",
    "GI_JOURNAL",
    "GOVERNMENT_REPORT",
    "OTHER",
)
DOI_PREFIXES = ("https://doi.org/", "http://doi.org/", "https://dx.doi.org/", "doi:")
DOI_HOSTS = ("https://doi.org/", "https://dx.doi.org/")
ISBN_URL = "https://openlibrary.org/isbn/{isbn}"
DOI_URL = "https://doi.org/{doi}"
WORD = re.compile(r"[^\W_]+")
TITLE_PREFIX_WORDS = 4
YEAR_SLACK = 1
UNNAMED_CEILING = "C"
UNCONFIRMED = (
    "not found in Crossref, OpenAlex or Semantic Scholar, so it is graded as the work it says it is: {why}"
)

AccessKind = Literal[*ACCESS_KINDS]
IdentityKind = Literal[*IDENTITY_KINDS]


def normal_doi(value: str) -> str:
    text = value.strip()
    for prefix in DOI_PREFIXES:
        if text.lower().startswith(prefix):
            text = text[len(prefix) :]
            break
    if not re.fullmatch(DOI_PATTERN, text):
        raise ValueError("a DOI starts 10. and names its registrant and item, such as 10.1000/xyz123")
    return text.lower()


def isbn13(value: str) -> str:
    digits = re.sub(r"[\s-]", "", value).upper()
    if re.fullmatch(r"\d{9}[\dX]", digits):
        if sum((10 - n) * (10 if c == "X" else int(c)) for n, c in enumerate(digits)) % 11:
            raise ValueError("the ISBN-10's check digit does not match")
        digits = "978" + digits[:9]
        return digits + str((10 - sum((3 if n % 2 else 1) * int(c) for n, c in enumerate(digits)) % 10) % 10)
    if not re.fullmatch(r"97[89]\d{10}", digits):
        raise ValueError("an ISBN has 10 or 13 digits")
    if sum((3 if n % 2 else 1) * int(c) for n, c in enumerate(digits)) % 10:
        raise ValueError("the ISBN-13's check digit does not match")
    return digits


class SourceIdentity(ContractModel):
    doi: str | None = Field(default=None, max_length=255)
    isbn: str | None = Field(default=None, max_length=20)
    url: HttpsUrl | None = None
    title: str = Field(min_length=3, max_length=TITLE_MAX_CHARS)
    authors: list[str] = Field(default_factory=list, max_length=AUTHORS_MAX)
    year: int | None = Field(default=None, ge=YEAR_MIN, le=YEAR_MAX)
    publisher: str | None = Field(default=None, min_length=2, max_length=300)
    kind: IdentityKind = "OTHER"
    language: str = Field(default="en", max_length=16, pattern=LANGUAGE_TAG)

    @field_validator("doi")
    @classmethod
    def _doi(cls, value: str | None) -> str | None:
        return None if value is None else normal_doi(value)

    @field_validator("isbn")
    @classmethod
    def _isbn(cls, value: str | None) -> str | None:
        return None if value is None else isbn13(value)

    @field_validator("authors")
    @classmethod
    def _named(cls, value: list[str]) -> list[str]:
        names = [" ".join(name.split()) for name in value]
        if any(not 2 <= len(name) <= 200 for name in names):
            raise ValueError("each author is named in 2 to 200 characters")
        return names

    @model_validator(mode="after")
    def _identified(self) -> Self:
        if self.doi is None and self.isbn is None and self.url is None:
            raise ValueError("a source is identified by its DOI, its ISBN or its address (url)")
        return self


class SourceAccess(ContractModel):
    how: AccessKind
    accessed_on: date
    note: str | None = Field(default=None, min_length=2, max_length=300)


class SuppliedPassage(ContractModel):
    text: str = Field(min_length=PASSAGE_MIN_CHARS, max_length=PASSAGE_MAX_CHARS)
    locator: str = Field(min_length=1, max_length=LOCATOR_MAX_CHARS)


class SupplySource(ContractModel):
    schema_version: Literal[1] = SUPPLIED_SCHEMA_VERSION
    identity: SourceIdentity
    access: SourceAccess
    licence: str | None = Field(default=None, min_length=2, max_length=200)
    passages: list[SuppliedPassage] = Field(default_factory=list, max_length=PASSAGES_MAX)
    text: str | None = Field(default=None, min_length=TEXT_MIN_CHARS, max_length=SUPPLIED_TEXT_MAX_CHARS)
    upload: Literal[*UPLOAD_KINDS] | None = None

    @model_validator(mode="after")
    def _one_way_in(self) -> Self:
        given = [bool(self.passages), self.text is not None, self.upload is not None]
        if sum(given) != 1:
            raise ValueError(
                "give the source's words one way: passages, the whole text, or upload pdf or text"
            )
        texts = [passage.text for passage in self.passages]
        if len(set(texts)) != len(texts):
            raise ValueError("each passage is given once")
        if len(supplied_text(self.passages)) > SUPPLIED_TEXT_MAX_CHARS:
            raise ValueError(f"the passages hold at most {SUPPLIED_TEXT_MAX_CHARS} characters together")
        return self


class Confirmation(ContractModel):
    index: str
    work_id: str
    title: str
    doi: str | None
    year: int | None
    authors: list[str]


class CiteAs(ContractModel):
    url: str
    title: str
    licence: str | None


class SuppliedUpload(ContractModel):
    upload_url: str
    upload_method: Literal["PUT"] = "PUT"
    upload_types: list[str]
    upload_max_bytes: int
    expires_at: datetime


class SuppliedSourceReply(ContractModel):
    schema_version: Literal[1] = SUPPLIED_SCHEMA_VERSION
    supplied_source_id: uuid.UUID
    state: Literal[*SUPPLIED_STATES]
    cite_as: CiteAs
    grade: TrustTier
    grade_reason: str
    confirmed: Confirmation | None
    characters: int = Field(ge=0)
    passages: int = Field(ge=0)
    text_sha256: str | None
    upload: SuppliedUpload | None = None
    message: str
    next_step: str


class SuppliedProvenance(ContractModel):
    supplied_source_id: uuid.UUID
    access: AccessKind
    accessed_on: date
    grade: TrustTier
    confirmed_by: str | None
    text_sha256: str
    characters: int = Field(ge=0)


class SuppliedSourceView(ContractModel):
    schema_version: Literal[1] = SUPPLIED_SCHEMA_VERSION
    id: uuid.UUID
    state: Literal[*SUPPLIED_STATES]
    cite_url: str
    identity: SourceIdentity
    access: SourceAccess
    licence: str | None
    grade: TrustTier
    grade_reason: str
    confirmed: Confirmation | None
    characters: int
    text_sha256: str | None
    passages: list[SuppliedPassage]
    text: str | None
    created_at: datetime


def supplied_text(passages: Sequence[SuppliedPassage]) -> str:
    return PASSAGE_SEPARATOR.join(passage.text for passage in passages)


def cite_key(url: str) -> str:
    canonical = canonical_url(url)
    for host in DOI_HOSTS:
        if canonical.lower().startswith(host):
            return DOI_URL.format(doi=canonical[len(host) :].lower())
    return canonical


def cite_url(identity: SourceIdentity, confirmed_doi: str | None = None) -> str:
    doi = identity.doi or confirmed_doi
    if doi is not None:
        return DOI_URL.format(doi=doi.lower())
    if identity.url is not None:
        return cite_key(identity.url)
    return ISBN_URL.format(isbn=identity.isbn)


def supplied_grade(identity: SourceIdentity, confirmed: EvidenceItem | None) -> tuple[str, str]:
    named = bool(identity.authors) or bool(confirmed and confirmed.authors)
    if confirmed is not None:
        grade = UNNAMED_CEILING if not named and confirmed.trust == "B" else confirmed.trust
        return grade, f"found in {confirmed.adapter} as {confirmed.source_type.lower()}, graded {grade}"
    if named:
        return "C", UNCONFIRMED.format(why="a work with a named author read by the proposer is graded C")
    if identity.publisher is not None:
        return "C", UNCONFIRMED.format(why="a named organisation's own publication is graded C")
    return "D", UNCONFIRMED.format(why="a work with no named author or publisher is graded D")


def supplied_note(supplied_id: uuid.UUID, access: SourceAccess) -> str:
    return (
        f"text supplied by the proposer, {ACCESS_WORDS[access.how]} on {access.accessed_on.isoformat()}, "
        f"is held privately for reviewers as supplied source {supplied_id}"
    )


def matching_work(identity: SourceIdentity, found: Sequence[EvidenceItem]) -> EvidenceItem | None:
    if identity.doi is not None:
        return next((item for item in found if (item.doi or "").lower() == identity.doi), None)
    return next((item for item in found if _same_work(identity, item)), None)


def _same_work(identity: SourceIdentity, item: EvidenceItem) -> bool:
    return (
        _same_title(identity.title, item.title)
        and _same_year(identity, item)
        and _same_author(identity, item)
    )


def _same_title(declared: str, indexed: str) -> bool:
    mine, theirs = _words(declared), _words(indexed)
    if mine == theirs:
        return True
    shorter, longer = sorted((mine, theirs), key=len)
    return len(shorter) >= TITLE_PREFIX_WORDS and longer[: len(shorter)] == shorter


def _same_year(identity: SourceIdentity, item: EvidenceItem) -> bool:
    if identity.year is None or not item.published:
        return True
    return abs(int(item.published[:4]) - identity.year) <= YEAR_SLACK


def _same_author(identity: SourceIdentity, item: EvidenceItem) -> bool:
    if not identity.authors or not item.authors:
        return True
    return shares_an_author(identity.authors, item.authors)


def _words(text: str) -> tuple[str, ...]:
    return tuple(word.casefold() for word in WORD.findall(text))
