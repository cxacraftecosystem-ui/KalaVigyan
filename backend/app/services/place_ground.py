from __future__ import annotations

import json
import logging
import uuid
from collections.abc import Mapping, Sequence
from dataclasses import replace
from functools import lru_cache
from typing import Any

from pydantic import ValidationError
from sqlalchemy import Float, Row, and_, cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.core.errors import InvalidInput
from app.data.map_layers import LAYERS_DIR, MINERALS_FILE, RELIEF_FILE, RIVERS_FILE
from app.data.river_names import NamedRiver, load_river_names, place_river
from app.geo.datasets import region_dataset, registry_row_ref
from app.geo.ground_frame import framed
from app.geo.ground_layers import GroundLayers, ground_layers
from app.geo.ground_materials import CraftMaterial
from app.geo.ground_readings import cited_readings, reading_codes
from app.geo.place_ground import (
    GroundInputs,
    LocatedPlace,
    Measured,
    Measures,
    craft_ground,
    map_place_ground,
    measured,
)
from app.models import (
    AdminDistrict,
    AdminState,
    Craft,
    CraftLocation,
    CuratedCraft,
    Material,
    Process,
    ProcessStage,
    Source,
    StageMaterial,
)
from app.models.science import live_process
from app.research.citations import SourceRef
from app.research.crafts import CraftRef
from app.research.datasets import DatasetRef
from app.research.place_ground import PLACE_PRECISIONS, MapPlaceGround
from app.research.retrieval import RESTRICTED_SENSITIVITY
from app.research.rivers import HYDRORIVERS_DATASET_CODE
from app.research.vocabulary import PLACE_ROLES
from app.research.why_here import CraftGround, GroundFrame, GroundPin, GroundRiver

from .chapter_context import PlacePoint
from .chapter_records import place_points
from .curated_index import IndexPlace, stored_curated_page
from .knowledge_view import claims_by_id, craft_ref, source_ref
from .region_records import dataset_records, district_values, located_places

__all__ = [
    "abroad_pins",
    "craft_ground_of",
    "ground_measures",
    "ground_rivers",
    "map_ground_at",
    "name_dataset",
    "named_rivers",
    "stored_layers",
    "subject_ground",
]

logger = logging.getLogger(__name__)

PLACES_CACHED = 4096
FRAMES_CACHED = 512
DEGREE_PLACES = 3
TOOL_ROLE = "TOOL"
SRID = 4326
PLACE_TOLERANCE_DEGREES = 0.002
INDIA = "India"
RIVER_KIND = "RIVER"
ABROAD_KEY = "abroad-{wikidata_id}"
RIVER_KEY = "river-{main_riv}-{source}-{mouth}"

Box = tuple[float, float, float, float]


@lru_cache(maxsize=1)
def stored_layers() -> GroundLayers:
    def read(name: str) -> Any:
        return json.loads((LAYERS_DIR / name).read_text(encoding="utf-8"))

    return ground_layers(read(RELIEF_FILE), read(RIVERS_FILE), read(MINERALS_FILE))


@lru_cache(maxsize=PLACES_CACHED)
def _measured_at(longitude: float, latitude: float) -> Measured:
    return measured(stored_layers(), (longitude, latitude))


@lru_cache(maxsize=FRAMES_CACHED)
def _framed(box: Box) -> GroundFrame:
    return framed(stored_layers(), box)


def ground_measures() -> Measures:
    return Measures(
        layers=stored_layers(),
        at=lambda point: _measured_at(round(point[0], DEGREE_PLACES), round(point[1], DEGREE_PLACES)),
        frame=_framed,
    )


async def subject_ground(session: AsyncSession, craft_id: uuid.UUID) -> CraftGround | None:
    craft = await session.get(Craft, craft_id)
    if craft is None:
        return None
    try:
        return await craft_ground_of(session, craft)
    except (ValidationError, InvalidInput) as refused:
        logger.warning("the ground under %s was not drawn: %s", craft.slug, refused)
        return None


async def craft_ground_of(session: AsyncSession, craft: Craft) -> CraftGround | None:
    places = await _located(session, craft)
    if not places:
        return None
    districts = sorted({place.district_lgd for place in places if place.district_lgd is not None})
    codes = reading_codes()
    readings, datasets = cited_readings(
        await district_values(session, districts, codes=codes), await dataset_records(session, codes)
    )
    named = await _dossier_places(session, craft)
    inputs = GroundInputs(
        craft=CraftRef.model_validate(craft_ref(craft)),
        places=places,
        materials=await _materials(session, craft),
        readings=readings,
        datasets=tuple(datasets),
        sources=await _sources(session, [place.source_id for place in places]),
        abroad=await _abroad(session, named),
        rivers=await _rivers(session, named),
    )
    return craft_ground(inputs, ground_measures())


def abroad_pins(places: Sequence[IndexPlace], points: Mapping[str, PlacePoint]) -> tuple[GroundPin, ...]:
    held: dict[str, GroundPin] = {}
    for place in places:
        point = points.get(place.wikidata_id or "")
        if point is None:
            continue
        found = held.get(point.wikidata_id)
        roles = {*(found.roles if found else ()), place.role}
        held[point.wikidata_id] = GroundPin(
            key=ABROAD_KEY.format(wikidata_id=point.wikidata_id),
            name=found.name if found else place.name,
            roles=sorted(roles, key=PLACE_ROLES.index),
            country=place.country,
            wikidata_id=point.wikidata_id,
            longitude=round(point.longitude, DEGREE_PLACES),
            latitude=round(point.latitude, DEGREE_PLACES),
        )
    return tuple(sorted(held.values(), key=lambda pin: (pin.name.casefold(), pin.key)))


def name_dataset(code: str) -> DatasetRef | None:
    row = load_river_names().dataset(code)
    return registry_row_ref(row) if row is not None else None


def named_rivers(places: Sequence[IndexPlace]) -> tuple[NamedRiver, ...]:
    found: dict[tuple[int, tuple[int, ...]], NamedRiver] = {}
    for place in places:
        river = place_river(place.name, place.district_lgd) if place.kind == RIVER_KIND else None
        if river is not None:
            found.setdefault((river.main_riv, tuple(river.reach_ids)), river)
    return tuple(found.values())


def ground_rivers(named: Sequence[NamedRiver], datasets: Mapping[str, DatasetRef]) -> tuple[GroundRiver, ...]:
    lines = datasets.get(HYDRORIVERS_DATASET_CODE)
    rivers = []
    for river in named:
        names = datasets.get(river.dataset_code)
        if lines is None or names is None:
            logger.warning(
                "the river %s is not drawn: %s or %s has no dataset row",
                river.name,
                HYDRORIVERS_DATASET_CODE,
                river.dataset_code,
            )
            continue
        key = RIVER_KEY.format(main_riv=river.main_riv, source=river.reach_ids[0], mouth=river.reach_ids[-1])
        rivers.append(
            GroundRiver(
                key=key,
                name=river.name,
                main_riv=river.main_riv,
                reach_ids=list(river.reach_ids),
                hydrorivers=lines,
                names=names,
            )
        )
    return tuple(rivers)


async def _dossier_places(session: AsyncSession, craft: Craft) -> tuple[IndexPlace, ...]:
    page = await session.scalar(select(CuratedCraft.page).where(CuratedCraft.craftId == craft.id))
    curated = stored_curated_page(craft.id, page)
    if curated is None:
        return ()
    marked = [place for place in curated.places if place.kind == RIVER_KIND or place.country != INDIA]
    shown, _ = await claims_by_id(session, [claim for place in marked for claim in place.claim_ids])
    return tuple(place for place in marked if any(claim in shown for claim in place.claim_ids))


async def _abroad(session: AsyncSession, places: Sequence[IndexPlace]) -> tuple[GroundPin, ...]:
    wanted = [place for place in places if place.country != INDIA and place.kind != RIVER_KIND]
    points = await place_points(session, {place.wikidata_id for place in wanted if place.wikidata_id})
    return abroad_pins(wanted, points)


async def _rivers(session: AsyncSession, places: Sequence[IndexPlace]) -> tuple[GroundRiver, ...]:
    named = named_rivers(places)
    if not named:
        return ()
    lines = (await dataset_records(session, [HYDRORIVERS_DATASET_CODE])).get(HYDRORIVERS_DATASET_CODE)
    codes = {river.dataset_code for river in named}
    datasets = {code: found for code in codes if (found := name_dataset(code)) is not None}
    if lines is not None:
        datasets[HYDRORIVERS_DATASET_CODE] = region_dataset(lines)
    return ground_rivers(named, datasets)


async def map_ground_at(session: AsyncSession, point: tuple[float, float]) -> MapPlaceGround | None:
    spot = func.ST_SetSRID(func.ST_MakePoint(point[0], point[1]), SRID)
    if not await _a_craft_place(session, spot):
        return None
    holder = (
        await session.execute(
            select(AdminDistrict.lgd, AdminDistrict.name)
            .where(AdminDistrict.geom.is_not(None), func.ST_Covers(AdminDistrict.geom, spot))
            .order_by(AdminDistrict.lgd)
            .limit(1)
        )
    ).first()
    codes = reading_codes()
    values = await district_values(session, [holder.lgd], codes=codes) if holder else ()
    readings, datasets = cited_readings(values, await dataset_records(session, codes))
    found = readings.get(holder.lgd, ()) if holder else ()
    return map_place_ground(point, holder.name if holder else None, ground_measures(), (found, datasets))


async def _a_craft_place(session: AsyncSession, spot: Any) -> bool:
    located = select(CraftLocation.id).where(
        CraftLocation.precision.in_(PLACE_PRECISIONS),
        func.ST_DWithin(func.geometry(CraftLocation.geom), spot, PLACE_TOLERANCE_DEGREES),
    )
    centred = select(AdminDistrict.lgd).where(
        AdminDistrict.centroid.is_not(None),
        func.ST_DWithin(AdminDistrict.centroid, spot, PLACE_TOLERANCE_DEGREES),
    )
    found = await session.scalar(select(located.exists().label("found")))
    return bool(found) or bool(await session.scalar(select(centred.exists().label("found"))))


async def _located(session: AsyncSession, craft: Craft) -> tuple[LocatedPlace, ...]:
    located = located_places(CraftLocation.craftId == craft.id)
    district, state, holder = aliased(AdminDistrict), aliased(AdminState), aliased(CraftLocation)
    point = func.coalesce(func.geometry(holder.geom), district.centroid)
    statement = (
        select(
            located.c.id,
            located.c.precision,
            located.c.placeLabel,
            located.c.role,
            district.lgd.label("district_lgd"),
            district.name.label("district_name"),
            state.name.label("state_name"),
            cast(func.ST_X(point), Float).label("longitude"),
            cast(func.ST_Y(point), Float).label("latitude"),
            Source.id.label("source_id"),
        )
        .select_from(located)
        .join(holder, holder.id == located.c.id)
        .outerjoin(district, district.lgd == located.c.located_lgd)
        .outerjoin(state, state.lgd == func.coalesce(district.stateLgd, located.c.stateLgd))
        .join(Source, and_(Source.id == located.c.sourceId, Source.sensitivity != RESTRICTED_SENSITIVITY))
        .where(located.c.precision.in_(PLACE_PRECISIONS))
        .order_by(located.c.id)
    )
    rows = (await session.execute(statement)).all()
    return _merged([row for row in rows if row.longitude is not None and row.latitude is not None])


def _merged(rows: Sequence[Row[Any]]) -> tuple[LocatedPlace, ...]:
    places: dict[tuple[str, float, float], LocatedPlace] = {}
    for row in rows:
        name = row.placeLabel or row.district_name
        if not name:
            continue
        key = (name.casefold(), round(row.longitude, DEGREE_PLACES), round(row.latitude, DEGREE_PLACES))
        held = places.get(key)
        if held is not None:
            roles = {role for role in (*held.roles, row.role) if role}
            places[key] = replace(held, roles=tuple(sorted(roles, key=PLACE_ROLES.index)))
            continue
        places[key] = LocatedPlace(
            key=f"place-{row.id}",
            name=name,
            roles=(row.role,) if row.role else (),
            precision=row.precision,
            district=row.district_name,
            district_lgd=row.district_lgd,
            state=row.state_name,
            longitude=row.longitude,
            latitude=row.latitude,
            source_id=str(row.source_id),
        )
    return tuple(sorted(places.values(), key=lambda place: (place.name.casefold(), place.key)))


async def _materials(session: AsyncSession, craft: Craft) -> tuple[CraftMaterial, ...]:
    statement = (
        select(Material.name, Material.kind)
        .join(StageMaterial, StageMaterial.materialId == Material.id)
        .join(ProcessStage, ProcessStage.id == StageMaterial.stageId)
        .join(Process, Process.id == ProcessStage.processId)
        .where(Process.craftId == craft.id, live_process(), StageMaterial.role != TOOL_ROLE)
        .distinct()
    )
    rows = (await session.execute(statement)).all()
    return tuple(sorted({CraftMaterial(name, kind) for name, kind in rows}, key=lambda m: (m.name, m.kind)))


async def _sources(session: AsyncSession, ids: Sequence[str]) -> tuple[SourceRef, ...]:
    ordered = list(dict.fromkeys(ids))
    rows = (await session.scalars(select(Source).where(Source.id.in_([uuid.UUID(i) for i in ordered])))).all()
    found = {str(row.id): SourceRef.model_validate(source_ref(row)) for row in rows}
    return tuple(found[source_id] for source_id in ordered if source_id in found)
