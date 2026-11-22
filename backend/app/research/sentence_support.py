from __future__ import annotations

import re
from collections.abc import Iterable, Mapping, Sequence
from types import MappingProxyType

from .evidence import personal_data_in
from .gate_thrift import NEGATION
from .hedges import dropped_doubt
from .quotes import content_stems, figures_in, fold_digits, normalise_quote_text
from .translation import NUMBER_UNITS, SYMBOL_UNITS

__all__ = [
    "NEGATION_CHANGED",
    "NUMBER_WORD_VALUES",
    "SCREEN_KINDS",
    "SPAN_SHARED_MIN",
    "STANCE_KINDS",
    "SupportGap",
    "figure_units",
    "negation_count",
    "negation_gap",
    "number_words_in",
    "screen_gaps",
    "stance_gaps",
    "unrelated_refs",
]

SPAN_SHARED_MIN = 2
NEGATION_CHANGED = "NEGATION_CHANGED"
STANCE_KINDS = (NEGATION_CHANGED, "NUMBER_WORD", "UNIT_CHANGED", "DROPPED_HEDGE")
SCREEN_KINDS = ("LINK_OR_MARKUP", "PERSONAL_DATA")
NUMBER_WORD_VALUES: Mapping[str, float] = MappingProxyType(
    {
        "zero": 0,
        "one": 1,
        "single": 1,
        "two": 2,
        "twice": 2,
        "double": 2,
        "pair": 2,
        "three": 3,
        "thrice": 3,
        "triple": 3,
        "four": 4,
        "five": 5,
        "six": 6,
        "seven": 7,
        "eight": 8,
        "nine": 9,
        "ten": 10,
        "eleven": 11,
        "twelve": 12,
        "dozen": 12,
        "dozens": 12,
        "thirteen": 13,
        "fourteen": 14,
        "fifteen": 15,
        "sixteen": 16,
        "seventeen": 17,
        "eighteen": 18,
        "nineteen": 19,
        "twenty": 20,
        "thirty": 30,
        "forty": 40,
        "fifty": 50,
        "sixty": 60,
        "seventy": 70,
        "eighty": 80,
        "ninety": 90,
        "hundred": 100,
        "hundreds": 100,
        "thousand": 1000,
        "thousands": 1000,
        "million": 1000000,
        "millions": 1000000,
        "half": 0.5,
    }
)
NUMERAL_ONE = (
    r"(?<!\bno )(?<!\beach )(?<!\bevery )(?<!\bany )(?<!\bthe )(?<!\bthis )(?<!\bthat )(?<!\bwhich )"
    r"\bone\b(?! another\b)(?! of\b)"
)
NUMBER_WORD = re.compile(
    r"\b(?:"
    + "|".join(sorted((word for word in NUMBER_WORD_VALUES if word != "one"), key=len, reverse=True))
    + r")\b|"
    + NUMERAL_ONE,
    re.IGNORECASE,
)
UNIT_NAMES = sorted({*SYMBOL_UNITS, *NUMBER_UNITS}, key=lambda unit: (-len(unit), unit))
FIGURE_UNIT = re.compile(
    r"(?<![\d.,])(\d+(?:[.,]\d+)*)\s?(" + "|".join(re.escape(unit) for unit in UNIT_NAMES) + r")(?![^\W\d_])"
)
LINK = re.compile(
    r"https?:|www\.|(?<![\w@.-])[a-z0-9-]+(?:\.[a-z0-9-]+)*\.(?:com|org|net|in|shop|store|info|biz)(?![\w-])"
)
MARKUP = re.compile(r"</?[A-Za-z!]|\]\(")

SupportGap = tuple[str, str]


def stance_gaps(text: str, quotes: Sequence[str]) -> list[SupportGap]:
    gaps: list[SupportGap] = []
    negation = negation_gap(text, quotes)
    if negation is not None:
        gaps.append((NEGATION_CHANGED, negation))
    gaps += [("NUMBER_WORD", word) for word in _unheld_number_words(text, quotes)]
    gaps += [("UNIT_CHANGED", figure) for figure in _changed_units(text, quotes)]
    gaps += [("DROPPED_HEDGE", hedge) for hedge in dropped_doubt(text, quotes)]
    return gaps


def screen_gaps(text: str) -> list[SupportGap]:
    folded = normalise_quote_text(text)
    gaps: list[SupportGap] = []
    if LINK.search(folded) or MARKUP.search(folded):
        gaps.append(("LINK_OR_MARKUP", "the sentence carries a link or markup"))
    gaps += [("PERSONAL_DATA", label) for label in personal_data_in(folded)]
    return gaps


def unrelated_refs(text: str, spans: Mapping[str, Sequence[str]]) -> list[str]:
    if len(spans) < 2:
        return []
    said = _support_items(text)
    return [ref for ref, quotes in spans.items() if not any(_relates(quote, said) for quote in quotes)]


def negation_count(text: str) -> int:
    return len(NEGATION.findall(normalise_quote_text(text)))


def number_words_in(text: str) -> list[str]:
    return [found.group().casefold() for found in NUMBER_WORD.finditer(normalise_quote_text(text))]


def negation_gap(text: str, quotes: Sequence[str]) -> str | None:
    counts = [negation_count(quote) for quote in quotes]
    said = negation_count(text)
    if not counts or max(counts) <= said <= sum(counts):
        return None
    return f"the sentence holds {said} negation(s) where its quotes hold {max(counts)} to {sum(counts)}"


def figure_units(text: str) -> list[tuple[str, str]]:
    folded = fold_digits(normalise_quote_text(text))
    return [(found.group(1).replace(",", ""), found.group(2)) for found in FIGURE_UNIT.finditer(folded)]


def _unheld_number_words(text: str, quotes: Sequence[str]) -> list[str]:
    held_words = {word for quote in quotes for word in number_words_in(quote)}
    held_values = {NUMBER_WORD_VALUES[word] for word in held_words}
    held_figures = {figure for quote in quotes for figure in figures_in(quote)}
    return [
        word
        for word in dict.fromkeys(number_words_in(text))
        if word not in held_words
        and NUMBER_WORD_VALUES[word] not in held_values
        and _figure(NUMBER_WORD_VALUES[word]) not in held_figures
    ]


def _changed_units(text: str, quotes: Iterable[str]) -> list[str]:
    held: dict[str, set[str]] = {}
    for quote in quotes:
        for number, unit in figure_units(quote):
            held.setdefault(number, set()).add(unit.casefold())
    return [
        f"{number} {unit}"
        for number, unit in dict.fromkeys(figure_units(text))
        if number in held and unit.casefold() not in held[number]
    ]


def _support_items(text: str) -> set[str]:
    return content_stems(text) | set(figures_in(text))


def _relates(quote: str, said: set[str]) -> bool:
    own = _support_items(quote)
    return len(own & said) >= max(1, min(SPAN_SHARED_MIN, len(own)))


def _figure(value: float) -> str:
    return str(int(value)) if value == int(value) else str(value)
