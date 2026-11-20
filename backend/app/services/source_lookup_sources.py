from __future__ import annotations

import time
from collections import OrderedDict
from collections.abc import Callable, Collection, Sequence
from dataclasses import dataclass
from typing import Protocol

from app.core.errors import NotConfigured
from app.planner.reading import LiveSources
from app.research.evidence import OpenAccessLocator, SourceAdapter, SourceDocument
from app.research.fetcher import FetchedPage, Fetcher, FetchRequest
from app.research.images import ImageSource
from app.sources.reference.pubchem import PubChemAdapter, PubChemCompound
from app.sources.web.fallback import WebSearch

__all__ = [
    "PAID_ROUTES",
    "PICTURE_SOURCES",
    "REFERENCE",
    "SCHOLARLY",
    "SEARCH_KINDS",
    "WEB",
    "Archiver",
    "CachedFetcher",
    "CompoundSource",
    "LookupSources",
    "SnapshotFinder",
    "TtlCache",
    "from_live",
]

SEARCH_KINDS = ("scholarly", "reference", "web")
SCHOLARLY, REFERENCE, WEB = SEARCH_KINDS
PAID_ROUTES = frozenset({"brave", "elsevier"})
REFERENCE_SEARCHERS = ("wikipedia", "wikidata")
COMPOUND_SOURCE = "pubchem"
ENTITY_SOURCE = "wikidata"
NOT_SCHOLARLY = frozenset({"wikipedia", "wikidata", "pubchem", "wikimedia_commons", "web"})
PICTURE_SOURCES = ("wikimedia_commons", "openverse")
CACHE_SECONDS = 600.0
CACHE_ENTRIES = 256


class Archiver(Protocol):
    async def save(self, url: str) -> str: ...


class SnapshotFinder(Protocol):
    async def closest(self, url: str) -> str | None: ...


class CompoundSource(Protocol):
    name: str

    async def compounds(self, text: str, k: int) -> list[PubChemCompound]: ...

    async def compound(self, cid: int) -> PubChemCompound | None: ...

    async def fetch(self, item_id: str) -> SourceDocument: ...


class TtlCache[K, V]:
    def __init__(
        self,
        *,
        seconds: float = CACHE_SECONDS,
        entries: int = CACHE_ENTRIES,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._seconds = seconds
        self._entries = entries
        self._clock = clock
        self._held: OrderedDict[K, tuple[float, V]] = OrderedDict()

    def get(self, key: K) -> V | None:
        found = self._held.get(key)
        if found is None:
            return None
        stored_at, value = found
        if self._clock() - stored_at > self._seconds:
            del self._held[key]
            return None
        self._held.move_to_end(key)
        return value

    def put(self, key: K, value: V) -> None:
        self._held[key] = (self._clock(), value)
        self._held.move_to_end(key)
        while len(self._held) > self._entries:
            self._held.popitem(last=False)


class CachedFetcher:
    def __init__(self, fetcher: Fetcher, cache: TtlCache[str, FetchedPage]) -> None:
        self.fetcher = fetcher
        self.cache = cache

    async def fetch(self, request: FetchRequest) -> FetchedPage:
        found = self.cache.get(request.url)
        if found is not None:
            return found
        page = await self.fetcher.fetch(request)
        self.cache.put(request.url, page)
        return page


@dataclass(frozen=True)
class LookupSources:
    fetcher: Fetcher
    scholarly: tuple[SourceAdapter, ...] = ()
    reference: tuple[SourceAdapter, ...] = ()
    web: SourceAdapter | None = None
    paid_web: SourceAdapter | None = None
    locator: OpenAccessLocator | None = None
    compounds: CompoundSource | None = None
    entities: SourceAdapter | None = None
    pictures: tuple[ImageSource, ...] = ()
    archiver: Archiver | None = None
    snapshots: SnapshotFinder | None = None

    def searchers(self, kinds: Collection[str], *, paid: bool) -> tuple[SourceAdapter, ...]:
        chosen: list[SourceAdapter] = []
        if SCHOLARLY in kinds:
            chosen.extend(a for a in self.scholarly if paid or a.name not in PAID_ROUTES)
        if REFERENCE in kinds:
            chosen.extend(self.reference)
        web = self.paid_web if paid and self.paid_web is not None else self.web
        if WEB in kinds and web is not None:
            chosen.append(web)
        return tuple(chosen)

    def reaches_paid(self, kinds: Collection[str]) -> bool:
        scholarly = SCHOLARLY in kinds and any(a.name in PAID_ROUTES for a in self.scholarly)
        return scholarly or (WEB in kinds and self.paid_web is not None)


def from_live(
    live: LiveSources,
    images: Sequence[ImageSource],
    fetcher: Fetcher,
    extras: tuple[Archiver, SnapshotFinder],
) -> LookupSources:
    named = {searcher.name: searcher for searcher in live.searchers}
    web, paid_web = _web_routes(named.get(WEB))
    compounds = named.get(COMPOUND_SOURCE)
    if not isinstance(compounds, PubChemAdapter):
        raise NotConfigured(COMPOUND_SOURCE, "The PubChem adapter is not among the live sources")
    return LookupSources(
        fetcher=fetcher,
        scholarly=tuple(s for s in live.searchers if s.name not in NOT_SCHOLARLY),
        reference=tuple(named[name] for name in REFERENCE_SEARCHERS if name in named),
        web=web,
        paid_web=paid_web,
        locator=live.locator,
        compounds=compounds,
        entities=named.get(ENTITY_SOURCE),
        pictures=tuple(source for source in images if source.name in PICTURE_SOURCES),
        archiver=extras[0],
        snapshots=extras[1],
    )


def _web_routes(web: SourceAdapter | None) -> tuple[SourceAdapter | None, SourceAdapter | None]:
    if isinstance(web, WebSearch) and web.fallback is not None:
        return WebSearch(web.primary), web
    return web, None
