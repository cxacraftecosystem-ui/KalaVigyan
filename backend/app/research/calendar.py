from __future__ import annotations

import re
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from itertools import pairwise
from types import MappingProxyType

from .calendar_words import (
    EXCLUDING_BIGRAMS,
    NEGATING_WORDS,
    POINT_WORDS,
    REGIONAL_MONTHS,
    SEASON_WORDS,
    SPAN_WORDS_AFTER,
    SPAN_WORDS_BEFORE,
    SPRING_WORDS_AFTER_REFUSED,
    SPRING_WORDS_BEFORE,
)

__all__ = [
    "EXCLUDING_WORDS",
    "EXCLUDING_WORDS_BEFORE",
    "MAPPING_WORDS_AFTER",
    "MAPPING_WORDS_BEFORE",
    "MONTHS",
    "MONTH_NAMES",
    "first_season",
    "months_named",
    "only_season",
    "regional_month",
    "regional_month_months",
    "regional_months_named",
    "season_months",
    "seasons_named",
    "year_months",
]

MONTHS = 12
MONTH_NAMES = (
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December",
)
AMBIGUOUS_MONTH = "May"
SENTENCE_START = re.compile(r"(?:^|[.!?;:]\s*)$")
MONTH = re.compile(
    r"\b(" + "|".join(name for month in MONTH_NAMES for name in (month, month[:3])) + r"|Sept)\.?(?![a-z])"
)
QUALIFIER = r"(?:(?:early|mid|late)[\s-]+)?"
RANGE_JOIN = re.compile(rf"^\s*(?:to|till|until|through|-|–|—)\s*{QUALIFIER}$")
PAIR_JOIN = re.compile(rf"^\s*(?:and|or)\s*{QUALIFIER}$")
BETWEEN_BEFORE = re.compile(rf"\bbetween\s+{QUALIFIER}$", re.IGNORECASE)
DAY_OR_YEAR_AFTER = re.compile(r"^[\s,/-]*(?:\d{4}|\d{1,2}(?:st|nd|rd|th)?)\b")
DAY_BEFORE = re.compile(r"\b\d{1,2}(?:st|nd|rd|th)?[\s,/-]*$")
DATED_AFTER = re.compile(r"^\s+of\s+\d{4}\b")
CLAUSE_BREAK = re.compile(r"[.;:!?]")
WORD = re.compile(r"\w+")
MONTH_CONTEXT_BEFORE = re.compile(r"\bmonths?\s+of\s+['‘’\"]?$", re.IGNORECASE)
MONTH_CONTEXT_AFTER = re.compile(r"^['‘’\"]?\s+(?:month|maas|masa|mahina)\b", re.IGNORECASE)
REGIONAL_PREFIX = "month:"
SEASON_SURFACES: Mapping[str, str] = MappingProxyType(
    {word: season for season, words in SEASON_WORDS.items() for word in words}
)
SEASON_PATTERN = re.compile(
    r"(?<![\w-])(?:"
    + "|".join(re.escape(word) for word in sorted(SEASON_SURFACES, key=lambda word: (-len(word), word)))
    + r")(?!\w)",
    re.IGNORECASE,
)
REGIONAL_SURFACES: Mapping[str, str] = MappingProxyType(
    {name.casefold(): month for month, names in REGIONAL_MONTHS.items() for name in names}
)
REGIONAL_PATTERN = re.compile(
    r"(?<![\w-])(?:"
    + "|".join(re.escape(name) for name in sorted(REGIONAL_SURFACES, key=lambda name: (-len(name), name)))
    + r")(?![\w-])",
    re.IGNORECASE,
)
SPRING = "spring"
EXCLUDING_WORDS = POINT_WORDS | NEGATING_WORDS
NEGATION = "not"
CONTRACTED_NOT = "n't"
POINT_CLAUSE = re.compile(r"[,.;:!?]")
CLAUSE_TOKEN = re.compile(r"[\w'’]+")
BARE_ABBREVIATIONS = frozenset({"Jan", "Mar", "Dec"})
NAME_AFTER = re.compile(r"\s+[A-Z]")
MAPPING_WORDS_AFTER = 8
MAPPING_WORDS_BEFORE = 3
POINT_WORDS_BEFORE = 3
EXCLUDING_WORDS_BEFORE = 5


@dataclass(frozen=True)
class _Span:
    start: int
    end: int


@dataclass(frozen=True)
class _Mention(_Span):
    month: int


@dataclass(frozen=True)
class _Range(_Span):
    months: frozenset[int]


@dataclass(frozen=True)
class _NameMention(_Span):
    name: str


def months_named(texts: Iterable[str]) -> frozenset[int]:
    named: set[int] = set()
    for text in texts:
        mentions = _mentions(text)
        named |= {mention.month for mention in mentions}
        for found in _joined(text, mentions):
            named |= found.months
    return frozenset(named)


def year_months(texts: Iterable[str]) -> frozenset[int]:
    named: set[int] = set()
    for text in texts:
        named |= _timed_months(text, _undated(text))
    return frozenset(named)


def seasons_named(texts: Iterable[str]) -> frozenset[str]:
    return frozenset(mention.name for text in texts for mention in _season_mentions(text))


def first_season(texts: Iterable[str]) -> str | None:
    for text in texts:
        mentions = _season_mentions(text)
        if mentions:
            return mentions[0].name
    return None


def only_season(text: str) -> str | None:
    return _only_name(text, _season_mentions(text))


def regional_months_named(texts: Iterable[str]) -> frozenset[str]:
    named: set[str] = set()
    for text in texts:
        mapped = _calendar_months(text, _regional_mentions(text))
        named |= {_key(mention.name) for mention in _regional_in_context(text)}
        named |= {_key(name) for name in mapped}
    return frozenset(named)


def regional_month(text: str) -> str | None:
    found = _only_name(text, _regional_in_context(text))
    return _key(found) if found is not None else None


def season_months(text: str) -> dict[str, frozenset[int]]:
    return _calendar_months(text, _season_mentions(text))


def regional_month_months(text: str) -> dict[str, frozenset[int]]:
    return {_key(name): months for name, months in _calendar_months(text, _regional_mentions(text)).items()}


def _calendar_months(text: str, mentions: Sequence[_NameMention]) -> dict[str, frozenset[int]]:
    found = _NamedText(text, mentions)
    taken: dict[_NameMention, _Range] = {}
    for look in (found.after, found.before):
        for mention in found.mentions:
            span = None if mention in taken else look(mention)
            if span is not None and span not in taken.values():
                taken[mention] = span
    stated: dict[str, set[frozenset[int]]] = {}
    for mention, span in taken.items():
        stated.setdefault(mention.name, set()).add(span.months)
    return {name: next(iter(spans)) for name, spans in stated.items() if len(spans) == 1}


def _only_name(text: str, mentions: Sequence[_NameMention]) -> str | None:
    kept = [mention for mention in mentions if not _a_point(text, mention)]
    named = {mention.name for mention in kept}
    if len(named) != 1 or any(_negated(text, mention.start) for mention in kept):
        return None
    return next(iter(named))


def _key(name: str) -> str:
    return name.removeprefix(REGIONAL_PREFIX)


def _mentions(text: str) -> list[_Mention]:
    return [
        _Mention(match.start(), match.end(), _month_number(match.group(1)))
        for match in MONTH.finditer(text)
        if not _modal_may(text, match) and not _a_name(text, match)
    ]


def _undated(text: str) -> list[_Mention]:
    return [
        mention
        for mention in _mentions(text)
        if not DAY_OR_YEAR_AFTER.match(text[mention.end :]) and not DAY_BEFORE.search(text[: mention.start])
    ]


def _timed_months(text: str, mentions: Sequence[_Mention]) -> set[int]:
    ranges = _joined(text, mentions)
    months: set[int] = set()
    for span in ranges:
        if not _excluded(text, span.start):
            months |= span.months
    for mention in mentions:
        ranged = any(span.start <= mention.start < span.end for span in ranges)
        if not ranged and not _excluded(text, mention.start):
            months.add(mention.month)
    return months


def _excluded(text: str, start: int) -> bool:
    return bool(EXCLUDING_WORDS.intersection(_clause_words(text, start, EXCLUDING_WORDS_BEFORE)))


def _negated(text: str, start: int) -> bool:
    return bool(NEGATING_WORDS.intersection(_clause_words(text, start, EXCLUDING_WORDS_BEFORE)))


def _a_point(text: str, mention: _Span) -> bool:
    return bool(POINT_WORDS.intersection(_clause_words(text, mention.start, POINT_WORDS_BEFORE)))


def _clause_words(text: str, start: int, most: int) -> list[str]:
    clause = POINT_CLAUSE.split(text[:start])[-1]
    words = [_clause_word(token) for token in CLAUSE_TOKEN.findall(clause)]
    joined = [
        EXCLUDING_BIGRAMS.get((before, word), word) for before, word in zip(["", *words], words, strict=False)
    ]
    return joined[-most:]


def _clause_word(token: str) -> str:
    folded = token.casefold().replace("’", "'")
    return NEGATION if folded.endswith(CONTRACTED_NOT) else folded


def _ranges(text: str) -> list[_Range]:
    return _joined(text, _undated(text))


def _joined(text: str, mentions: Sequence[_Mention]) -> list[_Range]:
    found: list[_Range] = []
    for first, last in pairwise(mentions):
        months = _joined_months(text, first, last)
        if months:
            found.append(_Range(first.start, last.end, frozenset(months)))
    return found


def _joined_months(text: str, first: _Mention, last: _Mention) -> set[int]:
    gap = text[first.end : last.start]
    if RANGE_JOIN.match(gap):
        return _months_between(first.month, last.month)
    if not PAIR_JOIN.match(gap):
        return set()
    if BETWEEN_BEFORE.search(text[: first.start]):
        return _months_between(first.month, last.month)
    return {first.month, last.month} if last.month == first.month % MONTHS + 1 else set()


def _season_mentions(text: str) -> list[_NameMention]:
    return [
        _NameMention(match.start(), match.end(), SEASON_SURFACES[match.group(0).casefold()])
        for match in SEASON_PATTERN.finditer(text)
        if not DATED_AFTER.match(text[match.end() :]) and _a_season(text, match)
    ]


def _a_season(text: str, match: re.Match[str]) -> bool:
    if match.group(0).casefold() != SPRING:
        return True
    before = WORD.findall(text[: match.start()])
    after = WORD.findall(text[match.end() :])
    opens = not before or SENTENCE_START.search(text[: match.start()]) is not None
    led = (
        opens or before[-1].casefold() in SPRING_WORDS_BEFORE or text[: match.start()].rstrip().endswith(",")
    )
    return led and not (after and after[0].casefold() in SPRING_WORDS_AFTER_REFUSED)


def _regional_mentions(text: str) -> list[_NameMention]:
    return [
        _NameMention(
            match.start(), match.end(), REGIONAL_PREFIX + REGIONAL_SURFACES[match.group(0).casefold()]
        )
        for match in REGIONAL_PATTERN.finditer(text)
    ]


def _regional_in_context(text: str) -> list[_NameMention]:
    return [
        mention
        for mention in _regional_mentions(text)
        if MONTH_CONTEXT_BEFORE.search(text[: mention.start])
        or MONTH_CONTEXT_AFTER.match(text[mention.end :])
    ]


class _NamedText:
    def __init__(self, text: str, mentions: Sequence[_NameMention]) -> None:
        self.text = text
        self.ranges = _ranges(text)
        self.mentions = list(mentions)

    def after(self, mention: _NameMention) -> _Range | None:
        span = next((span for span in self.ranges if span.start >= mention.end), None)
        if span is None or _a_point(self.text, mention):
            return None
        gap = _Span(mention.end, span.start)
        return span if self._joins(gap, SPAN_WORDS_AFTER, MAPPING_WORDS_AFTER) else None

    def before(self, mention: _NameMention) -> _Range | None:
        span = next((span for span in reversed(self.ranges) if span.end <= mention.start), None)
        if span is None or _a_point(self.text, mention):
            return None
        gap = _Span(span.end, mention.start)
        return span if self._joins(gap, SPAN_WORDS_BEFORE, MAPPING_WORDS_BEFORE) else None

    def _joins(self, gap: _Span, allowed: frozenset[str], most_words: int) -> bool:
        between = self.text[gap.start : gap.end]
        words = [word.casefold() for word in WORD.findall(between)]
        if CLAUSE_BREAK.search(between) or len(words) > most_words:
            return False
        if any(word not in allowed and not any(c.isdigit() for c in word) for word in words):
            return False
        return not any(gap.start <= other.start < gap.end for other in self.mentions)


def _month_number(name: str) -> int:
    short = "Sep" if name == "Sept" else name[:3]
    return next(index for index, month in enumerate(MONTH_NAMES, 1) if month.startswith(short))


def _a_name(text: str, match: re.Match[str]) -> bool:
    return match.group(0) in BARE_ABBREVIATIONS and NAME_AFTER.match(text, match.end()) is not None


def _modal_may(text: str, match: re.Match[str]) -> bool:
    return match.group(1) == AMBIGUOUS_MONTH and SENTENCE_START.search(text[: match.start()]) is not None


def _months_between(first: int, last: int) -> set[int]:
    span = (last - first) % MONTHS
    return {(first - 1 + step) % MONTHS + 1 for step in range(span + 1)}
