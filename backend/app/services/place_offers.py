from __future__ import annotations

import logging
from collections.abc import Collection, Sequence
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.data.district_register import load_district_other_names
from app.data.river_names import NamedRiver, RiverNames, load_river_names, name_forms
from app.geo.datasets import region_dataset, registry_row_ref
from app.geo.layers import LAYERS_BY_ID
from app.geo.records import LayerValues
from app.geo.river_trace import RiverNetworkError
from app.geo.section_layers import STORY_LAYER_FACETS, section_layer_order
from app.models import AdminDistrict, AdminState, Craft
from app.research.blocks_place import DistrictRef
from app.research.datasets import DatasetRef

from .component_places import practised_states
from .knowledge_view import resolve_craft
from .map_layer_store import district_layers, layer_values
from .region_records import district_places
from .region_story import LayerOffer, OfferedRiver, RegionOffer
from .river_store import RiverCrossing, named_crossing, rivers_crossing, trace_river

__all__ = [
    "REGION_RIVERS_MAX",
    "SectionLayer",
    "district_refs",
    "mapped_districts",
    "name_datasets",
    "offered_rivers",
    "region_offer",
    "section_map_layer",
    "stated_crossings",
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


async def region_offer(
    session: AsyncSession, craft_slug: str, *, texts: Sequence[str] = ()
) -> RegionOffer | None:
    craft = await resolve_craft(session, craft_slug)
    lgds = await mapped_districts(session, craft) if craft is not None else ()
    if not lgds:
        return None
    rivers = await offered_rivers(session, lgds, texts=texts)
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
        datasets={
            **{code: region_dataset(record) for code, record in layers.datasets.items()},
            **name_datasets(rivers, load_river_names()),
        },
    )


async def offered_rivers(
    session: AsyncSession, district_lgds: Sequence[int], *, texts: Sequence[str] = ()
) -> tuple[OfferedRiver, ...]:
    names = load_river_names()
    crossings = [
        *await stated_crossings(session, district_lgds, names, texts),
        *await rivers_crossing(session, district_lgds, limit=REGION_RIVERS_MAX),
    ]
    found: list[OfferedRiver] = []
    for crossing in {crossing.hyriv_id: crossing for crossing in crossings}.values():
        river = await _offered(session, crossing, names.of_reach(crossing.hyriv_id), f"r{len(found) + 1}")
        if river is not None:
            found.append(river)
        if len(found) == REGION_RIVERS_MAX:
            break
    return tuple(found)


async def _offered(
    session: AsyncSession, crossing: RiverCrossing, named: NamedRiver | None, ref: str
) -> OfferedRiver | None:
    try:
        trace = await trace_river(session, crossing.hyriv_id, named=named.reach_ids if named else ())
    except RiverNetworkError as broken:
        logger.warning("river %s is not offered: %s", crossing.main_riv, broken)
        return None
    if trace is None:
        return None
    name, dataset = (named.name, named.dataset_code) if named else (None, None)
    return OfferedRiver(ref, trace, crossing.ord_stra, crossing.dis_av_cms, name=name, name_dataset=dataset)


async def stated_crossings(
    session: AsyncSession, district_lgds: Sequence[int], names: RiverNames, texts: Sequence[str]
) -> list[RiverCrossing]:
    stated = {name for text in texts for name in names.named_in(text)}
    held = set(district_lgds)
    rivers = [
        river
        for names_set in names.sets
        for river in names_set.rivers
        if held.intersection(river.district_lgds) and stated.intersection(name_forms(river.name))
    ]
    found = [await named_crossing(session, district_lgds, river.reach_ids) for river in rivers]
    return [crossing for crossing in found if crossing is not None]


def name_datasets(rivers: Sequence[OfferedRiver], names: RiverNames) -> dict[str, DatasetRef]:
    codes = dict.fromkeys(river.name_dataset for river in rivers if river.name_dataset)
    return {code: registry_row_ref(row) for code in codes if (row := names.dataset(code)) is not None}


async def district_refs(session: AsyncSession, district_lgds: Collection[int]) -> dict[int, DistrictRef]:
    if not district_lgds:
        return {}
    statement = (
        select(AdminDistrict.lgd, AdminDistrict.name, AdminState.name)
        .join(AdminState, AdminState.lgd == AdminDistrict.stateLgd)
        .where(AdminDistrict.lgd.in_(list(district_lgds)))
    )
    rows = (await session.execute(statement)).all()
    others = load_district_other_names()
    return {
        lgd: DistrictRef(district_lgd=lgd, name=name, state_name=state, other_names=list(others.get(lgd, ())))
        for lgd, name, state in rows
    }


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
