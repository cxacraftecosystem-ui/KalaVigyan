from __future__ import annotations

import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass

from .terms import TERM_LABEL_MAX_CHARS, TermSpan

__all__ = ["SURFACE_MIN_CHARS", "WORD_CHARS", "GlossaryEntry", "TermMarker"]

SURFACE_MIN_CHARS = 2
WORD_CHARS = r"\w\u064B-\u065F\u0670\u0900-\u0963\u0966-\u0D7F"


@dataclass(frozen=True)
class GlossaryEntry:
    key: str
    surfaces: tuple[str, ...]


class TermMarker:
    def __init__(self, glossary: Sequence[GlossaryEntry]) -> None:
        self._keys = _surface_keys(glossary)
        ordered = sorted(self._keys, key=lambda surface: (-len(surface), surface))
        alternatives = "|".join(re.escape(surface) for surface in ordered)
        bounded = rf"(?<![{WORD_CHARS}])(?:{alternatives})(?![{WORD_CHARS}])"
        self._pattern = re.compile(bounded, re.IGNORECASE) if ordered else None

    def spans(self, text: str) -> list[TermSpan]:
        if self._pattern is None:
            return []
        spans: list[TermSpan] = []
        marked: set[str] = set()
        for match in self._pattern.finditer(text):
            shown = match.group()
            key = self._keys.get(_folded(shown))
            if key is None or key in marked or text.find(shown) != match.start():
                continue
            marked.add(key)
            spans.append(TermSpan(text=shown, term_key=key))
        return spans


def _surface_keys(glossary: Iterable[GlossaryEntry]) -> dict[str, str]:
    keys: dict[str, str] = {}
    shared: set[str] = set()
    for entry in glossary:
        for surface in {_folded(s) for s in entry.surfaces}:
            if not SURFACE_MIN_CHARS <= len(surface) <= TERM_LABEL_MAX_CHARS:
                continue
            if keys.setdefault(surface, entry.key) != entry.key:
                shared.add(surface)
    return {surface: key for surface, key in keys.items() if surface not in shared}


def _folded(text: str) -> str:
    return " ".join(text.split()).casefold()
