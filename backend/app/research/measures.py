from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from types import MappingProxyType
from typing import Annotated, Literal

from pydantic import Field

from .datasets import DatasetRef
from .quotes import numbers_in

__all__ = [
    "CONVERSION_BASES",
    "DEFINED_UNITS",
    "METRIC_SIGNIFICANT_FIGURES",
    "METRIC_UNITS",
    "UNIT_DEFINITIONS",
    "UNIT_KEY_PATTERN",
    "DefinedUnit",
    "MetricUnit",
    "UnitKey",
    "metric_value",
    "stated_numbers",
]

UNIT_KEY_PATTERN = r"^[a-z][a-z0-9]*(?:-[a-z0-9]+)*$"
METRIC_SIGNIFICANT_FIGURES = 3
METRIC_UNITS = ("mm", "cm", "m", "km", "m2", "ha", "g", "kg", "ml", "l")
CONVERSION_BASES = ("DEFINED", "REGIONAL")

MetricUnit = Literal[*METRIC_UNITS]
UnitKey = Annotated[str, Field(pattern=UNIT_KEY_PATTERN, max_length=40)]


@dataclass(frozen=True)
class DefinedUnit:
    metric_unit: str
    factor: Decimal
    words: tuple[str, ...] = ()


DEFINED_UNITS: Mapping[str, DefinedUnit] = MappingProxyType(
    {
        "inch": DefinedUnit("cm", Decimal("2.54"), ("inch", "inches")),
        "foot": DefinedUnit("m", Decimal("0.3048"), ("foot", "feet", "ft")),
        "yard": DefinedUnit("m", Decimal("0.9144"), ("yard", "yards", "yd", "yds")),
        "mile": DefinedUnit("km", Decimal("1.609344"), ("mile", "miles")),
        "square-foot": DefinedUnit(
            "m2", Decimal("0.09290304"), ("square foot", "square feet", "sq ft", "sq. ft.", "sq.ft.")
        ),
    }
)

UNIT_DEFINITIONS = DatasetRef(
    code="NIST_SP_811_2008",
    title="Guide for the Use of the International System of Units (SI), Appendix B: Conversion Factors",
    publisher="National Institute of Standards and Technology",
    edition="NIST Special Publication 811, 2008 edition",
    period="2008",
    native_resolution="exact conversion factors",
    licence="Not subject to copyright in the United States (U.S. Government work)",
    licence_url=None,
    attribution="Ambler Thompson and Barry N. Taylor, NIST",
    citation=(
        "Thompson, A., & Taylor, B. N. (2008). Guide for the Use of the International System of Units (SI) "
        "(NIST Special Publication 811). National Institute of Standards and Technology."
    ),
    url="https://www.nist.gov/pml/special-publication-811",
)


def metric_value(value: float, factor: float | Decimal) -> float:
    product = _decimal(value) * _decimal(factor)
    if product == 0:
        return 0.0
    step = Decimal(1).scaleb(product.adjusted() - METRIC_SIGNIFICANT_FIGURES + 1)
    return float(product.quantize(step, rounding=ROUND_HALF_UP))


def stated_numbers(text: str) -> list[Decimal]:
    return [Decimal(figure) for figure in numbers_in(text)]


def _decimal(value: float | Decimal) -> Decimal:
    return value if isinstance(value, Decimal) else Decimal(repr(value))
