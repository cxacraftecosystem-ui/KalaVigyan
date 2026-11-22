from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from types import MappingProxyType

from app.research.calendar import MONTH_NAMES

__all__ = [
    "MAX_DECIMALS",
    "RANGE_DASH",
    "compound_text",
    "decimals_of",
    "measure_text",
    "months_text",
    "number_text",
    "p_text",
    "rain_text",
    "range_text",
    "sentence_case",
    "years_text",
]

MAX_DECIMALS = 2
RANGE_DASH = "–"
MINUS = "−"
P_VALUE_UNIT = "p-value"
P_VALUE_FLOOR = 0.001
P_FINE_BELOW = 0.1
RAIN_WHOLE_FROM = 10
UNIT_TEXT: Mapping[str, str] = MappingProxyType(
    {
        "degC": "°C",
        "degC per decade": "°C per decade",
        "m2": "m²",
        "l": "L",
        "km2": "km²",
        "km/km2": "km/km²",
        "m3/s": "m³/s",
        "kg/dm3": "g/cm³",
    }
)
BARE_UNITS = frozenset({"Strahler order"})
PERCENT_UNITS = frozenset({"%", "coefficient of variation %"})
FRACTION_PREFIX = "fraction"


def decimals_of(value: float) -> int:
    if not math.isfinite(value):
        raise ValueError(f"{value} is not a finite number")
    text = f"{value:.{MAX_DECIMALS}f}".rstrip("0").rstrip(".")
    point = text.find(".")
    return 0 if point < 0 else len(text) - point - 1


def number_text(value: float, decimals: int | None = None) -> str:
    shown = decimals_of(value) if decimals is None else decimals
    whole, _, fraction = f"{abs(value):.{shown}f}".partition(".")
    text = f"{_indian_groups(whole)}.{fraction}" if fraction else _indian_groups(whole)
    return f"{MINUS}{text}" if value < 0 else text


def p_text(p_value: float) -> str:
    if p_value < P_VALUE_FLOOR:
        return f"p < {P_VALUE_FLOOR}"
    return f"p = {number_text(p_value, 3 if p_value < P_FINE_BELOW else 2)}"


def measure_text(value: float, unit: str) -> str:
    if unit.strip() == P_VALUE_UNIT:
        return p_text(value)
    prefix, suffix, scale = _parts(unit)
    return f"{prefix}{number_text(_scaled(value, scale))}{suffix}"


def range_text(low: float, high: float | None, unit: str) -> str:
    prefix, suffix, scale = _parts(unit)
    values = [_scaled(low, scale), *([] if high is None else [_scaled(high, scale)])]
    decimals = max(decimals_of(value) for value in values)
    shown = dict.fromkeys(number_text(value, decimals) for value in values)
    return f"{prefix}{RANGE_DASH.join(shown)}{suffix}"


def rain_text(millimetres: float) -> str:
    return f"{number_text(millimetres, 0 if millimetres >= RAIN_WHOLE_FROM else 1)} mm"


def months_text(months: Sequence[int]) -> str:
    runs = _runs(sorted(set(months)))
    return ", ".join(RANGE_DASH.join(MONTH_NAMES[month - 1] for month in run) for run in runs)


def years_text(first: int, last: int) -> str:
    return str(first) if first == last else f"{first}{RANGE_DASH}{last}"


def compound_text(name: str, formula: str | None, pubchem_cid: int | None) -> str:
    parts = (name, formula, f"PubChem CID {pubchem_cid}" if pubchem_cid is not None else None)
    return " · ".join(part for part in parts if part)


def sentence_case(code: str) -> str:
    words = " ".join(code.replace("_", " ").split())
    return words[:1].upper() + words[1:] if words else code


def _parts(unit: str) -> tuple[str, str, float]:
    trimmed = unit.strip()
    if trimmed == "pH":
        return "pH ", "", 1
    if trimmed in PERCENT_UNITS:
        return "", "%", 1
    if trimmed == "degree":
        return "", "°", 1
    if trimmed in BARE_UNITS:
        return "", "", 1
    if trimmed.startswith(FRACTION_PREFIX):
        rest = trimmed[len(FRACTION_PREFIX) :].strip()
        return "", f"% {rest}" if rest else "%", 100
    shown = UNIT_TEXT.get(trimmed, trimmed)
    return "", f" {shown}" if shown else "", 1


def _scaled(value: float, scale: float) -> float:
    return round(value * scale, 6)


def _indian_groups(whole: str) -> str:
    if len(whole) <= 3:
        return whole
    head, tail = whole[:-3], whole[-3:]
    groups = [head[max(0, end - 2) : end] for end in range(len(head), 0, -2)]
    return ",".join([*reversed(groups), tail])


def _runs(months: Sequence[int]) -> list[tuple[int, ...]]:
    runs: list[list[int]] = []
    for month in months:
        if runs and month == runs[-1][-1] + 1:
            runs[-1].append(month)
        else:
            runs.append([month])
    return [(run[0],) if len(run) == 1 else (run[0], run[-1]) for run in runs]
