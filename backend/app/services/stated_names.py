from __future__ import annotations

import re
from collections.abc import Sequence
from functools import lru_cache

from app.data.district_register import load_district_register
from app.data.river_names import load_river_names
from app.research.calendar import MONTH_NAMES, months_named, seasons_named
from app.research.quotes import quote_occurs

__all__ = ["COMPASS_WORDS", "register_places_named", "river_names_named", "unstated_names"]

COMPASS_WORDS = frozenset({"North", "South", "East", "West", "Central", "Outer", "Middle"})


def unstated_names(text: str, supports: Sequence[str]) -> list[str]:
    months = sorted(months_named([text]) - months_named(supports))
    seasons = sorted(seasons_named([text]) - seasons_named(supports))
    places = [name for name in register_places_named(text) if not _stated(name, supports)]
    rivers = [name for name in river_names_named(text) if name not in places and not _stated(name, supports)]
    return [
        *(MONTH_NAMES[month - 1] for month in months),
        *(season.lower() for season in seasons),
        *places,
        *rivers,
    ]


def register_places_named(text: str) -> list[str]:
    return list(dict.fromkeys(match.group(0) for match in _register_places().finditer(text)))


def river_names_named(text: str) -> list[str]:
    return load_river_names().named_in(text)


def _stated(name: str, supports: Sequence[str]) -> bool:
    return any(quote_occurs(name.casefold(), support.casefold()) for support in supports)


@lru_cache(maxsize=1)
def _register_places() -> re.Pattern[str]:
    names = [
        name for name in load_district_register().place_names() if not set(name.split()) <= COMPASS_WORDS
    ]
    ordered = sorted(names, key=lambda name: (-len(name), name))
    return re.compile(r"(?<![\w-])(?:" + "|".join(re.escape(name) for name in ordered) + r")(?![\w-])")
