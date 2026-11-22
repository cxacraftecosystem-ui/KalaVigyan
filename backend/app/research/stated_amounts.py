from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from decimal import Decimal
from functools import lru_cache
from types import MappingProxyType

from .local_units import LOCAL_UNITS
from .stated_quantities import NUMBER_PATTERN, stated_decimal

__all__ = [
    "ACIDITY_UNIT",
    "AMOUNT_KINDS",
    "AMOUNT_UNITS",
    "AmountUnit",
    "StatedAmount",
    "stated_amounts",
]

AMOUNT_KINDS = (
    "TEMPERATURE",
    "TIME",
    "MASS",
    "LENGTH",
    "AREA",
    "VOLUME",
    "CONCENTRATION",
    "SHARE",
    "ACIDITY",
)
ACIDITY_UNIT = "ph"
SYMBOL_CHARS_MAX = 2
RANGE_JOIN = r"\s*(?:-|–|—|to)\s*"
WORD_END = r"(?![^\W\d_])"
METRIC_MEASURES: Mapping[str, str] = MappingProxyType(
    {
        "mm": "LENGTH",
        "cm": "LENGTH",
        "m": "LENGTH",
        "km": "LENGTH",
        "m2": "AREA",
        "ha": "AREA",
        "g": "MASS",
        "kg": "MASS",
        "ml": "VOLUME",
        "l": "VOLUME",
    }
)


@dataclass(frozen=True)
class AmountUnit:
    measures: str
    words: tuple[str, ...]


@dataclass(frozen=True)
class StatedAmount:
    stated: str
    low: Decimal
    high: Decimal | None
    unit: str
    measures: str


SCIENCE_UNITS: Mapping[str, AmountUnit] = MappingProxyType(
    {
        "degree-celsius": AmountUnit(
            "TEMPERATURE",
            ("°C", "° C", "ºC", "℃", "degrees Celsius", "degree Celsius", "degrees centigrade", "deg C"),
        ),
        "degree-fahrenheit": AmountUnit("TEMPERATURE", ("°F", "° F", "℉", "degrees Fahrenheit")),
        "second": AmountUnit("TIME", ("second", "seconds", "sec", "secs")),
        "minute": AmountUnit("TIME", ("minute", "minutes", "min", "mins")),
        "hour": AmountUnit("TIME", ("hour", "hours", "hr", "hrs")),
        "day": AmountUnit("TIME", ("day", "days")),
        "week": AmountUnit("TIME", ("week", "weeks")),
        "month": AmountUnit("TIME", ("month", "months")),
        "milligram": AmountUnit("MASS", ("mg", "milligram", "milligrams")),
        "gram": AmountUnit("MASS", ("g", "gm", "gms", "gram", "grams", "gramme", "grammes")),
        "kilogram": AmountUnit("MASS", ("kg", "kgs", "kilo", "kilos", "kilogram", "kilograms")),
        "tonne": AmountUnit("MASS", ("tonne", "tonnes", "ton", "tons")),
        "micrometre": AmountUnit("LENGTH", ("µm", "μm", "micron", "microns", "micrometre", "micrometres")),
        "nanometre": AmountUnit("LENGTH", ("nm", "nanometre", "nanometres", "nanometer", "nanometers")),
        "millimetre": AmountUnit("LENGTH", ("mm", "millimetre", "millimetres", "millimeter", "millimeters")),
        "centimetre": AmountUnit("LENGTH", ("cm", "centimetre", "centimetres", "centimeter", "centimeters")),
        "metre": AmountUnit("LENGTH", ("m", "metre", "metres", "meter", "meters")),
        "kilometre": AmountUnit("LENGTH", ("km", "kilometre", "kilometres", "kilometer", "kilometers")),
        "hectare": AmountUnit("AREA", ("ha", "hectare", "hectares")),
        "acre": AmountUnit("AREA", ("acre", "acres")),
        "millilitre": AmountUnit(
            "VOLUME", ("ml", "mL", "millilitre", "millilitres", "milliliter", "milliliters")
        ),
        "litre": AmountUnit("VOLUME", ("l", "L", "litre", "litres", "liter", "liters", "ltr", "ltrs")),
        "gram-per-litre": AmountUnit(
            "CONCENTRATION", ("g/l", "g/L", "gpl", "grams per litre", "g per litre")
        ),
        "milligram-per-litre": AmountUnit("CONCENTRATION", ("mg/l", "mg/L")),
        "part-per-million": AmountUnit("CONCENTRATION", ("ppm",)),
        "percent": AmountUnit("SHARE", ("%", "per cent", "percent")),
    }
)
AMOUNT_UNITS: Mapping[str, AmountUnit] = MappingProxyType(
    {
        **SCIENCE_UNITS,
        **{key: AmountUnit(METRIC_MEASURES[unit.measures], unit.words) for key, unit in LOCAL_UNITS.items()},
        ACIDITY_UNIT: AmountUnit("ACIDITY", ()),
    }
)
ACIDITY = re.compile(
    rf"(?<![\w])pH\s*(?:(?:of|value of|value)\s*)?(?P<low>{NUMBER_PATTERN})(?:{RANGE_JOIN}(?P<high>{NUMBER_PATTERN}))?"
    r"(?![\d])"
)


def stated_amounts(text: str) -> list[StatedAmount]:
    found: list[tuple[int, StatedAmount]] = []
    for match in _amount_pattern().finditer(text):
        amount = _amount(match, _unit_named(match.group("unit")))
        found += [(match.start(), amount)] if amount is not None else []
    for match in ACIDITY.finditer(text):
        amount = _amount(match, ACIDITY_UNIT)
        found += [(match.start(), amount)] if amount is not None else []
    once: dict[str, StatedAmount] = {}
    for _, amount in sorted(found, key=lambda pair: pair[0]):
        once.setdefault(amount.stated.casefold(), amount)
    return list(once.values())


def _amount(match: re.Match[str], unit: str | None) -> StatedAmount | None:
    low, high = stated_decimal(match.group("low")), stated_decimal(match.group("high"))
    if unit is None or low is None or (match.group("high") and (high is None or high <= low)):
        return None
    return StatedAmount(match.group(0), low, high, unit, AMOUNT_UNITS[unit].measures)


def _unit_named(written: str) -> str | None:
    folded = " ".join(written.split())
    return _words().get(folded) or _words().get(folded.casefold())


@lru_cache(maxsize=1)
def _words() -> Mapping[str, str]:
    found: dict[str, str] = {}
    for key, unit in AMOUNT_UNITS.items():
        for word in unit.words:
            found.setdefault(word if _symbol(word) else word.casefold(), key)
    return MappingProxyType(found)


def _symbol(word: str) -> bool:
    return len(word) <= SYMBOL_CHARS_MAX


def _alternatives(words: Iterable[str], *, folded: bool) -> str:
    ordered = sorted(set(words), key=lambda word: (-len(word), word))
    joined = "|".join(r"\s+".join(map(re.escape, word.split())) for word in ordered)
    return f"(?i:{joined})" if folded else f"(?:{joined})"


@lru_cache(maxsize=1)
def _amount_pattern() -> re.Pattern[str]:
    words = [word for unit in AMOUNT_UNITS.values() for word in unit.words]
    symbols = _alternatives((word for word in words if _symbol(word)), folded=False)
    named = _alternatives((word for word in words if not _symbol(word)), folded=True)
    return re.compile(
        rf"(?<![\w.,])(?P<low>{NUMBER_PATTERN})(?:{RANGE_JOIN}(?P<high>{NUMBER_PATTERN}))?"
        rf"(?:\s*-\s*|\s*)(?P<unit>{named}|{symbols}){WORD_END}"
    )
