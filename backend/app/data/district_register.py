from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from functools import lru_cache
from types import MappingProxyType
from typing import Any

from .craft_master_loader import DATA_DIR

__all__ = [
    "OTHER_NAMES_FILE",
    "REGISTER_FILE",
    "DistrictCodes",
    "DistrictRegister",
    "load_district_codes",
    "load_district_other_names",
    "load_district_register",
    "load_listed_places",
    "parse_district_codes",
    "parse_district_other_names",
    "parse_district_register",
    "parse_listed_places",
]

REGISTER_FILE = DATA_DIR / "lgd_register.json"
OTHER_NAMES_FILE = DATA_DIR / "district_other_names.json"
OTHER_NAMES_SCHEMA_VERSION = 1


@dataclass(frozen=True)
class DistrictRegister:
    states: frozenset[str]
    districts: Mapping[str, frozenset[str]]

    def has_state(self, name: str) -> bool:
        return name in self.states

    def has_district(self, state: str, name: str) -> bool:
        return name in self.districts.get(state, frozenset())

    def district_names(self, state: str) -> frozenset[str]:
        return self.districts.get(state, frozenset())

    def place_names(self) -> frozenset[str]:
        return self.states.union(*self.districts.values())


@dataclass(frozen=True)
class DistrictCodes:
    states: Mapping[str, int]
    districts: Mapping[tuple[str, str], int]

    def state_lgd(self, state: str) -> int | None:
        return self.states.get(state)

    def district_lgd(self, state: str, district: str) -> int | None:
        return self.districts.get((state, district))


def parse_district_register(raw: Mapping[str, Any]) -> DistrictRegister:
    state_names = {int(row["lgd"]): str(row["name"]) for row in raw["states"]}
    named: dict[str, set[str]] = {name: set() for name in state_names.values()}
    for row in raw["districts"]:
        state_lgd = int(row["stateLgd"])
        if state_lgd not in state_names:
            raise ValueError(
                f"district {row['lgd']} names state {state_lgd}, which the register does not list"
            )
        named[state_names[state_lgd]].add(str(row["name"]))
    for row in raw.get("pending", []):
        if row["state"] not in named:
            raise ValueError(f"pending district {row['district']} names unknown state {row['state']}")
        named[row["state"]].add(str(row["district"]))
    return DistrictRegister(
        states=frozenset(named),
        districts=MappingProxyType({state: frozenset(names) for state, names in named.items()}),
    )


@lru_cache(maxsize=1)
def load_district_register() -> DistrictRegister:
    return parse_district_register(json.loads(REGISTER_FILE.read_text(encoding="utf-8")))


def parse_district_codes(raw: Mapping[str, Any]) -> DistrictCodes:
    states = {int(row["lgd"]): str(row["name"]) for row in raw["states"]}
    districts: dict[tuple[str, str], int] = {}
    for row in raw["districts"]:
        state_lgd = int(row["stateLgd"])
        if state_lgd not in states:
            raise ValueError(
                f"district {row['lgd']} names state {state_lgd}, which the register does not list"
            )
        named = (states[state_lgd], str(row["name"]))
        if named in districts:
            raise ValueError(f"district {row['lgd']} repeats {named[1]!r} of {named[0]}")
        districts[named] = int(row["lgd"])
    return DistrictCodes(
        states=MappingProxyType({name: lgd for lgd, name in states.items()}),
        districts=MappingProxyType(districts),
    )


@lru_cache(maxsize=1)
def load_district_codes() -> DistrictCodes:
    return parse_district_codes(json.loads(REGISTER_FILE.read_text(encoding="utf-8")))


def parse_listed_places(raw: Mapping[str, Any]) -> list[dict[str, Any]]:
    districts: dict[int, list[dict[str, Any]]] = {}
    for row in raw["districts"]:
        districts.setdefault(int(row["stateLgd"]), []).append(
            {"lgd": int(row["lgd"]), "name": str(row["name"])}
        )
    states = [
        {
            "lgd": int(row["lgd"]),
            "name": str(row["name"]),
            "districts": sorted(districts.get(int(row["lgd"]), []), key=lambda d: d["name"]),
        }
        for row in raw["states"]
    ]
    return sorted(states, key=lambda state: state["name"])


@lru_cache(maxsize=1)
def load_listed_places() -> tuple[dict[str, Any], ...]:
    return tuple(parse_listed_places(json.loads(REGISTER_FILE.read_text(encoding="utf-8"))))


def parse_district_other_names(
    raw: Mapping[str, Any], register: Mapping[str, Any]
) -> Mapping[int, tuple[str, ...]]:
    if raw.get("schemaVersion") != OTHER_NAMES_SCHEMA_VERSION:
        raise ValueError(
            f"district other names are schema {OTHER_NAMES_SCHEMA_VERSION}, not {raw.get('schemaVersion')!r}"
        )
    names = {int(row["lgd"]): str(row["name"]) for row in register["districts"]}
    found: dict[int, tuple[str, ...]] = {}
    for row in raw["districts"]:
        lgd = int(row["lgd"])
        if names.get(lgd) != row["name"]:
            raise ValueError(f"district {lgd} is {names.get(lgd)!r} in the LGD register, not {row['name']!r}")
        found[lgd] = tuple(str(name) for name in row["otherNames"])
    return MappingProxyType(found)


@lru_cache(maxsize=1)
def load_district_other_names() -> Mapping[int, tuple[str, ...]]:
    return parse_district_other_names(
        json.loads(OTHER_NAMES_FILE.read_text(encoding="utf-8")),
        json.loads(REGISTER_FILE.read_text(encoding="utf-8")),
    )
