from __future__ import annotations

from .base import ContractModel
from .datasets import DatasetRef
from .map_layer_proposals import MapLayerPlan

__all__ = ["LayerBounds", "LayerReview", "layer_checks"]

LICENCE_CHECK = "Its licence is open and lets anyone redistribute the data"
CRS_CHECK = "It is in WGS 84 longitude and latitude (EPSG:4326)"
FRAME_CHECK = "Every coordinate lies inside India's frame, at the precision the map keeps"
VALUE_CHECK = "Every feature gives its {property} as a number, or null where it has no reading"
POINT_CHECK = "Points, never simplified"
SIMPLIFIED_CHECK = "Simplified to {simplified:g} degree, within the {allowed:g} its layer class allows"
METHOD_CHECK = "Its method names no interpolation or smoothing"


class LayerBounds(ContractModel):
    west: float
    south: float
    east: float
    north: float


class LayerReview(ContractModel):
    dataset: DatasetRef
    plan: MapLayerPlan
    geometry: str
    features: int
    byte_size: int
    bounds: LayerBounds
    checks: list[str]


def layer_checks(plan: MapLayerPlan) -> list[str]:
    allowed = plan.kind.tolerance
    shaped = (
        POINT_CHECK
        if allowed is None
        else SIMPLIFIED_CHECK.format(simplified=plan.simplified_to or 0.0, allowed=allowed)
    )
    valued = [VALUE_CHECK.format(property=plan.value_property)] if plan.value_property else []
    return [LICENCE_CHECK, CRS_CHECK, shaped, FRAME_CHECK, *valued, METHOD_CHECK]
