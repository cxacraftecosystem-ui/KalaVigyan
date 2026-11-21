from __future__ import annotations

import re
import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from itertools import pairwise

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Chunk
from app.research.quotes import occurs_in_key, quote_key

__all__ = [
    "PASSAGE_JOIN",
    "Holding",
    "Passage",
    "QuotePassages",
    "source_passages",
    "spanned_locator",
]

PASSAGE_JOIN = "\n\n"
PARAGRAPHS = re.compile(r"^paras? (\d+)(?:-(\d+))?$")


@dataclass(frozen=True)
class Passage:
    id: uuid.UUID
    ordinal: int
    locator: str | None
    text: str
    acl: str


@dataclass(frozen=True)
class Holding:
    chunk_id: uuid.UUID
    locator: str | None
    acl: str


class QuotePassages:
    def __init__(self, passages: Sequence[Passage]) -> None:
        self.passages = tuple(passages)
        self._keys = [quote_key(passage.text) for passage in self.passages]
        self._pairs: dict[int, str] = {}

    def holding(self, quote: str) -> Holding | None:
        for passage, key in zip(self.passages, self._keys, strict=True):
            if occurs_in_key(quote, key):
                return Holding(passage.id, passage.locator, passage.acl)
        for index, (first, second) in enumerate(pairwise(self.passages)):
            if _adjacent(first, second) and occurs_in_key(quote, self._pair_key(index)):
                return Holding(first.id, spanned_locator(first.locator, second.locator), first.acl)
        return None

    def next_ordinal(self) -> int:
        return max((passage.ordinal for passage in self.passages), default=-1) + 1

    def _pair_key(self, index: int) -> str:
        if index not in self._pairs:
            first, second = self.passages[index], self.passages[index + 1]
            self._pairs[index] = quote_key(first.text + PASSAGE_JOIN + second.text)
        return self._pairs[index]


async def source_passages(session: AsyncSession, source_id: uuid.UUID) -> QuotePassages:
    rows = await session.execute(
        select(Chunk.id, Chunk.ordinal, Chunk.locator, Chunk.text, Chunk.acl)
        .where(Chunk.sourceId == source_id)
        .order_by(Chunk.ordinal)
    )
    return QuotePassages([Passage(row.id, row.ordinal, row.locator, row.text, row.acl) for row in rows])


def spanned_locator(first: str | None, last: str | None) -> str | None:
    start, end = _paragraphs(first), _paragraphs(last)
    if start is None or end is None:
        return first
    low, high = start[0], max(start[1], end[1])
    return f"para {low}" if low == high else f"paras {low}-{high}"


def _paragraphs(locator: str | None) -> tuple[int, int] | None:
    found = PARAGRAPHS.match(locator or "")
    if found is None:
        return None
    low = int(found.group(1))
    return low, int(found.group(2) or low)


def _adjacent(first: Passage, second: Passage) -> bool:
    return second.ordinal == first.ordinal + 1 and second.acl == first.acl
