from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType

from app.research.stream import StatusStep
from app.research.vocabulary import ANSWER_LANGUAGE_SPECS, CANONICAL_LANGUAGE

from .interface_words import ENGLISH_WORDS, InterfaceWords

__all__ = ["STATUS_WORDS_KEY", "status_line", "status_message"]

STATUS_WORDS_KEY = "stream.status"
PLANNING = "Planning the research"
PLANNING_ON = "Planning the research on {craft}"
PLAIN_LINES: Mapping[str, str] = MappingProxyType(
    {"SEARCHING_STORED": "Searching stored findings", "TRANSLATING": "Translating the answer into {language}"}
)
COUNTED_LINES: Mapping[str, tuple[str, str]] = MappingProxyType(
    {
        "RESEARCHING": ("Searching {count} live query", "Searching {count} live queries"),
        "READING": ("Reading the best of {count} source found", "Reading the best of {count} sources found"),
        "COMPOSING": (
            "Writing a cited answer from {count} passage",
            "Writing a cited answer from {count} passages",
        ),
        "WRITING_BACK": (
            "Saving {count} source for the next question",
            "Saving {count} sources for the next question",
        ),
    }
)


def status_line(step: StatusStep, count: int = 0, craft: str = "") -> str:
    if step == "PLANNING":
        return PLANNING_ON if craft else PLANNING
    if step in COUNTED_LINES:
        one, other = COUNTED_LINES[step]
        return one if count == 1 else other
    return PLAIN_LINES[step]


def status_message(
    step: StatusStep,
    count: int = 0,
    craft: str = "",
    *,
    language: str = CANONICAL_LANGUAGE,
    words: InterfaceWords = ENGLISH_WORDS,
) -> str:
    english = status_line(step, count, craft)
    spec = ANSWER_LANGUAGE_SPECS[language]
    shown = words.shown(STATUS_WORDS_KEY, english)
    if shown is None:
        return english.format(count=count, craft=craft, language=spec.label)
    return shown.format(count=count, craft=craft, language=spec.autonym)
