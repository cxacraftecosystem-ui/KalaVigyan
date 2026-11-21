from __future__ import annotations

import re
from collections.abc import Sequence

from .quotes import normalise_quote_text

__all__ = [
    "APPROXIMATE_FIGURE",
    "ENGLISH_APPROXIMATION",
    "ENGLISH_HEDGE",
    "HINDI_APPROXIMATION",
    "HINDI_DOUBT",
    "QUOTE_IGNORED_MODALS",
    "doubt_words",
    "dropped_doubt",
    "dropped_hedges",
    "hedged",
    "hedges_in",
    "quote_hedges",
    "unsourced_hedges",
]

ENGLISH_HEDGE = re.compile(
    r"\b(?:may|might|could|possibly|probably|perhaps|likely|in all likelihood|reportedly|allegedly|apparently"
    r"|presumably|supposedly|purportedly|seemingly|believed|said to|thought to)\b",
    re.IGNORECASE,
)
ENGLISH_APPROXIMATION = re.compile(
    r"\b(?:about|approximately|approx|around|nearly|almost|roughly|circa|estimated|some)\b", re.IGNORECASE
)
APPROXIMATE_FIGURE = re.compile(ENGLISH_APPROXIMATION.pattern + r"\s+\d", re.IGNORECASE)
QUOTE_IGNORED_MODALS = frozenset({"may", "might", "could"})
MONTH_MAY = "May"
DEVANAGARI_WORD = r"\w\u0900-\u0963\u0966-\u097f"
IS = r"(?:है|हैं|था|थी|थे)"
THAT = r",? क(?:ि|ी)"
SAID = rf"(?:कह(?:ा|ी|े)|मान(?:ा|ी|े)|बता(?:या|यी|ई|ये|ए)) जात(?:ा|ी|े) {IS}"
NUKTA = "\u093c"


def _hindi(*phrases: str) -> re.Pattern[str]:
    return re.compile(rf"(?<![{DEVANAGARI_WORD}])(?:{'|'.join(phrases)})(?![{DEVANAGARI_WORD}])")


HINDI_DOUBT = _hindi(
    "शायद",
    r"स(?:ं|म्)भवत(?:ः|:|या)?",
    rf"स(?:ं|म्)भव {IS}{THAT}",
    rf"{SAID}{THAT}",
    rf"ऐसा {SAID}",
    rf"मान्यता {IS}{THAT}",
    "ऐसी मान्यता",
    rf"हो सकत(?:ा|ी|े) {IS}{THAT}",
    r"प्रतीत हो(?:ता|ती|ते)",
)
HINDI_APPROXIMATION = _hindi(
    "लगभग",
    rf"क{NUKTA}?रीब(?:[- ]क{NUKTA}?रीब|(?=\s*\d))",
    rf"तक{NUKTA}?रीबन",
    r"अनुमानत(?:ः|:)?",
    "अनुमानित",
)


def unsourced_hedges(text: str, quotes: Sequence[str]) -> list[str]:
    if any(_found(HINDI_DOUBT, quote) for quote in quotes):
        return []
    stated = {hedge for quote in quotes for hedge in _english_hedges(quote)}
    return [hedge for hedge in dict.fromkeys(_english_hedges(text)) if hedge not in stated]


def dropped_hedges(text: str, quotes: Sequence[str]) -> list[str]:
    return _dropped(text, [quote_hedges(quote) for quote in quotes])


def dropped_doubt(text: str, quotes: Sequence[str]) -> list[str]:
    return _dropped(text, [doubt_words(quote) for quote in quotes])


def hedged(text: str) -> bool:
    return bool(_english_hedges(text)) or ENGLISH_APPROXIMATION.search(text) is not None


def quote_hedges(quote: str) -> list[str]:
    english = [hedge for hedge in _english_hedges(quote) if hedge not in QUOTE_IGNORED_MODALS]
    return [*english, *_found(HINDI_DOUBT, quote), *_found(HINDI_APPROXIMATION, quote)]


def doubt_words(text: str) -> list[str]:
    english = [
        found.group().casefold() for found in ENGLISH_HEDGE.finditer(text) if found.group() != MONTH_MAY
    ]
    return [*english, *_found(HINDI_DOUBT, text), *_found(HINDI_APPROXIMATION, text)]


def hedges_in(text: str) -> list[str]:
    approximations = [found.group().split()[0].casefold() for found in APPROXIMATE_FIGURE.finditer(text)]
    return list(dict.fromkeys([*doubt_words(text), *approximations]))


def _dropped(text: str, found: Sequence[Sequence[str]]) -> list[str]:
    if not found or not all(found) or hedged(text):
        return []
    return list(dict.fromkeys(word for words in found for word in words))


def _english_hedges(text: str) -> list[str]:
    return [
        found.group().casefold()
        for found in ENGLISH_HEDGE.finditer(text)
        if not (found.group() == MONTH_MAY and found.start() > 0)
    ]


def _found(pattern: re.Pattern[str], text: str) -> list[str]:
    return [found.group() for found in pattern.finditer(normalise_quote_text(text))]
