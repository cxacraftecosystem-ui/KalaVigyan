from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from functools import lru_cache
from types import MappingProxyType

from .local_units import LOCAL_UNITS
from .measures import DEFINED_UNITS
from .unit_registry import measures_alike, metric_unit_named

__all__ = [
    "NUMBER_PATTERN",
    "UNIT_WORDS",
    "StatedFactor",
    "StatedQuantity",
    "stated_decimal",
    "stated_factors",
    "stated_quantities",
]

NUMBER_PATTERN = r"\d+(?:[.,]\d+)*"
RANGE_JOIN = r"\s*(?:-|–|—|to)\s*"
APPROXIMATELY = r"(?:(?i:about|approximately|roughly|nearly|around|almost|some|c\.)\s*)?"
EQUALS = (
    r"(?:=|(?i:(?:is|was|were|being)(?:\s+(?:equal|equivalent)\s+to)?|equals?|equalled|equaled|"
    r"weigh(?:s|ed)?|measur(?:es|ed)|amounts?\s+to|comes?\s+to|came\s+to))"
)
SINGLE = r"(?i:a|an|one|1|each)"
BETWEEN = r"(?:\s+(?:(?i:of|in|the|local|standard|old)|[A-Z][\w-]*))*"
METRIC_WORD = r"(?:(?i:square|sq\.?)\s+)?[A-Za-z]+\.?"
WORD_END = r"(?![^\W\d_])"


@dataclass(frozen=True)
class StatedQuantity:
    stated: str
    low: Decimal
    high: Decimal | None
    unit_label: str
    unit: str


@dataclass(frozen=True)
class StatedFactor:
    unit: str
    factor: Decimal
    metric_unit: str
    stated: str


UNIT_WORDS: Mapping[str, str] = MappingProxyType(
    {
        word.casefold(): key
        for table in (DEFINED_UNITS, LOCAL_UNITS)
        for key, unit in table.items()
        for word in unit.words
    }
)


def stated_quantities(text: str) -> list[StatedQuantity]:
    found: dict[str, StatedQuantity] = {}
    for match in _quantity_pattern().finditer(text):
        low, high = stated_decimal(match.group("low")), stated_decimal(match.group("high"))
        if low is None or low <= 0 or (match.group("high") and (high is None or high <= low)):
            continue
        label = match.group("unit")
        unit = UNIT_WORDS[_folded_word(label)]
        stated = match.group(0)
        found.setdefault(stated.casefold(), StatedQuantity(stated, low, high, label, unit))
    return list(found.values())


def stated_factors(text: str) -> list[StatedFactor]:
    found: list[StatedFactor] = []
    for match in _factor_matches(text):
        unit = UNIT_WORDS[_folded_word(match.group("unit"))]
        factor = stated_decimal(match.group("factor"))
        metric = metric_unit_named(match.group("metric"))
        if unit not in LOCAL_UNITS or factor is None or factor <= 0 or metric is None:
            continue
        if measures_alike(unit, metric):
            found.append(StatedFactor(unit, factor, metric, match.group(0)))
    return found


def _factor_matches(text: str) -> Iterable[re.Match[str]]:
    forward, backward = _factor_patterns()
    yield from forward.finditer(text)
    yield from backward.finditer(text)


def stated_decimal(figure: str | None) -> Decimal | None:
    if figure is None:
        return None
    try:
        return Decimal(figure.replace(",", ""))
    except InvalidOperation:
        return None


def _folded_word(label: str) -> str:
    return " ".join(label.casefold().split())


def _word_pattern(words: Iterable[str]) -> str:
    ordered = sorted(set(words), key=lambda word: (-len(word), word))
    return "(?i:" + "|".join(r"\s+".join(map(re.escape, word.split())) for word in ordered) + ")"


@lru_cache(maxsize=1)
def _quantity_pattern() -> re.Pattern[str]:
    units = _word_pattern(UNIT_WORDS)
    return re.compile(
        rf"(?<![\w.,])(?P<low>{NUMBER_PATTERN})(?:{RANGE_JOIN}(?P<high>{NUMBER_PATTERN}))?"
        rf"(?:\s*-\s*|\s*)(?P<unit>{units}){WORD_END}"
    )


@lru_cache(maxsize=1)
def _factor_patterns() -> tuple[re.Pattern[str], re.Pattern[str]]:
    local = _word_pattern(word for word, key in UNIT_WORDS.items() if key in LOCAL_UNITS)
    forward = re.compile(
        rf"(?<![\w]){SINGLE}\s+(?P<unit>{local}){WORD_END}{BETWEEN}\s*{EQUALS}\s*{APPROXIMATELY}"
        rf"(?P<factor>{NUMBER_PATTERN})\s*(?P<metric>{METRIC_WORD}){WORD_END}"
    )
    backward = re.compile(
        rf"(?<![\w.,])(?P<factor>{NUMBER_PATTERN})\s*(?P<metric>{METRIC_WORD})\s*"
        rf"(?:=|(?i:make|makes|made|to|in))\s+{SINGLE}\s+(?P<unit>{local}){WORD_END}"
    )
    return forward, backward
