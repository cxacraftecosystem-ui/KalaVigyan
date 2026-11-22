from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from types import MappingProxyType

from pint.errors import PintError

from .elements import ELEMENTS
from .unit_registry import unit_registry

__all__ = [
    "UNIT_WORDS",
    "StatedQuantity",
    "element_formulas_in",
    "quantities_in",
    "quantity_supported",
]

UNIT_WORDS: Mapping[str, str] = MappingProxyType(
    {
        "°C": "degC",
        "°F": "degF",
        "K": "kelvin",
        "mg/L": "mg/L",
        "mg/l": "mg/L",
        "g/L": "g/L",
        "g/l": "g/L",
        "mg": "mg",
        "kg": "kg",
        "g": "g",
        "ml": "mL",
        "mL": "mL",
        "L": "L",
        "mm": "mm",
        "cm": "cm",
        "km": "km",
        "m": "m",
        "%": "percent",
        "hours": "hour",
        "hour": "hour",
        "hrs": "hour",
        "hr": "hour",
        "h": "hour",
        "minutes": "minute",
        "minute": "minute",
        "min": "minute",
        "days": "day",
        "day": "day",
        "weeks": "week",
        "week": "week",
        "months": "month",
        "month": "month",
        "years": "year",
        "year": "year",
    }
)
_UNIT_ALTERNATION = "|".join(re.escape(unit) for unit in sorted(UNIT_WORDS, key=len, reverse=True))
QUANTITY = re.compile(r"(?<!\d)(?<!\d[.,])(\d+(?:[.,]\d+)*)(?:\s?(" + _UNIT_ALTERNATION + r")(?![\w/]))?")
ELEMENT_RUN = re.compile(r"(?<![A-Za-z0-9])(?:[A-Z][a-z]?){2,}(?![A-Za-z0-9])")
ELEMENT_SYMBOL = re.compile(r"[A-Z][a-z]?")


@dataclass(frozen=True)
class StatedQuantity:
    number: str
    unit: str | None


def quantities_in(text: str) -> list[StatedQuantity]:
    return [
        StatedQuantity(match.group(1).replace(",", ""), match.group(2)) for match in QUANTITY.finditer(text)
    ]


def quantity_supported(stated: StatedQuantity, cited: Sequence[StatedQuantity]) -> bool:
    if any(other.number == stated.number for other in cited):
        return True
    return stated.unit is not None and any(_converts_to(other, stated) for other in cited if other.unit)


def element_formulas_in(text: str) -> list[str]:
    return list(dict.fromkeys(token for token in ELEMENT_RUN.findall(text) if _element_formula(token)))


def _element_formula(token: str) -> bool:
    symbols = ELEMENT_SYMBOL.findall(token)
    return all(symbol in ELEMENTS for symbol in symbols) and any(len(symbol) == 2 for symbol in symbols)


def _converts_to(other: StatedQuantity, stated: StatedQuantity) -> bool:
    registry = unit_registry()
    try:
        wanted = registry.Quantity(float(stated.number), UNIT_WORDS[stated.unit or ""])
        found = registry.Quantity(float(other.number), UNIT_WORDS[other.unit or ""])
        if found.dimensionality != wanted.dimensionality:
            return False
        converted = found.to(wanted.units).magnitude
    except PintError, ValueError, KeyError:
        return False
    return round(converted, _decimals(stated.number)) == float(stated.number)


def _decimals(number: str) -> int:
    return len(number.split(".", 1)[1]) if "." in number else 0
