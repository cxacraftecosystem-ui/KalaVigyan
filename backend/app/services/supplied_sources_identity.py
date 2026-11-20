from __future__ import annotations

import logging
from collections.abc import AsyncIterator, Awaitable, Callable, Sequence
from contextlib import asynccontextmanager

import httpx
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.research.evidence import SEARCH_QUERY_MAX_CHARS, EvidenceItem, SearchQuery
from app.research.supplied_sources import SourceIdentity, matching_work
from app.sources.adapter import HttpSourceAdapter
from app.sources.scholarly.registry import scholarly_sources

from .scholarly_keys import scholarly_keys

__all__ = ["IDENTITY_INDEXES", "IdentityLookup", "index_lookup", "no_lookup", "scholarly_lookup"]

logger = logging.getLogger(__name__)

IDENTITY_INDEXES = ("openalex", "crossref", "semantic_scholar")
RESULTS_PER_INDEX = 5

IdentityLookup = Callable[[SourceIdentity], Awaitable[EvidenceItem | None]]


async def no_lookup(identity: SourceIdentity) -> EvidenceItem | None:
    return None


def index_lookup(adapters: Sequence[HttpSourceAdapter]) -> IdentityLookup:
    async def lookup(identity: SourceIdentity) -> EvidenceItem | None:
        try:
            query = SearchQuery(text=identity.title[:SEARCH_QUERY_MAX_CHARS])
        except ValidationError:
            return None
        for adapter in adapters:
            try:
                found = await adapter.search(query, RESULTS_PER_INDEX)
            except AppError as failure:
                logger.warning("%s could not confirm a supplied source: %s", adapter.name, failure)
                continue
            match = matching_work(identity, found)
            if match is not None:
                return match
        return None

    return lookup


@asynccontextmanager
async def scholarly_lookup(session: AsyncSession) -> AsyncIterator[IdentityLookup]:
    keys = await scholarly_keys(session)
    async with httpx.AsyncClient() as client:
        try:
            sources = scholarly_sources(keys, client)
        except AppError as failure:
            logger.warning("supplied sources are graded unconfirmed: %s", failure)
            yield no_lookup
            return
        named = {adapter.name: adapter for adapter in sources.adapters}
        yield index_lookup([named[name] for name in IDENTITY_INDEXES if name in named])
