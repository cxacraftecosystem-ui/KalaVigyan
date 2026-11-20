from __future__ import annotations

import httpx

from app.core.db import sessionmaker
from app.core.errors import NotConfigured
from app.research.fetcher import FetchedPage
from app.sources.wayback_save import WaybackSaver

from .live_sources import LiveSourcesStore, live_source_client
from .source_lookup_archive import WaybackSnapshots, wayback_snapshots
from .source_lookup_sources import CachedFetcher, LookupSources, TtlCache, from_live

__all__ = ["LOOKUP_STORE", "LookupStore", "lookup_sources"]

NO_FETCHER = "The live sources hold no fetcher, so no page can be read"


class LookupStore:
    def __init__(self, live: LiveSourcesStore | None = None) -> None:
        self._live = live or LiveSourcesStore()
        self._pages: TtlCache[str, FetchedPage] = TtlCache()
        self._client: httpx.AsyncClient | None = None
        self._extras: tuple[WaybackSaver, WaybackSnapshots] | None = None

    async def sources(self) -> LookupSources:
        live = await self._live.get(sessionmaker())
        if live.fetcher is None:
            raise NotConfigured("fetcher", NO_FETCHER)
        images = await self._live.images()
        return from_live(live, images, CachedFetcher(live.fetcher, self._pages), self._archive_tools())

    def _archive_tools(self) -> tuple[WaybackSaver, WaybackSnapshots]:
        if self._extras is None:
            self._client = self._client or live_source_client()
            self._extras = (WaybackSaver(self._client), wayback_snapshots(self._client))
        return self._extras


LOOKUP_STORE = LookupStore()


async def lookup_sources() -> LookupSources:
    return await LOOKUP_STORE.sources()
