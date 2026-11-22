from __future__ import annotations

import uuid
from collections.abc import Sequence
from dataclasses import dataclass

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Chunk, ClaimSource, Source
from app.research.quotes import quote_key
from app.research.retrieval import OPEN_CHUNK_ACLS, PUBLIC_CHUNK_ACL
from app.research.storable import storable_text

from .citation_access import FAILED_QUOTE, readable_citation
from .quote_passages import Holding, QuotePassages, source_passages

__all__ = ["CitedQuote", "cited_quotes", "relink_quotes"]


@dataclass(frozen=True)
class CitedQuote:
    id: uuid.UUID
    quote: str
    chunk_id: uuid.UUID | None
    locator: str | None
    passage_locator: str | None
    public: bool

    def pointer(self, holding: Holding | None) -> tuple[uuid.UUID | None, str | None]:
        if holding is None or self._own_locator():
            return (None if holding is None else holding.chunk_id), self.locator
        return holding.chunk_id, holding.locator

    def _own_locator(self) -> bool:
        return self.locator is not None and self.locator != self.passage_locator


async def cited_quotes(session: AsyncSession, source_id: uuid.UUID) -> list[CitedQuote]:
    public = set(
        await session.scalars(
            select(ClaimSource.id).where(
                ClaimSource.sourceId == source_id,
                ClaimSource.quoteCheck != FAILED_QUOTE,
                readable_citation(OPEN_CHUNK_ACLS),
            )
        )
    )
    rows = await session.execute(
        select(
            ClaimSource.id,
            ClaimSource.quote,
            ClaimSource.chunkId,
            ClaimSource.locator,
            Chunk.locator.label("passage"),
        )
        .outerjoin(Chunk, Chunk.id == ClaimSource.chunkId)
        .where(ClaimSource.sourceId == source_id, ClaimSource.quote.is_not(None))
        .order_by(ClaimSource.id)
    )
    return [
        CitedQuote(row.id, row.quote, row.chunkId, row.locator, row.passage, row.id in public) for row in rows
    ]


async def relink_quotes(
    session: AsyncSession, source: Source, cited: Sequence[CitedQuote], *, lang: str
) -> int:
    if not cited:
        return 0
    passages = await source_passages(session, source.id)
    kept = _KeptQuotes(source, lang, passages.next_ordinal())
    pointers = [(cite, cite.pointer(_resting_place(cite, passages, kept))) for cite in cited]
    session.add_all(kept.chunks)
    await session.flush()
    for cite, (chunk_id, locator) in pointers:
        if (chunk_id, locator) != (cite.chunk_id, cite.locator):
            await session.execute(
                update(ClaimSource).where(ClaimSource.id == cite.id).values(chunkId=chunk_id, locator=locator)
            )
    await session.flush()
    return len(kept.chunks)


class _KeptQuotes:
    def __init__(self, source: Source, lang: str, ordinal: int) -> None:
        self._source = source
        self._lang = lang
        self._ordinal = ordinal
        self._kept: dict[str, Holding] = {}
        self.chunks: list[Chunk] = []

    def keep(self, cite: CitedQuote, found: Holding | None) -> Holding:
        key = quote_key(cite.quote)
        if key not in self._kept:
            locator = found.locator if found is not None else cite.locator
            chunk = Chunk(
                id=uuid.uuid4(),
                sourceId=self._source.id,
                ordinal=self._ordinal + len(self.chunks),
                locator=locator,
                text=storable_text(cite.quote),
                lang=self._lang,
                acl=PUBLIC_CHUNK_ACL,
                sensitivity=self._source.sensitivity,
            )
            self.chunks.append(chunk)
            self._kept[key] = Holding(chunk.id, locator, PUBLIC_CHUNK_ACL)
        return self._kept[key]


def _resting_place(cite: CitedQuote, passages: QuotePassages, kept: _KeptQuotes) -> Holding | None:
    found = passages.holding(cite.quote)
    if cite.public and (found is None or found.acl != PUBLIC_CHUNK_ACL):
        return kept.keep(cite, found)
    return found
