from __future__ import annotations

from typing import Literal

from pydantic import Field

from app.research.base import ContractModel
from app.research.vocabulary import TrustTier

__all__ = [
    "LOOKUP_SCHEMA_VERSION",
    "ArchivedSource",
    "CompoundLookup",
    "CompoundRecord",
    "EntityLookup",
    "EntityRecord",
    "FoundPicture",
    "FoundPictures",
    "FoundSources",
    "Hazards",
    "NearestMatch",
    "OpenCopy",
    "Passage",
    "PictureWidth",
    "QuoteCheck",
    "SourceHit",
    "SourceText",
]

LOOKUP_SCHEMA_VERSION = 1


class OpenCopy(ContractModel):
    status: str
    url: str
    landing_url: str | None = None
    pdf_url: str | None = None
    licence: str | None = None
    open_licence: bool
    version: str | None = None


class SourceHit(ContractModel):
    title: str
    url: str
    doi: str | None = None
    kind: str
    found_by: list[str]
    published: str | None = None
    authors: list[str] = Field(default_factory=list)
    publisher: str | None = None
    grade: TrustTier
    held: bool
    licence: str | None = None
    open_licence: bool
    open_copy: OpenCopy | None = None
    excerpts: list[str] = Field(default_factory=list)


class FoundSources(ContractModel):
    schema_version: Literal[1] = LOOKUP_SCHEMA_VERSION
    query: str
    kinds: list[str]
    sources: list[SourceHit]
    searched: list[str]
    unavailable: list[str] = Field(default_factory=list)
    notices: list[str] = Field(default_factory=list)


class Passage(ContractModel):
    locator: str
    start: int = Field(ge=1)
    text: str
    cut: bool = False


class SourceText(ContractModel):
    schema_version: Literal[1] = LOOKUP_SCHEMA_VERSION
    url: str
    doi: str | None = None
    readable: bool
    unread: str | None = None
    title: str | None = None
    authors: list[str] = Field(default_factory=list)
    published: str | None = None
    publisher: str | None = None
    licence: str | None = None
    open_licence: bool
    grade: TrustTier | None = None
    held: bool
    restricted: bool = False
    truncated: bool = False
    archived_url: str | None = None
    lines: int = Field(default=0, ge=0)
    around: str | None = None
    found: int = Field(default=0, ge=0)
    passages: list[Passage] = Field(default_factory=list)
    next_start: int | None = None


class NearestMatch(ContractModel):
    locator: str
    text: str
    shared: float = Field(ge=0.0, le=1.0)


class QuoteCheck(ContractModel):
    schema_version: Literal[1] = LOOKUP_SCHEMA_VERSION
    url: str
    doi: str | None = None
    quote: str
    locator: str | None = None
    passed: bool
    reasons: list[str]
    found_at: list[str] = Field(default_factory=list)
    nearest: NearestMatch | None = None
    grade: TrustTier | None = None
    held: bool
    licence: str | None = None
    open_licence: bool


class Hazards(ContractModel):
    title: str
    url: str
    publisher: str | None = None
    licence: str | None = None
    open_licence: bool
    attribution: str | None = None
    lines: list[str]


class CompoundRecord(ContractModel):
    cid: int
    title: str
    formula: str | None = None
    molecular_weight: str | None = None
    iupac_name: str | None = None
    inchikey: str | None = None
    smiles: str | None = None
    url: str
    licence: str
    grade: TrustTier
    held: bool
    held_name: str | None = None
    synonyms: list[str] = Field(default_factory=list)
    hazards: Hazards | None = None


class CompoundLookup(ContractModel):
    schema_version: Literal[1] = LOOKUP_SCHEMA_VERSION
    query: str
    compounds: list[CompoundRecord]
    notices: list[str] = Field(default_factory=list)


class EntityRecord(ContractModel):
    qid: str
    label: str
    url: str
    licence: str | None = None
    open_licence: bool
    grade: TrustTier
    taxon_name: str | None = None
    pubchem_cid: str | None = None
    lines: list[str]


class EntityLookup(ContractModel):
    schema_version: Literal[1] = LOOKUP_SCHEMA_VERSION
    query: str
    entities: list[EntityRecord]


class PictureWidth(ContractModel):
    width: int = Field(ge=1)
    url: str


class FoundPicture(ContractModel):
    provider: str
    page_url: str
    image_url: str
    original_url: str
    width: int | None = None
    height: int | None = None
    title: str
    description: str | None = None
    author: str
    site: str
    licence: str | None = None
    licence_url: str | None = None
    open_licence: bool
    credit: str
    widths: list[PictureWidth] = Field(default_factory=list)


class FoundPictures(ContractModel):
    schema_version: Literal[1] = LOOKUP_SCHEMA_VERSION
    query: str
    pictures: list[FoundPicture]
    searched: list[str]
    unavailable: list[str] = Field(default_factory=list)


class ArchivedSource(ContractModel):
    schema_version: Literal[1] = LOOKUP_SCHEMA_VERSION
    url: str
    archived_url: str
    message: str
