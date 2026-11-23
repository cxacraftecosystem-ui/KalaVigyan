from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from functools import lru_cache
from types import MappingProxyType

from app.data.district_register import load_district_codes, load_district_other_names, load_district_register
from app.data.river_names import load_river_names
from app.research.calendar import MONTH_NAMES, months_named, regional_months_named, seasons_named
from app.research.calendar_words import REGIONAL_MONTHS
from app.research.quotes import quote_occurs

__all__ = [
    "COMPASS_WORDS",
    "RegisterPlace",
    "place_spellings",
    "register_places",
    "register_places_named",
    "river_names_named",
    "unstated_names",
]

COMPASS_WORDS = frozenset({"North", "South", "East", "West", "Central", "Outer", "Middle"})


@dataclass(frozen=True)
class RegisterPlace:
    written: str
    register: str


def unstated_names(text: str, supports: Sequence[str]) -> list[str]:
    months = sorted(months_named([text]) - months_named(supports))
    seasons = sorted(seasons_named([text]) - seasons_named(supports))
    regional = [
        month
        for month in sorted(regional_months_named([text]))
        if not any(_quoted(name, supports) for name in REGIONAL_MONTHS[month])
    ]
    found = register_places(text)
    places = [
        place.written
        for place in found
        if place.written == place.register and not _stated(place.register, supports)
    ]
    written = {place.written for place in found}
    rivers = [name for name in river_names_named(text) if name not in written and not _quoted(name, supports)]
    return [
        *(MONTH_NAMES[month - 1] for month in months),
        *(season.lower() for season in seasons),
        *regional,
        *places,
        *rivers,
    ]


def register_places_named(text: str) -> list[str]:
    return list(dict.fromkeys(place.register for place in register_places(text)))


def river_names_named(text: str) -> list[str]:
    return load_river_names().named_in(text)


def register_places(text: str) -> list[RegisterPlace]:
    spelled = _register_spellings()
    found = (
        RegisterPlace(match.group(0), spelled[match.group(0)]) for match in _register_pattern().finditer(text)
    )
    return list(dict.fromkeys(found))


def place_spellings(register_name: str) -> tuple[str, ...]:
    return (register_name, *_other_names().get(register_name, ()))


def _stated(register_name: str, supports: Sequence[str]) -> bool:
    return any(_quoted(name, supports) for name in place_spellings(register_name))


def _quoted(name: str, supports: Sequence[str]) -> bool:
    return any(quote_occurs(name.casefold(), support.casefold()) for support in supports)


@lru_cache(maxsize=1)
def _other_names() -> Mapping[str, tuple[str, ...]]:
    named = {lgd: district for (_, district), lgd in load_district_codes().districts.items()}
    found: dict[str, tuple[str, ...]] = {}
    for lgd, others in load_district_other_names().items():
        found[named[lgd]] = (*found.get(named[lgd], ()), *others)
    return MappingProxyType(found)


@lru_cache(maxsize=1)
def _register_spellings() -> Mapping[str, str]:
    names = [
        name for name in load_district_register().place_names() if not set(name.split()) <= COMPASS_WORDS
    ]
    spelled = {name: name for name in names}
    for register_name, others in _other_names().items():
        spelled.update({other: register_name for other in others if other not in spelled})
    return MappingProxyType(spelled)


@lru_cache(maxsize=1)
def _register_pattern() -> re.Pattern[str]:
    ordered = sorted(_register_spellings(), key=lambda name: (-len(name), name))
    return re.compile(r"(?<![\w-])(?:" + "|".join(re.escape(name) for name in ordered) + r")(?![\w-])")
