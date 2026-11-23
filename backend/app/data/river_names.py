from __future__ import annotations

import json
import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from functools import lru_cache
from types import MappingProxyType
from typing import Any

from .craft_master_loader import DATA_DIR
from .english_words import load_english_words

__all__ = [
    "RIVER_NAMES_DIR",
    "RIVER_NAMES_SCHEMA_VERSION",
    "RIVER_NAME_FILES",
    "NamedRiver",
    "RiverNameSet",
    "RiverNames",
    "checkable",
    "checked_forms",
    "load_river_names",
    "name_forms",
    "parse_river_names",
    "place_river",
]

RIVER_NAMES_DIR = DATA_DIR / "rivers"
RIVER_NAME_FILES = ("river_names.wikidata.json", "river_names.osm.json")
RIVER_NAMES_SCHEMA_VERSION = 1
GENERIC_WORDS = frozenset({"river", "nadi", "nala", "nallah", "nullah"})
BRACKETED = re.compile(r"\s*\(([^()]+)\)\s*")
WORD = re.compile(r"[A-Za-z][A-Za-z-]*")
NAME_WORDS_MAX = 6
ITEM_REF = re.compile(r"^Q[1-9][0-9]*$")
ONE_WORD_CHARS_MIN = 4


@dataclass(frozen=True)
class NamedRiver:
    name: str
    dataset_code: str
    refs: tuple[str, ...]
    main_riv: int
    reach_ids: tuple[int, ...]
    district_lgds: tuple[int, ...]


@dataclass(frozen=True)
class RiverNameSet:
    dataset: Mapping[str, Any]
    rivers: tuple[NamedRiver, ...]

    @property
    def code(self) -> str:
        return str(self.dataset["code"])


@dataclass(frozen=True)
class RiverNames:
    sets: tuple[RiverNameSet, ...] = ()
    by_reach: Mapping[int, NamedRiver] = field(default_factory=lambda: MappingProxyType({}))
    checked: frozenset[str] = frozenset()

    def of_reach(self, hyriv_id: int) -> NamedRiver | None:
        return self.by_reach.get(hyriv_id)

    def dataset(self, code: str) -> Mapping[str, Any] | None:
        return next((names.dataset for names in self.sets if names.code == code), None)

    def place_river(self, place_name: str, district_lgd: int | None) -> NamedRiver | None:
        wanted = {form.casefold() for form in name_forms(place_name)}
        for names in self.sets:
            found = [
                river
                for river in names.rivers
                if wanted & {form.casefold() for form in name_forms(river.name)}
                and (district_lgd is None or district_lgd in river.district_lgds)
            ]
            if found:
                return found[0] if len(found) == 1 else None
        return None

    def named_in(self, text: str) -> list[str]:
        words = WORD.findall(text)
        covered: set[int] = set()
        found: list[str] = []
        for size in range(min(NAME_WORDS_MAX, len(words)), 0, -1):
            for start in range(len(words) - size + 1):
                name = " ".join(words[start : start + size])
                if name in self.checked and covered.isdisjoint(range(start, start + size)):
                    covered.update(range(start, start + size))
                    found.append(name)
        return list(dict.fromkeys(found))


def name_forms(name: str) -> tuple[str, ...]:
    inner = BRACKETED.findall(name)
    outer = BRACKETED.sub(" ", name).strip()
    forms = [form for form in (outer, *inner) if form]
    bare = [" ".join(word for word in form.split() if word.casefold() not in GENERIC_WORDS) for form in forms]
    return tuple(dict.fromkeys(form for form in (*forms, *bare) if form))


def parse_river_names(bodies: Iterable[Mapping[str, Any]], english: frozenset[str]) -> RiverNames:
    sets = tuple(_name_set(body) for body in bodies)
    by_reach: dict[int, NamedRiver] = {}
    for names in sets:
        for river in names.rivers:
            for reach in river.reach_ids:
                if reach in by_reach:
                    raise ValueError(
                        f"reach {reach} is named twice, as {by_reach[reach].name} and {river.name}"
                    )
                by_reach[reach] = river
    checked = frozenset(
        form for names in sets for river in names.rivers for form in checked_forms(river, english)
    )
    return RiverNames(sets=sets, by_reach=MappingProxyType(by_reach), checked=checked)


def checked_forms(river: NamedRiver, english: frozenset[str]) -> list[str]:
    item = all(ITEM_REF.match(ref) for ref in river.refs)
    return [form for form in name_forms(river.name) if checkable(form, english) and (" " in form or item)]


def checkable(form: str, english: frozenset[str]) -> bool:
    words = WORD.findall(form)
    if " ".join(words) != form or len(words) > NAME_WORDS_MAX:
        return False
    return len(words) > 1 or (len(form) >= ONE_WORD_CHARS_MIN and form.casefold() not in english)


def _name_set(body: Mapping[str, Any]) -> RiverNameSet:
    if body.get("schemaVersion") != RIVER_NAMES_SCHEMA_VERSION:
        raise ValueError(f"a river names file is schema version {RIVER_NAMES_SCHEMA_VERSION}")
    code = str(body["dataset"]["code"])
    rivers = tuple(
        NamedRiver(
            name=str(row["name"]),
            dataset_code=code,
            refs=tuple(str(ref) for ref in row["refs"]),
            main_riv=int(row["mainRiv"]),
            reach_ids=tuple(int(reach) for reach in row["reachIds"]),
            district_lgds=tuple(int(lgd) for lgd in row["districtLgds"]),
        )
        for row in body["rivers"]
    )
    if any(not river.reach_ids or not river.name.strip() for river in rivers):
        raise ValueError(f"every river of {code} has a name and at least one reach")
    return RiverNameSet(dataset=MappingProxyType(dict(body["dataset"])), rivers=rivers)


@lru_cache(maxsize=1)
def load_river_names() -> RiverNames:
    paths = [RIVER_NAMES_DIR / name for name in RIVER_NAME_FILES]
    bodies = [json.loads(path.read_text(encoding="utf-8")) for path in paths if path.is_file()]
    return parse_river_names(bodies, load_english_words())


def place_river(place_name: str, district_lgd: int | None) -> NamedRiver | None:
    return load_river_names().place_river(place_name, district_lgd)
