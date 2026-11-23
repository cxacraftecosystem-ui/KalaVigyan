from __future__ import annotations

import re
from collections.abc import Iterable, Iterator
from types import MappingProxyType

from .quotes import fold_digits, normalise_quote_text, quote_occurs

__all__ = [
    "CENTURY_WORDS",
    "MOVEMENT_WORDS",
    "YEAR_MAX",
    "YEAR_MIN",
    "YearSpan",
    "states_movement",
    "years_named",
    "years_offered",
    "years_stated",
]

YEAR_MIN = 1000
YEAR_MAX = 2099
YEARS_PER_CENTURY = 100
YEARS_PER_DECADE = 10
CENTURY_WORDS = MappingProxyType(
    {
        "first": 1,
        "second": 2,
        "third": 3,
        "fourth": 4,
        "fifth": 5,
        "sixth": 6,
        "seventh": 7,
        "eighth": 8,
        "ninth": 9,
        "tenth": 10,
        "eleventh": 11,
        "twelfth": 12,
        "thirteenth": 13,
        "fourteenth": 14,
        "fifteenth": 15,
        "sixteenth": 16,
        "seventeenth": 17,
        "eighteenth": 18,
        "nineteenth": 19,
        "twentieth": 20,
        "twenty-first": 21,
    }
)
MOVEMENT_WORDS = frozenset(
    {
        "arrive",
        "arrived",
        "brought",
        "came",
        "carried",
        "come",
        "exported",
        "fled",
        "imported",
        "invited",
        "migrate",
        "migrated",
        "migration",
        "move",
        "moved",
        "relocate",
        "relocated",
        "sent",
        "settle",
        "settled",
        "shipped",
        "trade",
        "traded",
        "travelled",
        "went",
    }
)

YearSpan = tuple[int, int]

BEFORE_COMMON_ERA = r"(?!\s*(?:B\.?C\.?E?\b|BCE\b))"
YEAR = r"(?<![\d.,])(1\d{3}|20\d{2})(?![\d])"
RANGE = re.compile(
    YEAR + r"\s*(?:-|to)\s*(?:(?:ca|c)\.\s*|circa\s+)?(\d{4}|\d{2})(?![\d])" + BEFORE_COMMON_ERA
)
SINGLE = re.compile(YEAR + r"(?!s\b)" + BEFORE_COMMON_ERA)
DECADE = re.compile(r"(?<![\d.,])(1\d{2}0|20\d0)s\b")
ORDINAL_WORDS = "|".join(sorted(CENTURY_WORDS, key=len, reverse=True))
ORDINAL = rf"(?:\d{{1,2}}(?:st|nd|rd|th)|(?:{ORDINAL_WORDS}))"
ORDINAL_JOIN = r"(?:\s*[-,]\s*(?:(?:and|or)\s+)?|\s+(?:to|and|or)\s+)(?:the\s+)?(?:(?:early|late|mid)[\s-]+)?"
CENTURY = re.compile(
    rf"(?<!\w){ORDINAL}(?:{ORDINAL_JOIN}{ORDINAL})*[\s-]+centur(?:y|ies)\b{BEFORE_COMMON_ERA}", re.IGNORECASE
)
CENTURY_ORDINAL = re.compile(rf"(?<!\w)(?:(\d{{1,2}})(?:st|nd|rd|th)|({ORDINAL_WORDS}))(?!\w)", re.IGNORECASE)
MEASURED = re.compile(
    r"(?<![\w.,])\d[\d,.]*(?:\s*(?:-|to)\s*\d[\d,.]*)?\s*"
    r"(?:°|º|degrees?\b|(?:hundred|thousand|million|billion)\b|(?:lakh|crore)s?\b)",
    re.IGNORECASE,
)
PRICED = re.compile(r"(?:₹|\brs\b\.?|\binr\b)\s*\d[\d,.]*", re.IGNORECASE)
WORD = re.compile(r"[^\W\d_]+")
COUNTED = re.compile(r"\s+([a-z]{2,})\b")
PLURAL_MIN_CHARS = 3
IRREGULAR_COUNTED = frozenset(
    {"cattle", "children", "feet", "folk", "geese", "men", "people", "sheep", "teeth", "women", "workmen"}
)
NOT_COUNTED = frozenset(
    {
        "across",
        "as",
        "dozens",
        "has",
        "his",
        "hundreds",
        "is",
        "its",
        "less",
        "millions",
        "plus",
        "this",
        "thousands",
        "thus",
        "unless",
        "was",
        "whereas",
    }
)


def years_named(texts: Iterable[str]) -> set[YearSpan]:
    return set(years_stated(texts))


def years_stated(texts: Iterable[str]) -> dict[YearSpan, str]:
    stated: dict[YearSpan, str] = {}
    for text in texts:
        plain = fold_digits(normalise_quote_text(text))
        for span, phrase in (*_ranges(plain), *_singles(plain), *_decades(plain), *_centuries(plain)):
            stated.setdefault(span, phrase)
    return stated


def years_offered(texts: Iterable[str]) -> set[YearSpan]:
    plain = [_unmeasured(fold_digits(normalise_quote_text(text))) for text in texts]
    dated = {year for text in plain for year in _dated_singles(text)}
    return {span for span in years_named(plain) if span[0] != span[1] or span[0] in dated}


def states_movement(texts: Iterable[str], start: str, end: str) -> bool:
    for text in texts:
        folded = text.casefold()
        moves = set(WORD.findall(folded)) & MOVEMENT_WORDS
        if (
            moves
            and quote_occurs(f"from {start.casefold()}", folded)
            and quote_occurs(end.casefold(), folded)
        ):
            return True
    return False


def _ranges(text: str) -> Iterator[tuple[YearSpan, str]]:
    for match in RANGE.finditer(text):
        start, tail = int(match.group(1)), match.group(2)
        end = int(tail) if len(tail) == 4 else start - start % YEARS_PER_CENTURY + int(tail)
        if start <= end <= YEAR_MAX:
            yield (start, end), match.group(0)


def _singles(text: str) -> Iterator[tuple[YearSpan, str]]:
    for match in SINGLE.finditer(text):
        year = int(match.group(1))
        if YEAR_MIN <= year <= YEAR_MAX:
            yield (year, year), match.group(1)


def _dated_singles(text: str) -> Iterator[int]:
    for match in SINGLE.finditer(text):
        counted = COUNTED.match(text, match.end())
        if counted is None or not _counts(counted.group(1)):
            yield int(match.group(1))


def _counts(word: str) -> bool:
    if word in IRREGULAR_COUNTED:
        return True
    return len(word) >= PLURAL_MIN_CHARS and word.endswith("s") and word not in NOT_COUNTED


def _decades(text: str) -> Iterator[tuple[YearSpan, str]]:
    for match in DECADE.finditer(text):
        start = int(match.group(1))
        yield (start, start + YEARS_PER_DECADE - 1), match.group(0)


def _unmeasured(text: str) -> str:
    return PRICED.sub(" ", MEASURED.sub(" ", text))


def _centuries(text: str) -> Iterator[tuple[YearSpan, str]]:
    for match in CENTURY.finditer(text):
        named = [_century(*found.groups()) for found in CENTURY_ORDINAL.finditer(match.group())]
        centuries = [century for century in named if century]
        if centuries and len(centuries) == len(named) and centuries == sorted(centuries):
            span = ((centuries[0] - 1) * YEARS_PER_CENTURY + 1, centuries[-1] * YEARS_PER_CENTURY)
            yield span, match.group(0)


def _century(digits: str | None, word: str | None) -> int | None:
    if digits:
        return int(digits) or None
    if word:
        return CENTURY_WORDS[word.casefold()]
    return None
