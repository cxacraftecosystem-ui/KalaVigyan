from __future__ import annotations

import re
from typing import Literal, Self

from pydantic import Field, model_validator

from .base import ContractModel, PartialDate
from .chapter_keys import CHAPTER_KEYS
from .citations import Citation, SourceRef
from .craft_chapters import Borrowed
from .craft_page_context import DEPTH_BASES
from .craft_parts import SOURCE_GROUPS, PagePlate

__all__ = [
    "GI_SHOWN",
    "NATIVE_NAME_SOURCES",
    "CiteThis",
    "Kicker",
    "Masthead",
    "MastheadGi",
    "NativeName",
    "PageSource",
    "Provenance",
    "Reliability",
]

GI_SHOWN = ("REGISTERED", "APPLIED")
NATIVE_NAME_SOURCES = ("DOSSIER", "WIKIDATA")
DAY_PATTERN = r"^\d{4}-(0[1-9]|1[0-2])-(0[1-9]|[12]\d|3[01])$"
CITE_PATH_PATTERN = r"^/crafts/[a-z0-9-]+(/v[1-9]\d*)?$"
VERSION_SEGMENT = re.compile(r"v[1-9]\d*")


class Kicker(ContractModel):
    family: str | None = Field(min_length=1)
    kind: str | None = Field(min_length=1)


class NativeName(ContractModel):
    text: str = Field(min_length=1, max_length=200)
    lang: str = Field(min_length=2, max_length=20)
    script: str | None = Field(pattern=r"^[A-Z][a-z]{3}$")
    source_id: str = Field(min_length=1)
    source_kind: Literal[*NATIVE_NAME_SOURCES]
    reviewed: bool


class MastheadGi(ContractModel):
    status: Literal[*GI_SHOWN]
    on: PartialDate | None
    citations: list[Citation]

    @model_validator(mode="after")
    def _dated_only_as_cited(self) -> Self:
        if self.on is not None and not self.citations:
            raise ValueError("a GI date is shown only with the claims that state it")
        return self


class Reliability(ContractModel):
    a: int = Field(ge=0)
    b: int = Field(ge=0)
    c: int = Field(ge=0)
    d: int = Field(ge=0)


class Provenance(ContractModel):
    basis: Literal[*DEPTH_BASES]
    sources: int = Field(ge=0)
    reliability: Reliability
    curated_on: str | None = Field(pattern=DAY_PATTERN)
    updated_on: str | None = Field(pattern=DAY_PATTERN)

    @model_validator(mode="after")
    def _curated_with_its_day(self) -> Self:
        if (self.basis == "CURATED") != (self.curated_on is not None):
            raise ValueError("a curated masthead, and only a curated one, gives its curation day")
        return self


class Masthead(ContractModel):
    kicker: Kicker
    name: str = Field(min_length=1)
    native_name: NativeName | None
    gi: MastheadGi | None
    place: str | None = Field(min_length=1)
    provenance: Provenance
    picture: PagePlate | None
    palette: str = Field(min_length=1, max_length=40)


class CiteThis(ContractModel):
    url: str = Field(pattern=CITE_PATH_PATTERN)
    version: int | None = Field(ge=1)
    curated_on: str | None = Field(pattern=DAY_PATTERN)
    text: str = Field(min_length=1)
    bibtex: str = Field(min_length=1)

    @model_validator(mode="after")
    def _versioned_only_when_curated(self) -> Self:
        if (self.version is None) != (self.curated_on is None):
            raise ValueError("a citation gives its version and curation day together")
        if (self.version is None) == (VERSION_SEGMENT.fullmatch(self.url.rsplit("/", 1)[-1]) is not None):
            raise ValueError("a curated citation names its versioned address, an uncurated one its plain one")
        return self


class PageSource(SourceRef):
    group: Literal[*SOURCE_GROUPS]
    from_: Borrowed | None = Field(alias="from")
    supports: int = Field(ge=0)

    @model_validator(mode="after")
    def _borrowed_from_its_group(self) -> Self:
        borrowed = self.group in ("FAMILY", "KIN")
        if borrowed != (self.from_ is not None):
            raise ValueError(f"source {self.id} names the monograph it comes from exactly when borrowed")
        return self


CHAPTER_ANCHORS = CHAPTER_KEYS
