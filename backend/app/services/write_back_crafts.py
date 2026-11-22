from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from .write_back_names import CraftFamily, CraftNames

__all__ = [
    "HELD_OTHER_PLACE",
    "HELD_UNNAMED",
    "MATERIAL_SCIENCE_FIELDS",
    "SKIP_ABROAD",
    "SKIP_SEVERAL_CATALOGUED",
    "SKIP_SEVERAL_CRAFTS",
    "CraftFiling",
    "FilingTexts",
    "craft_filing",
    "researched_craft",
]

MATERIAL_SCIENCE_FIELDS = frozenset({"CHEMISTRY", "PHYSICS", "MATERIALS"})
SKIP_SEVERAL_CRAFTS = "names more than one of the compared crafts, so no one craft's page can hold it"
SKIP_SEVERAL_CATALOGUED = "names {crafts} and not the craft researched, so no one craft's page can hold it"
SKIP_ABROAD = "is about {places}, outside India or another culture's practice, so no Indian craft holds it"
HELD_OTHER_PLACE = "names {places} but no craft of it"
HELD_UNNAMED = (
    "names no craft, nor do its passage and source, and is not material science its craft family shares"
)


@dataclass(frozen=True)
class FilingTexts:
    text: str
    quotes: tuple[str, ...] = ()
    passages: tuple[str, ...] = ()
    titles: tuple[str, ...] = ()


@dataclass(frozen=True)
class CraftFiling:
    slug: str | None
    refused: str | None = None
    family: CraftFamily | None = None
    held: str | None = None


def craft_filing(said: FilingTexts, *, field: str | None, names: CraftNames) -> CraftFiling:
    if names.lead is None:
        return CraftFiling(None)
    own = _filed_by(((said.text,), said.quotes), names)
    if own is not None:
        return own
    context = _filed_by((said.passages, said.titles), names)
    if context is not None:
        return context
    if field in MATERIAL_SCIENCE_FIELDS and names.family is not None:
        return CraftFiling(None, family=names.family)
    return CraftFiling(names.lead_slug, held=HELD_UNNAMED)


def researched_craft(names: CraftNames) -> CraftFiling:
    return CraftFiling(names.lead_slug)


def _filed_by(levels: Sequence[Sequence[str]], names: CraftNames) -> CraftFiling | None:
    for said in levels:
        found = _named(said, names) or _abroad(said, names)
        if found is not None:
            return found
    places = names.places_in([text for said in levels for text in said])
    if places:
        return CraftFiling(names.lead_slug, held=HELD_OTHER_PLACE.format(places=", ".join(places)))
    return None


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


def _abroad(said: Sequence[str], names: CraftNames) -> CraftFiling | None:
    abroad = names.abroad_in(said)
    return CraftFiling(None, SKIP_ABROAD.format(places=", ".join(abroad))) if abroad else None
