from __future__ import annotations

import asyncio
import logging
from collections.abc import Sequence
from dataclasses import dataclass

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ExternalFailure, InvalidInput
from app.models import Source
from app.planner.live_search import evidence_rank
from app.planner.policy import SEARCH_TIMEOUT_SECONDS
from app.research.evidence import (
    SEARCH_QUERY_MAX_CHARS,
    EvidenceItem,
    OpenAccessLocation,
    OpenAccessLocator,
    SearchQuery,
    SourceAdapter,
    canonical_url,
)
from app.research.evidence_pack import PackedEvidence
from app.research.licences import open_licence

from . import knowledge_api
from .source_lookup_models import FoundSources, OpenCopy, SourceHit
from .source_lookup_sources import LookupSources

__all__ = [
    "OPEN_COPIES_MAX",
    "RESULTS_PER_SOURCE",
    "SOURCES_MAX",
    "SearchAsk",
    "found_sources",
    "held_sources",
    "open_copy",
    "query_for",
]

logger = logging.getLogger(__name__)

RESULTS_PER_SOURCE = 5
SOURCES_MAX = 30
OPEN_COPIES_MAX = 10
EXCERPTS_MAX = 2
EVERY_SEARCH_FAILED = "Every source search failed just now; nothing was found. Try again in a few minutes."
PAID_SKIPPED = (
    "Brave and Elsevier were left out: this account's paid searches for the hour are spent, and they return "
    "in {wait}."
)


@dataclass(frozen=True)
class SearchAsk:
    query: str
    kinds: tuple[str, ...]
    paid: bool
    paid_wait: str | None = None


@dataclass(frozen=True)
class _Hit:
    searcher: str
    rank: int
    item: EvidenceItem


async def query_for(session: AsyncSession, text: str, craft_slug: str | None) -> str:
    if craft_slug is None:
        return text
    craft = await knowledge_api.known_craft(session, craft_slug)
    if craft.name.casefold() in text.casefold():
        return text
    return f"{text} {craft.name}"[:SEARCH_QUERY_MAX_CHARS].strip()


async def found_sources(session: AsyncSession, sources: LookupSources, ask: SearchAsk) -> FoundSources:
    searchers = sources.searchers(ask.kinds, paid=ask.paid)
    query = SearchQuery(text=ask.query)
    results = await asyncio.gather(*(_searched(searcher, query) for searcher in searchers))
    answered = [
        searcher.name for searcher, found in zip(searchers, results, strict=True) if found is not None
    ]
    if searchers and not answered:
        raise InvalidInput(EVERY_SEARCH_FAILED)
    hits = [hit for found in results if found for hit in found]
    packed = _packed(hits)[:SOURCES_MAX]
    items = [entry.item for entry in packed]
    held = await held_sources(session, items)
    copies = await _open_copies(sources.locator, items)
    return FoundSources(
        query=ask.query,
        kinds=list(ask.kinds),
        sources=[
            _hit(entry, held.get(entry.item.source_key), copies.get(entry.item.doi)) for entry in packed
        ],
        searched=answered,
        unavailable=[searcher.name for searcher in searchers if searcher.name not in answered],
        notices=[PAID_SKIPPED.format(wait=ask.paid_wait)] if ask.paid_wait else [],
    )


async def held_sources(session: AsyncSession, items: Sequence[EvidenceItem]) -> dict[str, Source]:
    urls = sorted({url for item in items for url in (item.url, canonical_url(item.url))})
    dois = sorted({item.doi.lower() for item in items if item.doi})
    if not urls and not dois:
        return {}
    rows = await session.scalars(
        select(Source).where(or_(Source.url.in_(urls), func.lower(Source.doi).in_(dois)))
    )
    by_key: dict[str, Source] = {}
    for row in rows:
        if row.doi:
            by_key.setdefault(f"doi:{row.doi.lower()}", row)
        by_key.setdefault(f"url:{canonical_url(row.url)}", row)
    held: dict[str, Source] = {}
    for item in items:
        match = next((by_key[key] for key in _keys(item) if key in by_key), None)
        if match is not None:
            held[item.source_key] = match
    return held


def _keys(item: EvidenceItem) -> list[str]:
    keys = [f"doi:{item.doi.lower()}"] if item.doi else []
    return [*keys, f"url:{canonical_url(item.url)}"]


async def _searched(searcher: SourceAdapter, query: SearchQuery) -> list[_Hit] | None:
    try:
        items = await asyncio.wait_for(searcher.search(query, RESULTS_PER_SOURCE), SEARCH_TIMEOUT_SECONDS)
    except (ExternalFailure, InvalidInput, TimeoutError) as failure:
        logger.warning("source lookup: %s search failed (%s)", searcher.name, type(failure).__name__)
        return None
    return [_Hit(searcher.name, rank, item) for rank, item in enumerate(items, start=1)]


def _packed(hits: Sequence[_Hit]) -> list[PackedEvidence]:
    groups: dict[str, list[_Hit]] = {}
    for hit in hits:
        groups.setdefault(hit.item.source_key, []).append(hit)
    packed = [_entry(group) for group in groups.values()]
    return sorted(packed, key=evidence_rank)


def _entry(group: Sequence[_Hit]) -> PackedEvidence:
    lead = min(group, key=lambda hit: (hit.item.trust, -len(hit.item.quotes), hit.rank))
    return PackedEvidence(
        item=lead.item,
        facet_indexes=(0,),
        found_by=tuple(dict.fromkeys([lead.searcher, *(hit.searcher for hit in group)])),
        hits=len({hit.searcher for hit in group}),
        best_rank=min(hit.rank for hit in group),
    )


async def _open_copies(
    locator: OpenAccessLocator | None, items: Sequence[EvidenceItem]
) -> dict[str | None, OpenAccessLocation]:
    dois = list(dict.fromkeys(item.doi for item in items if item.doi))[:OPEN_COPIES_MAX]
    if locator is None or not dois:
        return {}
    found = await asyncio.gather(*(locator.locate(doi) for doi in dois), return_exceptions=True)
    return {
        doi: copy
        for doi, copy in zip(dois, found, strict=True)
        if isinstance(copy, OpenAccessLocation) and copy.is_open
    }


def open_copy(location: OpenAccessLocation | None) -> OpenCopy | None:
    if location is None or not location.is_open:
        return None
    url = location.pdf_url or location.landing_url
    if url is None:
        return None
    return OpenCopy(
        status=location.status,
        url=url,
        landing_url=location.landing_url,
        pdf_url=location.pdf_url,
        licence=location.licence,
        open_licence=open_licence(location.licence),
        version=location.version,
    )


def _hit(entry: PackedEvidence, held: Source | None, copy: OpenAccessLocation | None) -> SourceHit:
    item = entry.item
    return SourceHit(
        title=item.title,
        url=item.url,
        doi=item.doi,
        kind=item.source_type,
        found_by=list(entry.found_by),
        published=item.published,
        authors=list(item.authors),
        publisher=item.publisher,
        grade=held.reliability if held is not None else item.trust,
        held=held is not None,
        licence=item.licence,
        open_licence=open_licence(item.licence),
        open_copy=open_copy(copy),
        excerpts=[quote.text for quote in item.quotes[:EXCERPTS_MAX]],
    )
