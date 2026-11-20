from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ExternalFailure, InvalidInput, NotConfigured
from app.core.rate_limit import PAID_SEARCHES, SOURCE_ARCHIVES, SOURCE_READS, SOURCE_SEARCHES
from app.models import User
from app.research.knowledge_writes import ProposedQuote

from .source_lookup import SearchAsk, found_sources, query_for
from .source_lookup_allowance import (
    LookupCaller,
    TierOf,
    account_tier,
    contributor_caller,
    lookup_caller,
    spend,
    spent_wait,
    wait_words,
)
from .source_lookup_archive import archived_source
from .source_lookup_models import (
    ArchivedSource,
    CompoundLookup,
    EntityLookup,
    FoundPictures,
    FoundSources,
    QuoteCheck,
    SourceText,
)
from .source_lookup_pictures import found_pictures
from .source_lookup_read import TextView, checked_quote, source_address, source_text
from .source_lookup_reference import compound_lookup, entity_lookup
from .source_lookup_sources import LookupSources
from .source_lookup_store import lookup_sources

__all__ = [
    "LookupAsk",
    "LookupDeps",
    "archive_call",
    "check_call",
    "compound_call",
    "entity_call",
    "pictures_call",
    "read_call",
    "search_call",
]

UNAVAILABLE = (
    "{service} could not be reached just now and nothing was read; call the tool again in a few minutes."
)
NOT_CONFIGURED = "The source tools are not set up on this server yet; nothing was read."
NO_ADAPTER = "{name} is not among this server's sources just now; nothing was read."
SERVICE_NAMES = {
    "fetcher": "KalaVigyan's page reader",
    "wayback-save": "The Wayback Machine",
    "pubchem": "PubChem",
    "wikidata": "Wikidata",
    "wikidata_sparql": "Wikidata",
}


@dataclass(frozen=True)
class LookupDeps:
    sources: Callable[[], Awaitable[LookupSources]] = lookup_sources
    tier: TierOf = account_tier


@dataclass(frozen=True)
class LookupAsk:
    session: AsyncSession
    user: User | None
    tool: str
    deps: LookupDeps

    def reader_id(self) -> uuid.UUID | None:
        return self.user.id if self.user is not None else None

    async def contributor(self) -> LookupCaller:
        return await contributor_caller(self.session, self.user, self.tool, self.deps.tier)

    async def anyone(self) -> LookupCaller:
        return await lookup_caller(self.session, self.user, self.deps.tier)

    async def sources(self) -> LookupSources:
        return await external(self.deps.sources())


async def external[T](work: Awaitable[T]) -> T:
    try:
        return await work
    except ExternalFailure as failure:
        raise InvalidInput(UNAVAILABLE.format(service=_service(failure))) from None
    except NotConfigured:
        raise InvalidInput(NOT_CONFIGURED) from None


async def search_call(
    ask: LookupAsk, query: str, craft_slug: str | None, kinds: Sequence[str]
) -> FoundSources:
    caller = await ask.contributor()
    text = await query_for(ask.session, query, craft_slug)
    await spend(SOURCE_SEARCHES, caller)
    sources = await ask.sources()
    chosen = tuple(dict.fromkeys(kinds))
    wait = await spent_wait(PAID_SEARCHES, caller) if sources.reaches_paid(chosen) else None
    paid = sources.reaches_paid(chosen) and wait is None
    asked = SearchAsk(
        query=text, kinds=chosen, paid=paid, paid_wait=None if wait is None else wait_words(wait)
    )
    return await external(found_sources(ask.session, sources, asked))


async def read_call(ask: LookupAsk, url: str | None, doi: str | None, view: TextView) -> SourceText:
    await spend(SOURCE_READS, await ask.contributor())
    sources = await ask.sources()
    address = await source_address(sources.locator, url=url, doi=doi)
    return await external(source_text(ask.session, sources, address, view, reader_id=ask.reader_id()))


async def check_call(ask: LookupAsk, url: str | None, doi: str | None, quote: ProposedQuote) -> QuoteCheck:
    await spend(SOURCE_READS, await ask.contributor())
    sources = await ask.sources()
    address = await source_address(sources.locator, url=url, doi=doi)
    return await external(checked_quote(ask.session, sources, address, quote, reader_id=ask.reader_id()))


async def compound_call(ask: LookupAsk, name: str | None, cid: int | None) -> CompoundLookup:
    await spend(SOURCE_READS, await ask.anyone())
    source = (await ask.sources()).compounds
    if source is None:
        raise InvalidInput(NO_ADAPTER.format(name="PubChem"))
    return await external(compound_lookup(ask.session, source, name=name, cid=cid))


async def entity_call(ask: LookupAsk, name: str | None, qid: str | None) -> EntityLookup:
    await spend(SOURCE_READS, await ask.anyone())
    source = (await ask.sources()).entities
    if source is None:
        raise InvalidInput(NO_ADAPTER.format(name="Wikidata"))
    return await external(entity_lookup(source, name=name, qid=qid))


async def pictures_call(ask: LookupAsk, query: str, craft_slug: str | None) -> FoundPictures:
    caller = await ask.anyone()
    text = await query_for(ask.session, query, craft_slug)
    await spend(SOURCE_SEARCHES, caller)
    sources = await ask.sources()
    return await external(found_pictures(sources.pictures, text))


async def archive_call(ask: LookupAsk, url: str) -> ArchivedSource:
    await spend(SOURCE_ARCHIVES, await ask.contributor())
    archiver = (await ask.sources()).archiver
    if archiver is None:
        raise InvalidInput(NO_ADAPTER.format(name="The Wayback Machine"))
    return await external(archived_source(archiver, url))


def _service(failure: ExternalFailure) -> str:
    return SERVICE_NAMES.get(failure.service or "", "A source")
