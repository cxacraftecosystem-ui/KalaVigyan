from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.errors import ExternalFailure
from app.models import Source
from app.sources.scholarly.crossref import CrossrefAdapter

from .live_sources import LiveSourcesStore

__all__ = [
    "JournalLookup",
    "JournalRead",
    "StoredDoi",
    "crossref_journals",
    "journal_reads",
    "store_journals",
    "unjournaled",
]

JournalLookup = Callable[[str], Awaitable[str | None]]


@dataclass(frozen=True)
class StoredDoi:
    id: uuid.UUID
    doi: str


@dataclass(frozen=True)
class JournalRead:
    id: uuid.UUID
    doi: str
    journal: str | None
    problem: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {"id": str(self.id), "doi": self.doi, "journal": self.journal, "problem": self.problem}


async def unjournaled(session: AsyncSession, *, limit: int | None = None) -> list[StoredDoi]:
    query = (
        select(Source.id, Source.doi)
        .where(Source.doi.is_not(None), Source.containerTitle.is_(None))
        .order_by(Source.createdAt, Source.id)
        .limit(limit)
    )
    return [StoredDoi(source_id, doi) for source_id, doi in (await session.execute(query)).tuples() if doi]


async def crossref_journals(
    sessions: async_sessionmaker[AsyncSession], live: LiveSourcesStore
) -> JournalLookup:
    return (await live.reference(sessions, CrossrefAdapter)).container_title


async def journal_reads(stored: Sequence[StoredDoi], lookup: JournalLookup) -> list[JournalRead]:
    reads: list[JournalRead] = []
    for source in stored:
        try:
            reads.append(JournalRead(source.id, source.doi, await lookup(source.doi)))
        except ExternalFailure as failure:
            reads.append(JournalRead(source.id, source.doi, None, problem=str(failure)))
    return reads


async def store_journals(session: AsyncSession, reads: Sequence[JournalRead]) -> int:
    stored = 0
    for read in reads:
        if read.journal is None:
            continue
        result = await session.execute(
            update(Source)
            .where(Source.id == read.id, Source.containerTitle.is_(None))
            .values(containerTitle=read.journal)
        )
        stored += result.rowcount
    return stored
