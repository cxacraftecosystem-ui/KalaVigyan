from __future__ import annotations

import unicodedata

from .gate_thrift import NEGATION
from .hedges import HINDI_APPROXIMATION, HINDI_DOUBT, hedged
from .quotes import normalise_quote_text
from .stance_marker_words import HEDGE_MARKERS, JOINERS, NEGATION_MARKERS, Markers

__all__ = ["hedge_marked", "negation_marked"]


def negation_marked(text: str, language: str) -> bool:
    if language not in NEGATION_MARKERS:
        return NEGATION.search(normalise_quote_text(text)) is not None
    return _carries(text, NEGATION_MARKERS[language])


def hedge_marked(text: str, language: str) -> bool:
    if language not in HEDGE_MARKERS:
        return hedged(text)
    folded = normalise_quote_text(text)
    if language == "hi" and (HINDI_DOUBT.search(folded) or HINDI_APPROXIMATION.search(folded)):
        return True
    return _carries(text, HEDGE_MARKERS[language])


def _carries(text: str, markers: Markers) -> bool:
    words = _words(text)
    joined = f" {' '.join(words)} "
    phrases = [marker for marker in markers.words if " " in marker]
    if markers.words & set(words) or any(f" {phrase} " in joined for phrase in phrases):
        return True
    return any(
        word.endswith(ending) and len(word) > len(ending) and word not in markers.unmarked
        for word in words
        for ending in markers.endings
    )


def _words(text: str) -> list[str]:
    stripped = (_bare(word) for word in normalise_quote_text(text).translate(JOINERS).split())
    return [word for word in stripped if word]


def _bare(word: str) -> str:
    start, end = 0, len(word)
    while start < end and unicodedata.category(word[start]).startswith(("P", "S")):
        start += 1
    while end > start and unicodedata.category(word[end - 1]).startswith(("P", "S")):
        end -= 1
    return word[start:end]
