from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

from app.core.errors import InvalidInput
from app.core.mcp_scopes import CONTRIBUTE_SCOPE, READ_SCOPE
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
    FoundPictures,
    FoundSources,
    QuoteCheck,
    SourceText,
)
from app.services.source_lookup_read import TextView

from .mcp_lookup_arguments import (
    COMPOUND,
    PICTURES,
    Lookup,
    LookupReply,
    ReadSource,
    SearchSources,
    SourceReading,
    SourceSearch,
    search_scope,
)
from .mcp_tool_base import LOOKS, SOURCES, Tool, ToolContext

__all__ = ["LOOKUP_TOOLS", "LOOKUP_TOOL_NAMES", "lookup_tools"]

SEARCH_SOURCES, READ_SOURCE, LOOKUP = LOOKUP_TOOL_NAMES = ("search_sources", "read_source", "lookup")
SEARCH_DESCRIPTION = (
    "Search the sources KalaVigyan itself searches, through the same adapters, keys and politeness: the "
    "scholarly registries (OpenAlex, Semantic Scholar, Crossref, Europe PMC, DOAJ, CORE, arXiv, Springer "
    "Nature, Elsevier), the reference works (Wikipedia, Wikidata), web search and, as kind pictures, "
    "Wikimedia Commons and Openverse. Each source carries the grade the source rubric gives it (the held grade "
    "when KalaVigyan holds it), its licence and whether it is open, an open-access copy where Unpaywall knows "
    "one, and its DOI or address; paid routes (Brave, Elsevier) run only within the account's paid searches. "
    "Each picture has a licence KalaVigyan accepts, its author, credit line, size and the Commons widths the "
    "site draws; KalaVigyan's team places such pictures, credited, and they are never given as one's own. A "
    "pictures search is open to anyone; the rest needs an account of Researcher or above. Each kind of search "
    "counts once against the account's source searches."
)
READ_DESCRIPTION = (
    "Read a source through KalaVigyan's own fetcher exactly as the QUOTES gate will: the text in the gate's "
    "normalisation, a page at a time from start, or every passage around the words you give, each with its "
    "locator, the licence the page states, the grade the gates will record, whether KalaVigyan holds it and an "
    "archived copy where one exists. A doi is read from its open-access copy when Unpaywall knows one; the url "
    "returned is the one to cite, and a source given with supply_source is read from the text given. quotes "
    "runs the gate's matcher on each without proposing: passed or failed with the gate's reasons, where it "
    "stands, or the nearest passage and the share of its words it holds. archive asks the Wayback Machine to "
    "save the page (up to two minutes). With quotes or archive the text comes back only when around or start "
    "is named. Needs an account of Researcher or above; the text and each quote count as source reads, an "
    "archive as a source archive."
)
LOOKUP_DESCRIPTION = (
    "Look up a compound in PubChem as KalaVigyan's science engine does: its record (CID, formula, molecular "
    "weight, IUPAC name, InChIKey, SMILES), its GHS hazards as PubChem's attributed sources report them, and "
    "the name and synonyms KalaVigyan holds; or Wikidata items for a place, a plant or a craft: each item's "
    "label, statements (a plant's taxon name, a place's coordinates and area), CC0 licence and grade. Give a "
    "name (up to three items) or an id. Open to anyone; signed in, it counts as a source read."
)

Asker = Callable[[ToolContext, str], LookupAsk]


@dataclass
class _Reading:
    text: SourceText | None = None
    quotes: list[QuoteCheck] = field(default_factory=list)
    archive: ArchivedSource | None = None
    notices: list[str] = field(default_factory=list)

    def holds(self) -> bool:
        return self.text is not None or bool(self.quotes) or self.archive is not None

    async def kept[T](self, work: Awaitable[T]) -> T | None:
        try:
            return await work
        except InvalidInput as refused:
            if not self.holds():
                raise
            self.notices.append(str(refused))
            return None

    def reply(self) -> SourceReading:
        return SourceReading(text=self.text, quotes=self.quotes, archive=self.archive, notices=self.notices)


def _asker(deps: LookupDeps) -> Asker:
    def ask(context: ToolContext, tool: str) -> LookupAsk:
        return LookupAsk(session=context.session, user=context.user, tool=tool, deps=deps)

    return ask


def _searched(
    arguments: SearchSources, found: FoundSources | None, pictures: FoundPictures | None
) -> SourceSearch:
    parts: list[Any] = [part for part in (found, pictures) if part is not None]
    return SourceSearch(
        query=parts[0].query,
        kinds=list(dict.fromkeys(arguments.kinds)),
        sources=[] if found is None else found.sources,
        pictures=[] if pictures is None else pictures.pictures,
        searched=[name for part in parts for name in part.searched],
        unavailable=[name for part in parts for name in part.unavailable],
        notices=[] if found is None else found.notices,
    )


def _search(ask: Asker) -> Callable[[ToolContext, SearchSources], Awaitable[SourceSearch]]:
    async def search(context: ToolContext, arguments: SearchSources) -> SourceSearch:
        asked = ask(context, SEARCH_SOURCES)
        texts = [kind for kind in dict.fromkeys(arguments.kinds) if kind != PICTURES]
        found = await search_call(asked, arguments.query, arguments.craft_slug, texts) if texts else None
        pictures = None
        if PICTURES in arguments.kinds:
            pictures = await pictures_call(asked, arguments.query, arguments.craft_slug)
        return _searched(arguments, found, pictures)

    return search


def _read(ask: Asker) -> Callable[[ToolContext, ReadSource], Awaitable[SourceReading]]:
    async def read(context: ToolContext, arguments: ReadSource) -> SourceReading:
        asked, reading = ask(context, READ_SOURCE), _Reading()
        if arguments.wants_text():
            view = TextView(around=arguments.around, start=arguments.start or 1)
            reading.text = await read_call(asked, arguments.url, arguments.doi, view)
        for quote in arguments.quotes:
            checked = await reading.kept(check_call(asked, arguments.url, arguments.doi, quote))
            if checked is None:
                return reading.reply()
            reading.quotes.append(checked)
        if arguments.archive:
            reading.archive = await reading.kept(archive_call(asked, str(arguments.url)))
        return reading.reply()

    return read


def _lookup(ask: Asker) -> Callable[[ToolContext, Lookup], Awaitable[LookupReply]]:
    async def lookup(context: ToolContext, arguments: Lookup) -> LookupReply:
        asked = ask(context, LOOKUP)
        if arguments.kind == COMPOUND:
            compounds = await compound_call(asked, arguments.name, arguments.cid())
            return LookupReply(
                kind=arguments.kind,
                query=compounds.query,
                compounds=compounds.compounds,
                notices=compounds.notices,
            )
        entities = await entity_call(asked, arguments.name, arguments.qid())
        return LookupReply(kind=arguments.kind, query=entities.query, entities=entities.entities)

    return lookup


def lookup_tools(deps: LookupDeps) -> tuple[Tool, ...]:
    ask = _asker(deps)
    return (
        Tool(
            SEARCH_SOURCES,
            "Search sources and pictures",
            SEARCH_DESCRIPTION,
            SearchSources,
            SourceSearch,
            _search(ask),
            CONTRIBUTE_SCOPE,
            LOOKS,
            group=SOURCES,
            scope_of=search_scope,
        ),
        Tool(
            READ_SOURCE,
            "Read a source and check quotes",
            READ_DESCRIPTION,
            ReadSource,
            SourceReading,
            _read(ask),
            CONTRIBUTE_SCOPE,
            LOOKS,
            group=SOURCES,
        ),
        Tool(
            LOOKUP,
            "Look up a compound, place, plant or craft",
            LOOKUP_DESCRIPTION,
            Lookup,
            LookupReply,
            _lookup(ask),
            READ_SCOPE,
            LOOKS,
            group=SOURCES,
        ),
    )


LOOKUP_TOOLS = lookup_tools(LookupDeps())
