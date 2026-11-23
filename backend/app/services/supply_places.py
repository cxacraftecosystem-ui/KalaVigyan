from __future__ import annotations

import re
from collections.abc import Collection, Iterable, Mapping, Sequence
from typing import Protocol

from app.research.blocks import stated_texts
from app.research.blocks_place import SupplyLink
from app.sources.reference.wikidata_places import PlaceCandidate, PlacePoint

from .place_points import OriginPlace

__all__ = [
    "PLACED_ORIGINS_MAX",
    "NamedPlace",
    "PlaceFinder",
    "chosen_candidate",
    "context_words",
    "named_places",
    "origin_places",
    "stated_words",
]

PLACED_ORIGINS_MAX = 8
CONTEXT_WORD = re.compile(r"\b[A-Z][\w-]{3,}")
DESCRIPTION_WORD = re.compile(r"[\w-]+")


class PlaceFinder(Protocol):
    async def place_candidates(self, name: str) -> list[PlaceCandidate]: ...

    async def place_points(self, item_ids: Sequence[str]) -> dict[str, PlacePoint]: ...


NamedPlace = tuple[str, frozenset[str]]


async def origin_places(finder: PlaceFinder, links: Sequence[SupplyLink]) -> dict[str, OriginPlace]:
    return await named_places(finder, _origin_contexts(links))


async def named_places(finder: PlaceFinder, named: Mapping[str, NamedPlace]) -> dict[str, OriginPlace]:
    chosen: dict[str, str] = {}
    for key, (name, words) in list(named.items())[:PLACED_ORIGINS_MAX]:
        candidate = chosen_candidate(await finder.place_candidates(name), words)
        if candidate is not None:
            chosen[key] = candidate.item_id
    if not chosen:
        return {}
    points = await finder.place_points(list(dict.fromkeys(chosen.values())))
    return {
        key: OriginPlace(item_id, points[item_id].latitude, points[item_id].longitude)
        for key, item_id in chosen.items()
        if item_id in points
    }


def chosen_candidate(candidates: Sequence[PlaceCandidate], words: Collection[str]) -> PlaceCandidate | None:
    if len(candidates) == 1:
        return candidates[0]
    described = [
        candidate
        for candidate in candidates
        if candidate.description and set(DESCRIPTION_WORD.findall(candidate.description)) & set(words)
    ]
    return described[0] if len(described) == 1 else None


def context_words(link: SupplyLink) -> frozenset[str]:
    return stated_words(stated_texts(link.sentence), (link.origin, link.material))


def stated_words(texts: Iterable[str], own: Iterable[str]) -> frozenset[str]:
    left_out = {word.casefold() for name in own for word in DESCRIPTION_WORD.findall(name)}
    stated = {word for text in texts for word in CONTEXT_WORD.findall(text)}
    return frozenset(word for word in stated if word.casefold() not in left_out)


def _origin_contexts(links: Sequence[SupplyLink]) -> dict[str, tuple[str, frozenset[str]]]:
    found: dict[str, tuple[str, frozenset[str]]] = {}
    for link in links:
        key = link.origin.casefold()
        origin, words = found.get(key, (link.origin, frozenset()))
        found[key] = (origin, words | context_words(link))
    return found
