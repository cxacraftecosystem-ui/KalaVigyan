from __future__ import annotations

import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from functools import lru_cache
from pathlib import Path
from types import MappingProxyType
from typing import Any

from .craft_master_loader import DATA_DIR

__all__ = [
    "INTERFACE_WORDS_DIR",
    "INTERFACE_WORDS_SCHEMA_VERSION",
    "Review",
    "WordEntry",
    "load_interface_words",
    "parse_interface_words",
    "placeholders_of",
]

INTERFACE_WORDS_DIR = DATA_DIR / "interface_words"
INTERFACE_WORDS_SCHEMA_VERSION = 1
KEY = re.compile(r"^[a-z]+(?:\.[a-z][A-Za-z]*)+$")
PLACEHOLDER = re.compile(r"\{([a-z]+)\}")


@dataclass(frozen=True)
class Review:
    by: str
    on: date


@dataclass(frozen=True)
class WordEntry:
    key: str
    english: str
    text: str
    source: str
    review: Review | None
    note: str | None = None


def placeholders_of(text: str) -> list[str]:
    return sorted(PLACEHOLDER.findall(text))


def parse_interface_words(raw: Mapping[str, Any], language: str) -> tuple[WordEntry, ...]:
    if raw.get("schemaVersion") != INTERFACE_WORDS_SCHEMA_VERSION:
        raise ValueError(
            f"interface words for {language} need schemaVersion {INTERFACE_WORDS_SCHEMA_VERSION}"
        )
    if raw.get("language") != language:
        raise ValueError(f"the interface words file for {language} names {raw.get('language')!r}")
    entries = tuple(_entry(item, language) for item in _listed(raw.get("words"), language))
    seen: set[tuple[str, str]] = set()
    for entry in entries:
        if (entry.key, entry.english) in seen:
            raise ValueError(f"{language}: {entry.key} gives {entry.english!r} twice")
        seen.add((entry.key, entry.english))
    return entries


@lru_cache(maxsize=1)
def load_interface_words() -> Mapping[str, tuple[WordEntry, ...]]:
    return MappingProxyType({path.stem: _read(path) for path in sorted(INTERFACE_WORDS_DIR.glob("*.json"))})


def _read(path: Path) -> tuple[WordEntry, ...]:
    return parse_interface_words(json.loads(path.read_text(encoding="utf-8")), path.stem)


def _listed(words: Any, language: str) -> Sequence[Mapping[str, Any]]:
    if not isinstance(words, list) or not all(isinstance(item, dict) for item in words):
        raise ValueError(f"the interface words for {language} are a list of entries")
    return words


def _entry(item: Mapping[str, Any], language: str) -> WordEntry:
    key, english, text, source = (
        _text(item, field, language) for field in ("key", "english", "text", "source")
    )
    if not KEY.fullmatch(key):
        raise ValueError(f"{language}: {key!r} is not a dotted interface word key")
    if placeholders_of(english) != placeholders_of(text):
        raise ValueError(f"{language}: {key} {english!r} and its text must hold the same placeholders")
    note = item.get("note")
    if note is not None and not (isinstance(note, str) and note.strip()):
        raise ValueError(f"{language}: {key} {english!r} has an empty note")
    return WordEntry(key, english, text, source, _review(item.get("review"), f"{language}: {key}"), note)


def _review(raw: Any, where: str) -> Review | None:
    if raw is None:
        return None
    if not isinstance(raw, dict) or set(raw) != {"by", "on"}:
        raise ValueError(f"{where}: a review names who read it (by) and the day (on), and nothing else")
    by, on = raw["by"], raw["on"]
    if not isinstance(by, str) or not by.strip():
        raise ValueError(f"{where}: a review names its reader")
    try:
        day = date.fromisoformat(on) if isinstance(on, str) else None
    except ValueError:
        day = None
    if day is None:
        raise ValueError(f"{where}: a review gives its day as YYYY-MM-DD")
    return Review(by.strip(), day)


def _text(item: Mapping[str, Any], field: str, language: str) -> str:
    value = item.get(field)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{language}: every interface word gives a non-empty {field}")
    return value
