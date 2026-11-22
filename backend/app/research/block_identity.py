from __future__ import annotations

from collections.abc import Callable, Collection, Mapping
from types import MappingProxyType

from .blocks import BlockBase
from .blocks_matter import MaterialCardBlock, Molecule3dBlock, ReactionPlayerBlock
from .blocks_place import MapLayerBlock, RegionStoryBlock

__all__ = ["block_keys", "repeats_shown"]


def _map_layer(block: MapLayerBlock) -> frozenset[str]:
    return frozenset({f"map_layer:{block.layer}"})


def _region_story(block: RegionStoryBlock) -> frozenset[str]:
    if block.river is not None:
        return frozenset({f"region_story:river:{block.river.main_riv}"})
    return frozenset(f"region_story:district:{district.district_lgd}" for district in block.districts)


def _reaction_player(block: ReactionPlayerBlock) -> frozenset[str]:
    return frozenset(f"reaction:{step.reaction_id}" for step in block.steps)


def _molecule(block: Molecule3dBlock) -> frozenset[str]:
    return frozenset({f"molecule_3d:{block.compound_id}"})


def _material_card(block: MaterialCardBlock) -> frozenset[str]:
    held = block.material_id or block.compound_id or block.term_key
    named = f"id:{held}" if held is not None else f"name:{block.name.casefold()}"
    return frozenset({f"material_card:{named}"})


KEYS_BY_KIND: Mapping[type[BlockBase], Callable[..., frozenset[str]]] = MappingProxyType(
    {
        MapLayerBlock: _map_layer,
        RegionStoryBlock: _region_story,
        ReactionPlayerBlock: _reaction_player,
        Molecule3dBlock: _molecule,
        MaterialCardBlock: _material_card,
    }
)


def block_keys(block: BlockBase) -> frozenset[str] | None:
    keys = KEYS_BY_KIND.get(type(block))
    return None if keys is None else keys(block)


def repeats_shown(block: BlockBase, shown: Collection[str]) -> bool:
    keys = block_keys(block)
    return keys is not None and keys <= set(shown)
