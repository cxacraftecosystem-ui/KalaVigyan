from __future__ import annotations

import logging
from collections.abc import Collection, Sequence
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.geo.datasets import region_dataset
from app.geo.layers import LAYERS_BY_ID
from app.geo.records import LayerValues
from app.geo.river_trace import RiverNetworkError
from app.geo.section_layers import STORY_LAYER_FACETS, section_layer_order
from app.models import AdminDistrict, AdminState, Craft
from app.research.blocks_place import DistrictRef

from .component_places import practised_states
from .knowledge_view import resolve_craft
from .map_layer_store import district_layers, layer_values
from .region_records import district_places
from .region_story import LayerOffer, OfferedRiver, RegionOffer
from .river_store import rivers_crossing, trace_river

__all__ = [
    "REGION_RIVERS_MAX",
    "SectionLayer",
    "district_refs",
    "mapped_districts",
    "offered_rivers",
    "region_offer",
    "section_map_layer",
]

logger = logging.getLogger(__name__)

REGION_RIVERS_MAX = 3


@dataclass(frozen=True)
class SectionLayer:
    values: LayerValues
    highlighted: tuple[int, ...]


async def mapped_districts(session: AsyncSession, craft: Craft) -> tuple[int, ...]:
    places = await district_places(session, craft)
    practised = practised_states(craft.stateOfPractice or ())
    return tuple(
        dict.fromkeys(
            place.district_lgd
            for place in places
            if place.has_polygon and place.district_lgd and (not practised or place.state.lgd in practised)
        )
    )


async def region_offer(session: AsyncSession, craft_slug: str) -> RegionOffer | None:
    craft = await resolve_craft(session, craft_slug)
    lgds = await mapped_districts(session, craft) if craft is not None else ()
    if not lgds:
        return None
    rivers = await offered_rivers(session, lgds)
    named = [*lgds, *(lgd for river in rivers for lgd in river.trace.district_lgds)]
    layers = await district_layers(session, lgds)
    offered = tuple(
        LayerOffer(layer_id, spec.title, spec.dataset_code)
        for layer_id in layers.districts
        if (spec := LAYERS_BY_ID[layer_id]).facet in STORY_LAYER_FACETS
    )
    return RegionOffer(
        craft_districts=lgds,
        rivers=rivers,
        districts=await district_refs(session, dict.fromkeys(named)),
        layers=offered,
        datasets={code: region_dataset(record) for code, record in layers.datasets.items()},
    )


async def offered_rivers(session: AsyncSession, district_lgds: Sequence[int]) -> tuple[OfferedRiver, ...]:
    found: list[OfferedRiver] = []
    for crossing in await rivers_crossing(session, district_lgds, limit=REGION_RIVERS_MAX):
        try:
            trace = await trace_river(session, crossing.hyriv_id)
        except RiverNetworkError as broken:
            logger.warning("river %s is not offered: %s", crossing.main_riv, broken)
            continue
        if trace is not None:
            found.append(OfferedRiver(f"r{len(found) + 1}", trace, crossing.ord_stra, crossing.dis_av_cms))
    return tuple(found)


async def district_refs(session: AsyncSession, district_lgds: Collection[int]) -> dict[int, DistrictRef]:
    if not district_lgds:
        return {}
    statement = (
        select(AdminDistrict.lgd, AdminDistrict.name, AdminState.name)
        .join(AdminState, AdminState.lgd == AdminDistrict.stateLgd)
        .where(AdminDistrict.lgd.in_(list(district_lgds)))
    )
    rows = (await session.execute(statement)).all()
    return {lgd: DistrictRef(district_lgd=lgd, name=name, state_name=state) for lgd, name, state in rows}


async def section_map_layer(
    session: AsyncSession, craft_slug: str, discipline: str, texts: Sequence[str]
) -> SectionLayer | None:
    craft = await resolve_craft(session, craft_slug)
    lgds = await mapped_districts(session, craft) if craft is not None else ()
    if not lgds:
        return None
    layers = await district_layers(session, lgds)
    for layer_id in section_layer_order(discipline, texts):
        highlighted = layers.districts.get(layer_id)
        if not highlighted:
            continue
        values = await layer_values(session, LAYERS_BY_ID[layer_id])
        if values is not None:
            return SectionLayer(values=values, highlighted=highlighted)
    return None
