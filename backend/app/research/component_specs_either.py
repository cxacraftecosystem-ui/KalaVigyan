from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType
from typing import Annotated, Any

from pydantic import BaseModel, Discriminator, RootModel, Tag

from .base import ContractModel
from .component_specs_data import ChartSpec, FactTableSpec, TimelineSpec
from .component_specs_data_maps import MapLayerSpec
from .component_specs_general import (
    GENERAL_CHART,
    GENERAL_MAP_LAYER,
    GENERAL_TABLE,
    GENERAL_TIMELINE,
    GeneralChartSpec,
    GeneralMapLayerSpec,
    GeneralTableSpec,
    GeneralTimelineSpec,
    is_declared,
)

__all__ = [
    "AUTHORED",
    "DECLARED",
    "EITHER_FORMS",
    "SPEC_MODELS_EITHER",
    "ChartKindSpec",
    "FactTableKindSpec",
    "MapLayerKindSpec",
    "TimelineKindSpec",
    "form_model",
    "spec_form",
]

AUTHORED = "authored"
DECLARED = "declared"


def spec_form(value: Any) -> str:
    return DECLARED if is_declared(value) else AUTHORED


class ChartKindSpec(
    RootModel[
        Annotated[
            Annotated[GeneralChartSpec, Tag(DECLARED)] | Annotated[ChartSpec, Tag(AUTHORED)],
            Discriminator(spec_form),
        ]
    ]
):
    pass


class FactTableKindSpec(
    RootModel[
        Annotated[
            Annotated[GeneralTableSpec, Tag(DECLARED)] | Annotated[FactTableSpec, Tag(AUTHORED)],
            Discriminator(spec_form),
        ]
    ]
):
    pass


class TimelineKindSpec(
    RootModel[
        Annotated[
            Annotated[GeneralTimelineSpec, Tag(DECLARED)] | Annotated[TimelineSpec, Tag(AUTHORED)],
            Discriminator(spec_form),
        ]
    ]
):
    pass


class MapLayerKindSpec(
    RootModel[
        Annotated[
            Annotated[GeneralMapLayerSpec, Tag(DECLARED)] | Annotated[MapLayerSpec, Tag(AUTHORED)],
            Discriminator(spec_form),
        ]
    ]
):
    pass


EITHER_FORMS: Mapping[str, Mapping[str, type[ContractModel]]] = MappingProxyType(
    {
        GENERAL_CHART: MappingProxyType({DECLARED: GeneralChartSpec, AUTHORED: ChartSpec}),
        GENERAL_TABLE: MappingProxyType({DECLARED: GeneralTableSpec, AUTHORED: FactTableSpec}),
        GENERAL_TIMELINE: MappingProxyType({DECLARED: GeneralTimelineSpec, AUTHORED: TimelineSpec}),
        GENERAL_MAP_LAYER: MappingProxyType({DECLARED: GeneralMapLayerSpec, AUTHORED: MapLayerSpec}),
    }
)
SPEC_MODELS_EITHER: Mapping[str, type[BaseModel]] = MappingProxyType(
    {
        GENERAL_CHART: ChartKindSpec,
        GENERAL_TABLE: FactTableKindSpec,
        GENERAL_TIMELINE: TimelineKindSpec,
        GENERAL_MAP_LAYER: MapLayerKindSpec,
    }
)


def form_model(kind: str, spec: Any) -> type[ContractModel] | None:
    forms = EITHER_FORMS.get(kind)
    return None if forms is None else forms[spec_form(spec)]
