from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any, Literal, Self

from pydantic import Field, model_validator

from app.core.mcp_scopes import CONTRIBUTE_SCOPE, READ_SCOPE
from app.research.base import ContractModel, HttpsUrl
from app.research.crafts import SLUG_MAX_CHARS
from app.research.evidence import DOI_PATTERN, SEARCH_QUERY_MAX_CHARS
from app.research.knowledge_writes import PROPOSAL_QUOTES_MAX, ProposedQuote
from app.services.lookup_subjects import HeldSubject
from app.services.source_lookup_models import (
    ArchivedSource,
    CompoundRecord,
    EntityRecord,
    FoundPicture,
    QuoteCheck,
    SourceHit,
    SourceText,
)

from .mcp_tool_base import Arguments

__all__ = [
    "COMPOUND",
    "ENTITY",
    "PICTURES",
    "SEARCH_KINDS",
    "TEXT_KINDS",
    "Lookup",
    "LookupReply",
    "ReadSource",
    "SearchSources",
    "SourceReading",
    "SourceSearch",
    "search_scope",
]

TEXT_KINDS = ("scholarly", "reference", "web")
PICTURES = "pictures"
SEARCH_KINDS = (*TEXT_KINDS, PICTURES)
COMPOUND, ENTITY = LOOKUP_KINDS = ("compound", "entity")
QID = re.compile(r"^Q[1-9]\d{0,11}$")
CID = re.compile(r"^[1-9]\d{0,11}$")
NAME_MAX_CHARS = 200
AROUND_MAX_CHARS = 200
ONE_ADDRESS = "give the source's url or its doi, one of them"
ARCHIVE_NEEDS_URL = "archive saves a page by its address: give its url"
ONE_KEY = {
    COMPOUND: "give the compound's name or its PubChem cid as id, one of them",
    ENTITY: "give the item's name or its Wikidata qid as id, one of them",
}
WRONG_ID = {
    COMPOUND: "a compound's id is its PubChem CID, a whole number such as 10215",
    ENTITY: "an entity's id is its Wikidata qid, such as Q12345",
}


class SearchSources(Arguments):
    query: str = Field(
        min_length=2,
        max_length=SEARCH_QUERY_MAX_CHARS,
        description="Words for what the source or picture should state or show, such as indigo vat lime",
    )
    craft_slug: str | None = Field(
        default=None,
        min_length=1,
        max_length=SLUG_MAX_CHARS,
        description="A slug from find_crafts; the craft's name joins the query",
    )
    kinds: list[Literal[*SEARCH_KINDS]] = Field(
        default_factory=lambda: list(TEXT_KINDS),
        min_length=1,
        max_length=len(SEARCH_KINDS),
        description="Any of scholarly, reference, web and pictures; the first three when absent",
    )


def search_scope(arguments: Mapping[str, Any]) -> str:
    kinds = arguments.get("kinds")
    if isinstance(kinds, list) and kinds and all(kind == PICTURES for kind in kinds):
        return READ_SCOPE
    return CONTRIBUTE_SCOPE


class ReadSource(Arguments):
    url: HttpsUrl | None = Field(default=None, description="The source's https address")
    doi: str | None = Field(
        default=None, pattern=DOI_PATTERN, max_length=255, description="The source's DOI, such as 10.1000/xyz"
    )
    around: str | None = Field(
        default=None,
        min_length=2,
        max_length=AROUND_MAX_CHARS,
        description="Words to find; every passage holding them is returned instead of a page",
    )
    start: int | None = Field(default=None, ge=1, description="The line or paragraph to start the page at")
    quotes: list[ProposedQuote] = Field(
        default_factory=list,
        max_length=PROPOSAL_QUOTES_MAX,
        description="Quotes to check as the QUOTES gate will, each {text (verbatim), locator}",
    )
    archive: bool = Field(default=False, description="Ask the Wayback Machine to save the page too")

    @model_validator(mode="after")
    def _one_address(self) -> Self:
        if (self.url is None) == (self.doi is None):
            raise ValueError(ONE_ADDRESS)
        if self.archive and self.url is None:
            raise ValueError(ARCHIVE_NEEDS_URL)
        return self

    def wants_text(self) -> bool:
        asked_for = self.around is not None or self.start is not None
        return asked_for or not (self.quotes or self.archive)


class Lookup(Arguments):
    kind: Literal[*LOOKUP_KINDS] = Field(description="compound (PubChem) or entity (Wikidata)")
    name: str | None = Field(
        default=None,
        min_length=2,
        max_length=NAME_MAX_CHARS,
        description="A compound's name, synonym or formula, or a place, plant or craft",
    )
    id: int | str | None = Field(default=None, description="A PubChem CID, or a Wikidata qid such as Q12345")

    @model_validator(mode="after")
    def _one_key(self) -> Self:
        if (self.name is None) == (self.id is None):
            raise ValueError(ONE_KEY[self.kind])
        if self.id is not None and not (QID if self.kind == ENTITY else CID).match(str(self.id)):
            raise ValueError(WRONG_ID[self.kind])
        return self

    def cid(self) -> int | None:
        return None if self.id is None else int(self.id)

    def qid(self) -> str | None:
        return None if self.id is None else str(self.id)


class SourceSearch(ContractModel):
    schema_version: Literal[1] = 1
    query: str
    kinds: list[str]
    sources: list[SourceHit] = Field(default_factory=list)
    pictures: list[FoundPicture] = Field(default_factory=list)
    searched: list[str] = Field(default_factory=list)
    unavailable: list[str] = Field(default_factory=list)
    notices: list[str] = Field(default_factory=list)


class SourceReading(ContractModel):
    schema_version: Literal[1] = 1
    text: SourceText | None = None
    quotes: list[QuoteCheck] = Field(default_factory=list)
    archive: ArchivedSource | None = None
    notices: list[str] = Field(default_factory=list)


class LookupReply(ContractModel):
    schema_version: Literal[1] = 1
    kind: str
    query: str
    compounds: list[CompoundRecord] = Field(default_factory=list)
    entities: list[EntityRecord] = Field(default_factory=list)
    subjects: list[HeldSubject] = Field(default_factory=list)
    notices: list[str] = Field(default_factory=list)
