from __future__ import annotations

import re
from bisect import bisect_right
from collections.abc import Sequence

from app.research.quotes import quote_key, spans_in_key

__all__ = ["PASSAGE_MAX_CHARS", "passage_around"]

PASSAGE_MAX_CHARS = 1200
PARAGRAPH_BREAK = re.compile(r"\n[ \t]*\n")
SENTENCE_END = re.compile(r"(?<=[.!?])\s+")


def passage_around(text: str, quote: str) -> str | None:
    paragraphs = [part.strip() for part in PARAGRAPH_BREAK.split(text) if part.strip()]
    holding = next((part for part in paragraphs if spans_in_key(quote, quote_key(part))), None)
    if holding is not None and len(holding) <= PASSAGE_MAX_CHARS:
        return holding
    return _window(holding or text, quote)


def _window(text: str, quote: str) -> str | None:
    pieces = [(part, key) for part in SENTENCE_END.split(text) if (key := quote_key(part))]
    keys = [key for _, key in pieces]
    found = spans_in_key(quote, " ".join(keys))
    if not found:
        return None
    first, last = _covering(keys, found[0])
    low, high = _widened([len(part) for part, _ in pieces], first, last)
    return " ".join(part.strip() for part, _ in pieces[low : high + 1])


def _covering(keys: Sequence[str], span: tuple[int, int]) -> tuple[int, int]:
    starts: list[int] = []
    at = 0
    for key in keys:
        starts.append(at)
        at += len(key) + 1
    start, end = span
    return bisect_right(starts, start) - 1, bisect_right(starts, max(start, end - 1)) - 1


def _widened(lengths: Sequence[int], first: int, last: int) -> tuple[int, int]:
    low, high = first, last
    size = sum(lengths[low : high + 1]) + high - low
    grown = True
    while grown:
        grown = False
        if low > 0 and size + 1 + lengths[low - 1] <= PASSAGE_MAX_CHARS:
            low -= 1
            size += 1 + lengths[low]
            grown = True
        if high < len(lengths) - 1 and size + 1 + lengths[high + 1] <= PASSAGE_MAX_CHARS:
            high += 1
            size += 1 + lengths[high]
            grown = True
    return low, high
