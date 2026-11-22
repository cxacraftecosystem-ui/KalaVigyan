from __future__ import annotations

from collections.abc import Mapping
from functools import lru_cache
from types import MappingProxyType

from pint import UnitRegistry
from pint.errors import PintError

from .local_units import LOCAL_UNITS

__all__ = [
    "INFORMAL_METRIC_WORDS",
    "METRIC_UNIT_NAMES",
    "PINT_NAMES",
    "measures_alike",
    "metric_unit_named",
    "unit_registry",
]

METRIC_UNIT_NAMES: Mapping[str, str] = MappingProxyType(
    {
        "millimeter": "mm",
        "centimeter": "cm",
        "meter": "m",
        "kilometer": "km",
        "meter ** 2": "m2",
        "hectare": "ha",
        "gram": "g",
        "kilogram": "kg",
        "milliliter": "ml",
        "liter": "l",
    }
)
INFORMAL_METRIC_WORDS: Mapping[str, str] = MappingProxyType(
    {"kilo": "kg", "kilos": "kg", "gm": "g", "gms": "g"}
)
PINT_NAMES = MappingProxyType({key: name for name, key in METRIC_UNIT_NAMES.items()})


@lru_cache(maxsize=1)
def unit_registry() -> UnitRegistry:
    registry = UnitRegistry()
    for key in LOCAL_UNITS:
        registry.define(f"{key} = [{key}]")
    return registry


def metric_unit_named(word: str) -> str | None:
    folded = " ".join(word.casefold().replace(".", " ").split())
    if folded in INFORMAL_METRIC_WORDS:
        return INFORMAL_METRIC_WORDS[folded]
    try:
        unit = unit_registry().parse_units(folded)
    except PintError, ValueError:
        return None
    return METRIC_UNIT_NAMES.get(str(unit))


def measures_alike(unit_key: str, metric_unit: str) -> bool:
    local = LOCAL_UNITS.get(unit_key)
    if local is None or metric_unit not in PINT_NAMES:
        return False
    registry = unit_registry()
    measured = registry.parse_units(PINT_NAMES[local.measures]).dimensionality
    return measured == registry.parse_units(PINT_NAMES[metric_unit]).dimensionality
