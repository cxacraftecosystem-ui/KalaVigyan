from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.errors import NotConfigured
from app.research.embedding import TextEmbedder
from app.research.retrieval import OPEN_CHUNK_ACLS
from app.research.structured import StructuredModel

from .answer_store import build_answer_translation
from .live_sources import LiveSourcesStore
from .term_research import LiveTermResearch, Searcher
from .term_store import SqlTermStore
from .term_summaries import StoredTermLookup, TermLookup

__all__ = ["WEB_SEARCHER", "WIKIPEDIA_SEARCHER", "build_term_lookup", "stored_term_lookup"]

WIKIPEDIA_SEARCHER = "wikipedia"
WEB_SEARCHER = "web"


async def build_term_lookup(
    *,
    sessions: async_sessionmaker[AsyncSession],
    live: LiveSourcesStore,
    summarise_model: StructuredModel,
    translate_model: StructuredModel,
    acls: Sequence[str] = OPEN_CHUNK_ACLS,
    embed: TextEmbedder | None = None,
) -> TermLookup:
    sources = await live.get(sessions)
    research = LiveTermResearch(
        wikipedia=_searcher(sources.searchers, WIKIPEDIA_SEARCHER),
        web=_searcher(sources.searchers, WEB_SEARCHER),
        summarise=summarise_model,
    )
    return TermLookup(
        store=SqlTermStore(sessions, acls=acls, embed=embed),
        research=research,
        translation=build_answer_translation(sessions, model=translate_model),
    )


def stored_term_lookup(
    sessions: async_sessionmaker[AsyncSession], *, acls: Sequence[str] = OPEN_CHUNK_ACLS
) -> StoredTermLookup:
    return StoredTermLookup(store=SqlTermStore(sessions, acls=acls))


def _searcher(searchers: tuple, name: str) -> Searcher:
    found = next((searcher for searcher in searchers if searcher.name == name), None)
    if found is None:
        raise NotConfigured(name, f"The {name} source is needed for term summaries and is not built")
    return found
