from __future__ import annotations

import re
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass

from app.research.quotes import normalise_quote_text, quote_key, quote_occurs

from .source_lookup_models import NearestMatch, Passage

__all__ = [
    "CONTEXT_LINES",
    "FOUND_AT_MAX",
    "LINE",
    "PAGE_CHARS",
    "PARAGRAPH",
    "SPAN_LINES",
    "WINDOWS_MAX",
    "WINDOW_CHARS",
    "found_at",
    "nearest_match",
    "page_of",
    "windows_around",
]

PAGE_CHARS = 8000
WINDOW_CHARS = 500
WINDOWS_MAX = 8
CONTEXT_LINES = 1
SPAN_LINES = 4
FOUND_AT_MAX = 3
LINE, PARAGRAPH = "line", "paragraph"
WORD = re.compile(r"\w+")


@dataclass(frozen=True)
class _Word:
    text: str
    line: int
    start: int
    end: int


def locator(unit: str, first: int, last: int) -> str:
    return f"{unit} {first}" if first == last else f"{unit}s {first}-{last}"


def page_of(lines: Sequence[str], unit: str, start: int) -> tuple[list[Passage], int | None]:
    passages: list[Passage] = []
    used, index = 0, start - 1
    while index < len(lines) and (not passages or used + len(lines[index]) <= PAGE_CHARS):
        text, cut = _clipped(lines[index], PAGE_CHARS)
        passages.append(
            Passage(locator=locator(unit, index + 1, index + 1), start=index + 1, text=text, cut=cut)
        )
        used += len(text)
        index += 1
    return passages, index + 1 if index < len(lines) else None


def windows_around(lines: Sequence[str], unit: str, around: str) -> tuple[list[Passage], int]:
    keys = [quote_key(line).casefold() for line in lines]
    phrase = quote_key(around).casefold()
    matches = [index for index, key in enumerate(keys) if phrase and phrase in key]
    if not matches:
        words = phrase.split()
        matches = [index for index, key in enumerate(keys) if words and all(word in key for word in words)]
    return [_window(lines, unit, index, around) for index in matches[:WINDOWS_MAX]], len(matches)


def found_at(lines: Sequence[str], unit: str, quote: str) -> list[str]:
    alone = [index for index, line in enumerate(lines) if quote_occurs(quote, line)]
    if alone:
        return [locator(unit, index + 1, index + 1) for index in alone[:FOUND_AT_MAX]]
    spans: list[str] = []
    for first in range(len(lines)):
        for last in range(first + 1, min(len(lines), first + SPAN_LINES)):
            if quote_occurs(quote, " ".join(lines[first : last + 1])):
                spans.append(locator(unit, first + 1, last + 1))
                break
        if len(spans) >= FOUND_AT_MAX:
            break
    return spans


def nearest_match(lines: Sequence[str], unit: str, quote: str) -> NearestMatch | None:
    wanted = [word.casefold() for word in WORD.findall(normalise_quote_text(quote))]
    words = [
        _Word(found.group().casefold(), number, found.start(), found.end())
        for number, line in enumerate(lines)
        for found in WORD.finditer(line)
    ]
    if not wanted or not words:
        return None
    start, shared = best_window([word.text for word in words], wanted)
    if shared == 0:
        return None
    first, last = words[start], words[min(len(words), start + len(wanted)) - 1]
    return NearestMatch(
        locator=locator(unit, first.line + 1, last.line + 1),
        text=_span_text(lines, first, last),
        shared=round(shared / len(wanted), 2),
    )


def best_window(words: Sequence[str], wanted: Sequence[str]) -> tuple[int, int]:
    need = Counter(wanted)
    size = len(wanted)
    have: Counter[str] = Counter()
    overlap = best = best_start = 0
    for index, word in enumerate(words):
        if have[word] < need[word]:
            overlap += 1
        have[word] += 1
        if index >= size:
            gone = words[index - size]
            if have[gone] <= need[gone]:
                overlap -= 1
            have[gone] -= 1
        if overlap > best:
            best, best_start = overlap, max(0, index - size + 1)
    return best_start, best


def _window(lines: Sequence[str], unit: str, index: int, around: str) -> Passage:
    reach = CONTEXT_LINES if unit == LINE else 0
    first, last = max(0, index - reach), min(len(lines) - 1, index + reach)
    text, cut = _trimmed(" ".join(lines[first : last + 1]), around)
    return Passage(locator=locator(unit, first + 1, last + 1), start=first + 1, text=text, cut=cut)


def _trimmed(text: str, around: str) -> tuple[str, bool]:
    wanted = normalise_quote_text(around)
    if len(text) <= 2 * WINDOW_CHARS + len(wanted):
        return text, False
    at = max(0, text.casefold().find(wanted.casefold()))
    begin = max(0, at - WINDOW_CHARS)
    end = min(len(text), at + len(wanted) + WINDOW_CHARS)
    if begin > 0:
        space = text.find(" ", begin, at)
        begin = space + 1 if space >= 0 else begin
    if end < len(text):
        space = text.rfind(" ", at + len(wanted), end)
        end = space if space >= 0 else end
    return text[begin:end].strip(), True


def _clipped(text: str, limit: int) -> tuple[str, bool]:
    if len(text) <= limit:
        return text, False
    cut = text.rfind(" ", 0, limit)
    return text[: cut if cut > 0 else limit], True


def _span_text(lines: Sequence[str], first: _Word, last: _Word) -> str:
    if first.line == last.line:
        return lines[first.line][first.start : last.end]
    middle = list(lines[first.line + 1 : last.line])
    return " ".join([lines[first.line][first.start :], *middle, lines[last.line][: last.end]])
