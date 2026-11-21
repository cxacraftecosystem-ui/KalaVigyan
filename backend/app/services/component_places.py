from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from app.data.district_register import load_district_codes
from app.models.enums import DISTRICT_PLACE_PREFIX

from .stated_names import register_places_named

__all__ = [
    "CLIMATE_FIELD",
    "PLACE_SUBJECT_PREFIX",
    "REGION_KINDS",
    "PlaceBinding",
    "PlacesHeld",
    "component_binding",
    "joined_places",
    "named_places",
    "practised_states",
    "subject_place_keys",
]

REGION_KINDS = frozenset(
    {
        "map_layer",
        "map_sequence",
        "timeline_map",
        "region_story",
        "supply_map",
        "climate_risk",
    }
)
CLIMATE_FIELD = "CLIMATE"
PLACE_SUBJECT_PREFIX = "place:"
DISTRICT_KEY_PREFIX = f"{DISTRICT_PLACE_PREFIX}:"


@dataclass(frozen=True)
class PlacesHeld:
    districts: frozenset[int] = frozenset()
    states: frozenset[int] = frozenset()


@dataclass(frozen=True)
class PlaceBinding:
    bound: bool = False
    districts: frozenset[int] = frozenset()
    states: frozenset[int] = frozenset()

    def held_by(self, held: PlacesHeld) -> bool:
        if not self.bound:
            return True
        return bool(self.districts & held.districts or self.states & held.states)


def joined_places(found: Iterable[PlacesHeld]) -> PlacesHeld:
    districts: set[int] = set()
    states: set[int] = set()
    for held in found:
        districts |= held.districts
        states |= held.states
    return PlacesHeld(frozenset(districts), frozenset(states))


def subject_place_keys(subjects: Iterable[str]) -> list[str]:
    return [
        subject.removeprefix(PLACE_SUBJECT_PREFIX)
        for subject in subjects
        if subject.startswith(PLACE_SUBJECT_PREFIX)
    ]


def component_binding(*, kind: str, field: str, places: Iterable[str], texts: Iterable[str]) -> PlaceBinding:
    keys = [key for key in places if key]
    names = {name for text in texts if text for name in register_places_named(text)}
    named = named_places(names)
    stated = frozenset(lgd for key in keys if (lgd := _district_lgd(key)) is not None)
    bound = bool(keys or names) or kind in REGION_KINDS or field == CLIMATE_FIELD
    return PlaceBinding(bound=bound, districts=stated | named.districts, states=named.states)


def named_places(names: Iterable[str]) -> PlacesHeld:
    codes = load_district_codes()
    found = set(names)
    states = {name for name in found if codes.state_lgd(name) is not None}
    candidates: dict[str, list[tuple[str, str]]] = {}
    for pair in codes.districts:
        if pair[1] in found:
            candidates.setdefault(pair[1], []).append(pair)
    chosen = [pair for pairs in candidates.values() for pair in [p for p in pairs if p[0] in states] or pairs]
    covered = {state for state, _ in chosen}
    return PlacesHeld(
        districts=frozenset(codes.districts[pair] for pair in chosen),
        states=frozenset(lgd for name in states - covered if (lgd := codes.state_lgd(name)) is not None),
    )


def practised_states(names: Iterable[str]) -> frozenset[int]:
    codes = load_district_codes()
    return frozenset(lgd for name in names if (lgd := codes.state_lgd(name.strip())) is not None)


def _district_lgd(key: str) -> int | None:
    if not key.startswith(DISTRICT_KEY_PREFIX):
        return None
    number = key.removeprefix(DISTRICT_KEY_PREFIX)
    return int(number) if number.isdigit() else None
