from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any

from app.data.interface_words import WordEntry, load_interface_words
from app.research.vocabulary import CANONICAL_LANGUAGE, answer_language_options

__all__ = [
    "ENGLISH_WORDS",
    "ESSAY_WORDS_PREFIX",
    "InterfaceWords",
    "essay_words",
    "language_options_with_words",
    "reviewed_of",
    "reviewed_words",
    "written_words",
]

ESSAY_WORDS_PREFIX = "essay."


@dataclass(frozen=True)
class InterfaceWords:
    language: str
    entries: Mapping[tuple[str, str], WordEntry] = field(default_factory=lambda: MappingProxyType({}))

    def shown(self, key: str, english: str) -> str | None:
        entry = self.entries.get((key, english))
        return entry.text if entry is not None else None

    def said(self, key: str, english: str, **values: object) -> str:
        return (self.shown(key, english) or english).format(**values)


ENGLISH_WORDS = InterfaceWords(CANONICAL_LANGUAGE)


def reviewed_of(language: str, entries: Iterable[WordEntry]) -> InterfaceWords:
    reviewed = {(entry.key, entry.english): entry for entry in entries if entry.review is not None}
    return InterfaceWords(language, MappingProxyType(reviewed))


def reviewed_words(language: str) -> InterfaceWords:
    return reviewed_of(language, load_interface_words().get(language, ()))


def written_words(language: str) -> InterfaceWords:
    entries = load_interface_words().get(language, ())
    return InterfaceWords(
        language, MappingProxyType({(entry.key, entry.english): entry for entry in entries})
    )


def essay_words(language: str) -> list[dict[str, str]]:
    return [
        {"key": entry.key, "english": entry.english, "text": entry.text}
        for entry in reviewed_words(language).entries.values()
        if entry.key.startswith(ESSAY_WORDS_PREFIX)
    ]


def language_options_with_words() -> list[dict[str, Any]]:
    return [_with_words(option) for option in answer_language_options()]


def _with_words(option: dict[str, Any]) -> dict[str, Any]:
    words = essay_words(option["code"])
    return {**option, "words": words} if words else option
