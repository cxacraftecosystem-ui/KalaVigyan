from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Literal

from pydantic import Field

from .base import ContractModel

__all__ = [
    "INDIA_FRAME",
    "INTERPOLATED",
    "LAYER_CLASSES",
    "LAYER_CLASS_NAMES",
    "LAYER_TYPES",
    "LINE_DECIMALS",
    "POINT_DECIMALS",
    "Frame",
    "LayerClass",
    "MapLayerPlan",
    "decimals_allowed",
    "layer_problems",
    "names_wgs84",
]

LINE_DECIMALS = 3
POINT_DECIMALS = 4
LAYER_TYPES = ("application/geo+json",)
PROPERTY_PATTERN = r"^[A-Za-z_][A-Za-z0-9_]{0,59}$"
INTERPOLATED = re.compile(r"interpolat|kriging|\bidw\b|inverse.distance|spline|smooth", re.IGNORECASE)
WGS84 = re.compile(r"\bEPSG\s*:*\s*4326\b|\bWGS\s*-?\s*84\b|\bCRS\s*84\b", re.IGNORECASE)
EPSG_CODE = re.compile(r"\bEPSG\s*:*\s*(\d+)\b", re.IGNORECASE)
WGS84_CODE = "4326"


@dataclass(frozen=True)
class LayerClass:
    geometry: str
    tolerance: float | None
    min_area: float | None = None


@dataclass(frozen=True)
class Frame:
    west: float
    south: float
    east: float
    north: float

    def holds(self, longitude: float, latitude: float) -> bool:
        return self.west <= longitude <= self.east and self.south <= latitude <= self.north


INDIA_FRAME = Frame(west=68.206, south=6.756, east=97.394, north=37.082)
LAYER_CLASSES: Mapping[str, LayerClass] = MappingProxyType(
    {
        "RIVERS": LayerClass("LINE", 0.01),
        "BASIN_REACHES": LayerClass("LINE", 0.005),
        "LAKES": LayerClass("SHAPE", 0.006, min_area=0.004),
        "COUNTRY_OUTLINES": LayerClass("SHAPE", 0.012),
        "RELIEF_BANDS": LayerClass("SHAPE", 0.018),
        "DISTRICT_SHAPES": LayerClass("SHAPE", 0.01),
        "POINT_SITES": LayerClass("POINT", None),
    }
)
LAYER_CLASS_NAMES: tuple[str, ...] = tuple(LAYER_CLASSES)


class MapLayerPlan(ContractModel):
    layer_class: Literal[*LAYER_CLASS_NAMES]
    simplified_to: float | None = Field(default=None, ge=0, le=1)
    value_property: str | None = Field(default=None, pattern=PROPERTY_PATTERN)
    variable: str | None = Field(default=None, min_length=2, max_length=120)
    unit: str | None = Field(default=None, min_length=1, max_length=40)
    method: str = Field(min_length=3, max_length=300)

    @property
    def kind(self) -> LayerClass:
        return LAYER_CLASSES[self.layer_class]


def names_wgs84(crs: str) -> bool:
    others = [code for code in EPSG_CODE.findall(crs) if code != WGS84_CODE]
    return bool(WGS84.search(crs)) and not others


def decimals_allowed(plan: MapLayerPlan) -> int:
    return POINT_DECIMALS if plan.kind.geometry == "POINT" else LINE_DECIMALS


def layer_problems(crs: str, plan: MapLayerPlan) -> list[str]:
    problems = []
    if not names_wgs84(crs):
        problems.append(f"a map layer is in WGS 84 longitude and latitude (EPSG:4326), not {crs!r}")
    problems += _simplification_problems(plan)
    if plan.value_property is not None and (plan.variable is None or plan.unit is None):
        problems.append(
            f"the value in {plan.value_property} names its variable and the unit its dataset states"
        )
    if INTERPOLATED.search(plan.method):
        problems.append(
            "a layer's values are what its dataset states for each place, never interpolated, kriged or smoothed"
        )
    return problems


def _simplification_problems(plan: MapLayerPlan) -> list[str]:
    allowed = plan.kind.tolerance
    name = plan.layer_class.lower().replace("_", " ")
    if allowed is None:
        if plan.simplified_to:
            return [f"{name} are points, and a point is never simplified"]
        return []
    if plan.simplified_to is None:
        return [f"give the tolerance the {name} were simplified to, at most {allowed:g} degree"]
    if plan.simplified_to > allowed:
        return [f"{name} are simplified no further than {allowed:g} degree, not {plan.simplified_to:g}"]
    return []
