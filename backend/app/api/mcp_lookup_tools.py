from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Literal, Self

from pydantic import BaseModel, Field, model_validator

from app.core.mcp_scopes import CONTRIBUTE_SCOPE, READ_SCOPE
from app.models.knowledge import QUOTE_MAX_CHARS
from app.research.base import HttpsUrl
from app.research.crafts import SLUG_MAX_CHARS
from app.research.evidence import DOI_PATTERN, SEARCH_QUERY_MAX_CHARS
from app.research.knowledge_writes import LOCATOR_MAX_CHARS, ProposedQuote
from app.services.source_lookup_calls import (
    LookupAsk,
    LookupDeps,
    archive_call,
    check_call,
    compound_call,
    entity_call,
    pictures_call,
    read_call,
    search_call,
)
from app.services.source_lookup_models import (
    ArchivedSource,
    CompoundLookup,
    EntityLookup,
    FoundPictures,
    FoundSources,
    QuoteCheck,
    SourceText,
)
from app.services.source_lookup_read import TextView

from .mcp_tool_base import Arguments, Tool, ToolContext

__all__ = ["LOOKUP_TOOLS", "LOOKUP_TOOL_NAMES", "lookup_tools"]

SEARCH_SOURCES, READ_SOURCE, CHECK_QUOTE = "search_sources", "read_source", "check_quote"
LOOKUP_COMPOUND, LOOKUP_ENTITY, FIND_PICTURES, ARCHIVE_SOURCE = (
    "lookup_compound",
    "lookup_entity",
    "find_pictures",
    "archive_source",
)
LOOKUP_TOOL_NAMES = (
    SEARCH_SOURCES,
    READ_SOURCE,
    CHECK_QUOTE,
    LOOKUP_COMPOUND,
    LOOKUP_ENTITY,
    FIND_PICTURES,
    ARCHIVE_SOURCE,
)
LOOKS = MappingProxyType({"readOnlyHint": True, "destructiveHint": False, "openWorldHint": True})
SAVES = MappingProxyType({"readOnlyHint": False, "destructiveHint": False, "openWorldHint": True})
QID_PATTERN = r"^Q[1-9]\d{0,11}$"
NAME_MAX_CHARS = 200
AROUND_MAX_CHARS = 200
ONE_ADDRESS = "give the source's url or its doi, one of them"
ONE_COMPOUND = "give the compound's name or its PubChem cid, one of them"
ONE_ENTITY = "give the item's name or its Wikidata qid, one of them"
CONTRIBUTORS = "Needs a signed-in account of Researcher or above."
ALLOWANCE = "It counts against the account's {kind} an hour by trust tier, as the contributor skill lists."
SEARCH_DESCRIPTION = (
    "Search the sources KalaVigyan itself searches, through the same adapters, keys and politeness: the "
    "scholarly registries (OpenAlex, Semantic Scholar, Crossref, Europe PMC, DOAJ, CORE, arXiv, Springer "
    "Nature, Elsevier), the reference works (Wikipedia, Wikidata) and web search. Each result carries the "
    "grade the source rubric gives it (the held grade when KalaVigyan already holds the source), its "
    "licence and whether that licence is open, an open-access copy where Unpaywall knows one, and its DOI "
    "or address. Paid routes (Brave, Elsevier) run only within the account's paid searches. Read a result "
    f"with read_source before quoting it. {CONTRIBUTORS} {ALLOWANCE.format(kind='source searches')}"
)
READ_DESCRIPTION = (
    "Read a source through KalaVigyan's own fetcher, exactly as the QUOTES gate will read it when you "
    "propose: the text in the gate's normalisation, a page at a time from start, or every passage around "
    "the words you give, each with its locator. It also gives the licence the page states, the grade the "
    "gates will record, whether KalaVigyan holds the source and an archived copy where one exists. A doi is "
    "read from its open-access copy when Unpaywall knows one; the url returned is the address to cite. "
    f"Copy quotes from these passages. {CONTRIBUTORS} {ALLOWANCE.format(kind='source reads')}"
)
CHECK_DESCRIPTION = (
    "Run the QUOTES gate's matcher on one quote without proposing anything: the source is fetched as the "
    "gate fetches it and the quote looked for as the gate looks for it. It answers passed or failed with the "
    "gate's reasons, where the quote stands, and when it fails the nearest passage and the share of the "
    f"quote's words it holds. Check every quote before you propose it. {CONTRIBUTORS} "
    f"{ALLOWANCE.format(kind='source reads')}"
)
COMPOUND_DESCRIPTION = (
    "Look up a compound in PubChem as KalaVigyan's science engine does: its record (CID, formula, "
    "molecular weight, IUPAC name, InChIKey, SMILES), its GHS hazards as PubChem's attributed sources "
    "report them, and, when KalaVigyan holds the compound, its stored name and synonyms. Open to anyone; "
    "signed in, it counts against the account's source reads."
)
ENTITY_DESCRIPTION = (
    "Look up Wikidata items for a place, a plant or a craft: each item's label, statements (a plant's "
    "taxon name among them, a place's coordinates and administrative area), its CC0 licence and its "
    "grade. Give a name for up to three items, or a qid for one. Open to anyone; signed in, it counts "
    "against the account's source reads."
)
PICTURES_DESCRIPTION = (
    "Find pictures on Wikimedia Commons and Openverse whose licence KalaVigyan accepts (CC0, public domain, "
    "PDDL, CC BY, CC BY-SA), each with its author, licence, credit line, size and, for a Commons file, the "
    "thumbnail addresses at the widths the site draws. These are pictures from elsewhere: KalaVigyan's team "
    "places them, credited to their authors; never give one with give_image. Open to anyone; signed in, it "
    "counts against the account's source searches."
)
ARCHIVE_DESCRIPTION = (
    "Ask the Wayback Machine to save a page and return the snapshot's address "
    "(https://web.archive.org/web/<timestamp>/<url>), to cite beside a live page that blocks automated "
    "reading or may change. It can take up to two minutes. "
    f"{CONTRIBUTORS} {ALLOWANCE.format(kind='source archives')}"
)

Run = Callable[[ToolContext, Any], Awaitable[BaseModel]]


class SearchSources(Arguments):
    query: str = Field(
        min_length=2,
        max_length=SEARCH_QUERY_MAX_CHARS,
        description="Words for what the source should state, such as indigo vat lime fermentation",
    )
    craft_slug: str | None = Field(
        default=None,
        min_length=1,
        max_length=SLUG_MAX_CHARS,
        description="A slug from find_crafts; the craft's name joins the query",
    )
    kinds: list[Literal["scholarly", "reference", "web"]] = Field(
        default_factory=lambda: ["scholarly", "reference", "web"],
        min_length=1,
        max_length=3,
        description="Which sources to search: scholarly, reference, web; all three when absent",
    )


class SourceAddress(Arguments):
    url: HttpsUrl | None = Field(default=None, description="The source's https address")
    doi: str | None = Field(
        default=None, pattern=DOI_PATTERN, max_length=255, description="The source's DOI, such as 10.1000/xyz"
    )

    @model_validator(mode="after")
    def _one_address(self) -> Self:
        if (self.url is None) == (self.doi is None):
            raise ValueError(ONE_ADDRESS)
        return self


class ReadSource(SourceAddress):
    around: str | None = Field(
        default=None,
        min_length=2,
        max_length=AROUND_MAX_CHARS,
        description="Words to find; every passage holding them is returned instead of a page",
    )
    start: int = Field(default=1, ge=1, description="The line or paragraph to start the page at; next_start")


class CheckQuote(SourceAddress):
    quote: str = Field(min_length=1, max_length=QUOTE_MAX_CHARS, description="The quote, verbatim")
    locator: str | None = Field(
        default=None, min_length=1, max_length=LOCATOR_MAX_CHARS, description="Where the quote stands"
    )


class LookupCompound(Arguments):
    name: str | None = Field(
        default=None, min_length=2, max_length=NAME_MAX_CHARS, description="A name, synonym or formula"
    )
    cid: int | None = Field(default=None, ge=1, description="A PubChem CID")

    @model_validator(mode="after")
    def _one_key(self) -> Self:
        if (self.name is None) == (self.cid is None):
            raise ValueError(ONE_COMPOUND)
        return self


class LookupEntity(Arguments):
    name: str | None = Field(
        default=None, min_length=2, max_length=NAME_MAX_CHARS, description="A place, plant or craft"
    )
    qid: str | None = Field(
        default=None, pattern=QID_PATTERN, description="A Wikidata item id, such as Q12345"
    )

    @model_validator(mode="after")
    def _one_key(self) -> Self:
        if (self.name is None) == (self.qid is None):
            raise ValueError(ONE_ENTITY)
        return self


class FindPictures(Arguments):
    query: str = Field(
        min_length=2,
        max_length=SEARCH_QUERY_MAX_CHARS,
        description="What the picture shows, such as resist printing",
    )
    craft_slug: str | None = Field(
        default=None, min_length=1, max_length=SLUG_MAX_CHARS, description="A slug from find_crafts"
    )


class ArchiveSource(Arguments):
    url: HttpsUrl = Field(description="The https address of the page to save")


@dataclass(frozen=True)
class _Entry:
    name: str
    title: str
    description: str
    arguments: type[Arguments]
    output: type[BaseModel]
    scope: str = CONTRIBUTE_SCOPE
    hints: Mapping[str, bool] = LOOKS


ENTRIES = (
    _Entry(SEARCH_SOURCES, "Search sources", SEARCH_DESCRIPTION, SearchSources, FoundSources),
    _Entry(READ_SOURCE, "Read a source", READ_DESCRIPTION, ReadSource, SourceText),
    _Entry(CHECK_QUOTE, "Check a quote", CHECK_DESCRIPTION, CheckQuote, QuoteCheck),
    _Entry(
        LOOKUP_COMPOUND,
        "Look up a compound",
        COMPOUND_DESCRIPTION,
        LookupCompound,
        CompoundLookup,
        READ_SCOPE,
    ),
    _Entry(
        LOOKUP_ENTITY,
        "Look up a place, plant or craft",
        ENTITY_DESCRIPTION,
        LookupEntity,
        EntityLookup,
        READ_SCOPE,
    ),
    _Entry(
        FIND_PICTURES, "Find open pictures", PICTURES_DESCRIPTION, FindPictures, FoundPictures, READ_SCOPE
    ),
    _Entry(ARCHIVE_SOURCE, "Archive a page", ARCHIVE_DESCRIPTION, ArchiveSource, ArchivedSource, hints=SAVES),
)


def lookup_tools(deps: LookupDeps) -> tuple[Tool, ...]:
    runs = {**_source_runs(deps), **_reference_runs(deps)}
    return tuple(
        Tool(
            entry.name,
            entry.title,
            entry.description,
            entry.arguments,
            entry.output,
            runs[entry.name],
            entry.scope,
            entry.hints,
        )
        for entry in ENTRIES
    )


def _asker(deps: LookupDeps) -> Callable[[ToolContext, str], LookupAsk]:
    def ask(context: ToolContext, tool: str) -> LookupAsk:
        return LookupAsk(session=context.session, user=context.user, tool=tool, deps=deps)

    return ask


def _source_runs(deps: LookupDeps) -> dict[str, Run]:
    ask = _asker(deps)

    async def search(context: ToolContext, arguments: SearchSources) -> FoundSources:
        asked = ask(context, SEARCH_SOURCES)
        return await search_call(asked, arguments.query, arguments.craft_slug, arguments.kinds)

    async def read(context: ToolContext, arguments: ReadSource) -> SourceText:
        view = TextView(around=arguments.around, start=arguments.start)
        return await read_call(ask(context, READ_SOURCE), arguments.url, arguments.doi, view)

    async def check(context: ToolContext, arguments: CheckQuote) -> QuoteCheck:
        quote = ProposedQuote(text=arguments.quote, locator=arguments.locator)
        return await check_call(ask(context, CHECK_QUOTE), arguments.url, arguments.doi, quote)

    async def archive(context: ToolContext, arguments: ArchiveSource) -> ArchivedSource:
        return await archive_call(ask(context, ARCHIVE_SOURCE), arguments.url)

    return {SEARCH_SOURCES: search, READ_SOURCE: read, CHECK_QUOTE: check, ARCHIVE_SOURCE: archive}


def _reference_runs(deps: LookupDeps) -> dict[str, Run]:
    ask = _asker(deps)

    async def compound(context: ToolContext, arguments: LookupCompound) -> CompoundLookup:
        return await compound_call(ask(context, LOOKUP_COMPOUND), arguments.name, arguments.cid)

    async def entity(context: ToolContext, arguments: LookupEntity) -> EntityLookup:
        return await entity_call(ask(context, LOOKUP_ENTITY), arguments.name, arguments.qid)

    async def pictures(context: ToolContext, arguments: FindPictures) -> FoundPictures:
        return await pictures_call(ask(context, FIND_PICTURES), arguments.query, arguments.craft_slug)

    return {LOOKUP_COMPOUND: compound, LOOKUP_ENTITY: entity, FIND_PICTURES: pictures}


LOOKUP_TOOLS = lookup_tools(LookupDeps())
