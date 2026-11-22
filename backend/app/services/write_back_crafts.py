from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from .write_back_names import CraftNames

__all__ = [
    "MATERIAL_SCIENCE_FIELDS",
    "SKIP_ABROAD",
    "SKIP_OTHER_PLACE",
    "SKIP_SEVERAL_CATALOGUED",
    "SKIP_SEVERAL_CRAFTS",
    "SKIP_UNNAMED",
    "CraftFiling",
    "craft_filing",
    "researched_craft",
]

MATERIAL_SCIENCE_FIELDS = frozenset({"CHEMISTRY", "PHYSICS", "MATERIALS"})
SKIP_SEVERAL_CRAFTS = "names more than one of the compared crafts, so no one craft's page can hold it"
SKIP_SEVERAL_CATALOGUED = "names {crafts} and not the craft researched, so no one craft's page can hold it"
SKIP_ABROAD = "is about {places}, outside India or another culture's practice, so no Indian craft holds it"
SKIP_OTHER_PLACE = "names {places} but no craft of it, so neither a craft's page nor its family holds it"
SKIP_UNNAMED = (
    "names no craft and is not material science its craft family shares, so no craft's page holds it"
)


@dataclass(frozen=True)
class CraftFiling:
    slug: str | None
    refused: str | None = None
    family: str | None = None


def craft_filing(text: str, quotes: Sequence[str], *, field: str | None, names: CraftNames) -> CraftFiling:
    if names.lead is None:
        return CraftFiling(None)
    for said in ((text,), tuple(quotes)):
        named = _named(said, names)
        if named is not None:
            return named
        abroad = names.abroad_in(said)
        if abroad:
            return CraftFiling(None, SKIP_ABROAD.format(places=", ".join(abroad)))
    places = names.places_in((text, *quotes))
    if places:
        return CraftFiling(None, SKIP_OTHER_PLACE.format(places=", ".join(places)))
    if field in MATERIAL_SCIENCE_FIELDS and names.family is not None:
        return CraftFiling(None, family=names.family)
    return CraftFiling(None, SKIP_UNNAMED)


def researched_craft(names: CraftNames) -> CraftFiling:
    return CraftFiling(names.lead_slug)


def _named(said: Sequence[str], names: CraftNames) -> CraftFiling | None:
    if not said:
        return None
    researched = names.researched(said)
    if len(researched) > 1:
        return CraftFiling(None, SKIP_SEVERAL_CRAFTS)
    if researched:
        return CraftFiling(researched[0].slug)
    others = names.catalogued(said)
    if len(others) > 1:
        crafts = ", ".join(craft.name for craft in others)
        return CraftFiling(None, SKIP_SEVERAL_CATALOGUED.format(crafts=crafts))
    return CraftFiling(others[0].slug) if others else None
