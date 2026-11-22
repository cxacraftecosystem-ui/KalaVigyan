from __future__ import annotations

import json
import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from functools import lru_cache
from types import MappingProxyType
from typing import Any

from .craft_master_loader import DATA_DIR
from .craft_text import core_key, key_phrases

__all__ = [
    "PLACES_ABROAD_FILE",
    "PLACES_ABROAD_SCHEMA_VERSION",
    "SOVEREIGN_NAMES_FILE",
    "PlacesAbroad",
    "load_places_abroad",
    "load_sovereign_names",
    "parse_places_abroad",
    "parse_sovereign_names",
]

PLACES_ABROAD_FILE = DATA_DIR / "places_abroad.json"
SOVEREIGN_NAMES_FILE = DATA_DIR / "places_abroad.natural_earth.json"
PLACES_ABROAD_SCHEMA_VERSION = 1
SOVEREIGN_NAMES_SCHEMA_VERSION = 1
NAME_MIN_CHARS = 4
INDIA = frozenset({"india", "indian"})


@dataclass(frozen=True)
class PlacesAbroad:
    names: Mapping[str, str]
    other_senses: re.Pattern[str] | None
    longest: int
    left_out: frozenset[str] = frozenset()

    def accounts_for(self, name: str) -> bool:
        key = core_key(name)
        return key in self.names or key in self.left_out

    def named_in(self, text: str) -> tuple[str, ...]:
        found: list[str] = []
        for part in self._outside_other_senses(core_key(text)):
            found.extend(self.names[key] for key in key_phrases(part, self.longest) if key in self.names)
        return tuple(dict.fromkeys(found))

    def _outside_other_senses(self, key: str) -> list[str]:
        if self.other_senses is None:
            return [key]
        return [part.strip() for part in self.other_senses.split(key)]


def parse_places_abroad(raw: Mapping[str, Any]) -> PlacesAbroad:
    if raw.get("schemaVersion") != PLACES_ABROAD_SCHEMA_VERSION:
        raise ValueError(f"places abroad need schemaVersion {PLACES_ABROAD_SCHEMA_VERSION}")
    countries: Mapping[str, list[str]] = raw.get("countries") or {}
    labels = [*countries, *(word for words in countries.values() for word in words)]
    names = _keyed([*labels, *raw.get("regions", []), *raw.get("cultures", [])])
    senses = _keyed(raw.get("otherSenses", []))
    unplaced = sorted(label for key, label in senses.items() if not set(key.split()) & _words(names))
    if unplaced:
        raise ValueError(f"other senses must hold a listed place word: {', '.join(unplaced)}")
    return PlacesAbroad(
        names=MappingProxyType(names),
        other_senses=_senses_pattern(senses) if senses else None,
        longest=max(len(key.split()) for key in names),
        left_out=_left_out(raw.get("leftOut") or {}, names),
    )


def parse_sovereign_names(raw: Mapping[str, Any]) -> tuple[str, ...]:
    if raw.get("schemaVersion") != SOVEREIGN_NAMES_SCHEMA_VERSION:
        raise ValueError(f"sovereign names need schemaVersion {SOVEREIGN_NAMES_SCHEMA_VERSION}")
    names = raw.get("names")
    if (
        not isinstance(names, list)
        or not names
        or not all(isinstance(name, str) and name.strip() for name in names)
    ):
        raise ValueError("sovereign names are a list of names")
    if any(set(core_key(name).split()) & INDIA for name in names):
        raise ValueError("sovereign names leave India out")
    return tuple(names)


@lru_cache(maxsize=1)
def load_places_abroad() -> PlacesAbroad:
    return parse_places_abroad(json.loads(PLACES_ABROAD_FILE.read_text(encoding="utf-8")))


def load_sovereign_names() -> tuple[str, ...]:
    return parse_sovereign_names(json.loads(SOVEREIGN_NAMES_FILE.read_text(encoding="utf-8")))


def _left_out(reasons: Mapping[str, Any], names: Mapping[str, str]) -> frozenset[str]:
    unexplained = sorted(
        label for label, reason in reasons.items() if not isinstance(reason, str) or not reason
    )
    if unexplained:
        raise ValueError(f"a name left out says why: {', '.join(unexplained)}")
    listed = sorted(label for label in reasons if core_key(label) in names)
    if listed:
        raise ValueError(f"left out but listed: {', '.join(listed)}")
    return frozenset(core_key(label) for label in reasons)


def _keyed(labels: Iterable[str]) -> dict[str, str]:
    keyed: dict[str, str] = {}
    for label in labels:
        key = core_key(label)
        if len(key) < NAME_MIN_CHARS or set(key.split()) & INDIA:
            raise ValueError(f"{label!r} is too short to name a place, or names India")
        if key in keyed:
            raise ValueError(f"{label!r} is listed twice")
        keyed[key] = label
    return keyed


def _words(names: Mapping[str, str]) -> set[str]:
    return {word for key in names for word in key.split()}


def _senses_pattern(senses: Mapping[str, str]) -> re.Pattern[str]:
    longest_first = sorted(senses, key=lambda key: (-len(key), key))
    return re.compile(rf"(?:^| )(?:{'|'.join(re.escape(key) for key in longest_first)})(?= |$)")
