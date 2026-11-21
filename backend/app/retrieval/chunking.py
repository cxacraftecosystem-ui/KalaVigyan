from __future__ import annotations

import re
from dataclasses import dataclass
from itertools import pairwise

from app.core.errors import InvalidInput
from app.models.knowledge import QUOTE_MAX_CHARS
from app.research.quotes import LINE_BREAK_HYPHEN

__all__ = ["CHUNK_MAX_CHARS", "CHUNK_OVERLAP_MAX_CHARS", "TextChunk", "chunk_text"]

CHUNK_MAX_CHARS = 1200
CHUNK_OVERLAP_MAX_CHARS = QUOTE_MAX_CHARS
PARAGRAPH_BREAK = re.compile(r"\n[ \t\f\v]*\n")
SENTENCE_END = re.compile(r"(?<=[.!?])\s+")
JOINED_WORD = r"\1\2"


@dataclass(frozen=True)
class TextChunk:
    ordinal: int
    text: str
    locator: str


@dataclass(frozen=True)
class _Unit:
    paragraph: int
    text: str


def chunk_text(text: str, *, max_chars: int = CHUNK_MAX_CHARS) -> list[TextChunk]:
    if max_chars <= CHUNK_OVERLAP_MAX_CHARS:
        raise InvalidInput(f"A chunk must allow more than {CHUNK_OVERLAP_MAX_CHARS} characters")
    units = _units(text, max_chars)
    if not units:
        raise InvalidInput("The text to chunk has no words")
    groups: list[list[_Unit]] = []
    current: list[_Unit] = []
    for unit in units:
        if current and len(_joined([*current, unit])) > max_chars:
            groups.append(current)
            current = _overlap(current[-1], unit, max_chars)
        current.append(unit)
    groups.append(current)
    return [TextChunk(ordinal, _joined(group), _locator(group)) for ordinal, group in enumerate(groups)]


def _overlap(tail: _Unit, unit: _Unit, max_chars: int) -> list[_Unit]:
    if len(tail.text) <= CHUNK_OVERLAP_MAX_CHARS and len(_joined([tail, unit])) <= max_chars:
        return [tail]
    return []


def _units(text: str, max_chars: int) -> list[_Unit]:
    joined = LINE_BREAK_HYPHEN.sub(JOINED_WORD, text.replace("\r\n", "\n"))
    paragraphs = [" ".join(part.split()) for part in PARAGRAPH_BREAK.split(joined)]
    units: list[_Unit] = []
    for number, paragraph in enumerate((p for p in paragraphs if p), start=1):
        pieces = [paragraph] if len(paragraph) <= max_chars else _split_long(paragraph, max_chars)
        units.extend(_Unit(number, piece) for piece in pieces)
    return units


def _split_long(paragraph: str, max_chars: int) -> list[str]:
    pieces: list[str] = []
    for sentence in SENTENCE_END.split(paragraph):
        pieces.extend([sentence] if len(sentence) <= max_chars else _split_words(sentence, max_chars))
    return pieces


def _split_words(sentence: str, max_chars: int) -> list[str]:
    pieces: list[str] = []
    current = ""
    for word in sentence.split(" "):
        for part in (word[i : i + max_chars] for i in range(0, len(word), max_chars)):
            if current and len(current) + 1 + len(part) > max_chars:
                pieces.append(current)
                current = part
            else:
                current = f"{current} {part}" if current else part
    if current:
        pieces.append(current)
    return pieces


def _joined(units: list[_Unit]) -> str:
    out = units[0].text
    for before, unit in pairwise(units):
        out += (" " if unit.paragraph == before.paragraph else "\n\n") + unit.text
    return out


def _locator(units: list[_Unit]) -> str:
    first, last = units[0].paragraph, units[-1].paragraph
    return f"para {first}" if first == last else f"paras {first}-{last}"
