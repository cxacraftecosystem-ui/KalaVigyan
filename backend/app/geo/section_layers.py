from __future__ import annotations

from collections.abc import Mapping, Sequence
from types import MappingProxyType

from app.geo.layer_terms import layer_marker, layer_terms
from app.geo.layers import MAP_LAYERS
from app.research.blocks_place import MapLayerBlock
from app.schemas.region import MapLayer

__all__ = [
    "SECTION_LAYER_FACETS",
    "STORY_LAYER_FACETS",
    "map_layer_block",
    "named_layers",
    "section_layer_order",
]

SECTION_LAYER_FACETS: Mapping[str, tuple[str, ...]] = MappingProxyType(
    {"GEOLOGY": ("SOIL", "GEOLOGY", "TERRAIN"), "CLIMATE": ("CLIMATE",)}
)
STORY_LAYER_FACETS = frozenset({"WATER", "CLIMATE", "SOIL", "GEOLOGY", "TERRAIN"})


def section_layer_order(discipline: str, texts: Sequence[str]) -> list[str]:
    facets = SECTION_LAYER_FACETS.get(discipline, ())
    candidates = [spec.id for spec in MAP_LAYERS if spec.facet in facets]
    named = named_layers(texts)
    return sorted(candidates, key=lambda layer: (named.get(layer, len(texts)), candidates.index(layer)))


def named_layers(texts: Sequence[str]) -> dict[str, int]:
    marker, layer_of = layer_marker(), layer_terms().layer_of()
    named: dict[str, int] = {}
    for position, text in enumerate(texts):
        for span in marker.spans(text):
            named.setdefault(layer_of[span.term_key], position)
    return named


def map_layer_block(layer: MapLayer, highlighted: Sequence[int], *, block_id: str) -> MapLayerBlock:
    return MapLayerBlock(
        id=block_id,
        kind="map_layer",
        version=1,
        reuse=None,
        layer=layer.layer.id,
        layer_version=layer.version,
        title=layer.layer.title,
        datasets=[layer.dataset, layer.boundary.dataset],
        highlighted=list(highlighted),
        boundary_caption=layer.boundary.caption,
    )
