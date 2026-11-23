from __future__ import annotations

import asyncio
import time
from collections.abc import Callable
from typing import TypeVar

import httpx
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import get_settings
from app.core.db import session_scope
from app.core.errors import NotConfigured
from app.planner.reading import LiveSources
from app.research.images import ImageSource
from app.services.scholarly_keys import scholarly_keys
from app.services.web_fetches import web_fetch_recorder
from app.services.web_sources import web_search_config
from app.sources.adapter import HttpSourceAdapter
from app.sources.fetcher_client import FetcherClient
from app.sources.http import source_client
from app.sources.images.registry import image_sources
from app.sources.images.web_images import with_web_image_fallback
from app.sources.reference.registry import reference_sources
from app.sources.scholarly.registry import scholarly_sources
from app.sources.web.brave import BraveAdapter
from app.sources.web.fallback import WebSearch
from app.sources.web.registry import web_search
from app.sources.web.searxng import SearxngAdapter

__all__ = ["DOI_SOURCE", "LIVE_SOURCES_TTL_SECONDS", "LiveSourcesStore", "live_source_client", "live_sources"]

DOI_SOURCE = "crossref"
LIVE_SOURCES_TTL_SECONDS = 600

AdapterT = TypeVar("AdapterT", bound=HttpSourceAdapter)


def live_source_client() -> httpx.AsyncClient:
    return source_client(str(get_settings().research_contact_email))


async def live_sources(session: AsyncSession, client: httpx.AsyncClient) -> LiveSources:
    fetcher = FetcherClient(get_settings().fetcher_url, client, record=web_fetch_recorder(session_scope))
    scholarly = scholarly_sources(await scholarly_keys(session), client)
    web = web_search(await web_search_config(session), client, fetcher)
    doi_source = next((adapter for adapter in scholarly.adapters if adapter.name == DOI_SOURCE), None)
    if doi_source is None:
        raise NotConfigured(DOI_SOURCE, f"The {DOI_SOURCE} adapter follows cited DOIs and must be built")
    return LiveSources(
        searchers=(*scholarly.adapters, *reference_sources(client), web),
        fetcher=fetcher,
        locator=scholarly.locator,
        doi_source=doi_source,
    )


class LiveSourcesStore:
    def __init__(
        self,
        *,
        ttl_seconds: float = LIVE_SOURCES_TTL_SECONDS,
        clock: Callable[[], float] = time.monotonic,
        client_factory: Callable[[], httpx.AsyncClient] = live_source_client,
    ) -> None:
        self._ttl = ttl_seconds
        self._clock = clock
        self._client_factory = client_factory
        self._client: httpx.AsyncClient | None = None
        self._sources: LiveSources | None = None
        self._images: tuple[ImageSource, ...] | None = None
        self._built_at = 0.0
        self._lock = asyncio.Lock()

    async def get(self, sessions: async_sessionmaker[AsyncSession]) -> LiveSources:
        async with self._lock:
            if self._sources is None or self._clock() - self._built_at >= self._ttl:
                if self._client is None:
                    self._client = self._client_factory()
                async with sessions() as session:
                    self._sources = await live_sources(session, self._client)
                self._built_at = self._clock()
            return self._sources

    async def reference(self, sessions: async_sessionmaker[AsyncSession], kind: type[AdapterT]) -> AdapterT:
        sources = await self.get(sessions)
        found = next((source for source in sources.searchers if isinstance(source, kind)), None)
        if found is None:
            raise NotConfigured(kind.name, f"The {kind.name} adapter is not among the live sources")
        return found

    async def images(self) -> tuple[ImageSource, ...]:
        async with self._lock:
            if self._client is None:
                self._client = self._client_factory()
            if self._images is None:
                settings = get_settings()
                fetcher = FetcherClient(settings.fetcher_url, self._client)
                self._images = image_sources(self._client, searxng_url=settings.searxng_url, fetcher=fetcher)
            return self._images

    async def web_images(self, sessions: async_sessionmaker[AsyncSession]) -> tuple[ImageSource, ...]:
        images = await self.images()
        web = next((s for s in (await self.get(sessions)).searchers if isinstance(s, WebSearch)), None)
        brave = (
            next((a for a in web.adapters if isinstance(a, BraveAdapter)), None) if web is not None else None
        )
        return with_web_image_fallback(images, primary_name=SearxngAdapter.name, fallback=brave)

    async def aclose(self) -> None:
        client, self._client, self._sources, self._images = self._client, None, None, None
        if client is not None:
            await client.aclose()
