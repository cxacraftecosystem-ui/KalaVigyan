from __future__ import annotations

import uuid
from collections.abc import Collection, Iterable, Sequence
from typing import Any

from sqlalchemy import (
    CTE,
    ColumnElement,
    Float,
    Row,
    String,
    Text,
    and_,
    case,
    cast,
    distinct,
    func,
    literal,
    not_,
    null,
    select,
)
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased
from sqlalchemy.sql.selectable import Subquery

from app.geo.aggregation import ABSENT_MEANS_ZERO, AGGREGATED_STATS
from app.geo.places import practice_states, region_places
from app.geo.records import (
    GEOLOGY_STAT,
    GEOLOGY_UNIT,
    GEOLOGY_VARIABLE,
    LITHOLOGY_TWIN_PREFIX,
    Coverage,
    DatasetRecord,
    LocationRecord,
    PlaceRecord,
    RegionRecords,
    SeriesTotals,
    StateRecord,
    ValueRecord,
)
from app.models import (
    AdminDistrict,
    AdminState,
    Craft,
    CraftLocation,
    DistrictEnvValue,
    DistrictGeology,
    EnvDataset,
    Source,
)
from app.research.citations import SourceRef
from app.research.crafts import CraftRef
from app.research.retrieval import RESTRICTED_SENSITIVITY
from app.services.dataset_registry import dataset_record
from app.services.knowledge_view import craft_ref, source_ref

__all__ = [
    "craft_places",
    "dataset_records",
    "district_places",
    "district_values",
    "located_places",
    "region_records",
    "region_values",
]


async def craft_places(session: AsyncSession, craft: Craft) -> tuple[PlaceRecord, ...]:
    known = {name.casefold(): StateRecord(lgd, name) for lgd, name in await _states(session)}
    return region_places(await _locations(session, craft), practice_states(craft.stateOfPractice, known))


async def region_records(session: AsyncSession, craft: Craft) -> RegionRecords:
    places = await craft_places(session, craft)
    own = [place for place in places if place.values_from == "DISTRICT"]
    districts = sorted({place.district_lgd for place in own if place.district_lgd is not None})
    states = sorted({place.state.lgd for place in places if place.values_from == "STATE"})
    values = await district_values(session, districts)
    totals = await _state_totals(session, states)
    codes = {row.dataset_code for row in values} | {row.dataset_code for row in totals}
    return RegionRecords(
        craft=CraftRef.model_validate(craft_ref(craft)),
        places=places,
        district_values=values,
        state_totals=totals,
        coverage=await _coverage(session, states),
        district_totals=await _district_totals(session, states),
        datasets=await dataset_records(session, codes),
        sources=await _place_sources(session, places),
    )


async def district_places(session: AsyncSession, craft: Craft) -> tuple[PlaceRecord, ...]:
    places = region_places(await _locations(session, craft), ())
    return tuple(place for place in places if place.scope == "DISTRICT" and place.district_lgd is not None)


async def dataset_records(session: AsyncSession, codes: Iterable[str]) -> dict[str, DatasetRecord]:
    wanted = sorted(set(codes))
    if not wanted:
        return {}
    rows = (await session.scalars(select(EnvDataset).where(EnvDataset.code.in_(wanted)))).all()
    return {row.code: dataset_record(row) for row in rows}


def region_values() -> Subquery:
    stored = (
        select(
            DistrictEnvValue.districtLgd.label("district_lgd"),
            EnvDataset.code.label("dataset_code"),
            DistrictEnvValue.variable.label("variable"),
            DistrictEnvValue.depthOrPeriod.label("depth_or_period"),
            cast(DistrictEnvValue.stat, Text).label("stat"),
            cast(DistrictEnvValue.value, Float).label("value"),
            DistrictEnvValue.valueText.label("value_text"),
            cast(DistrictEnvValue.unit, Text).label("unit"),
            cast(DistrictEnvValue.resolution, Text).label("resolution"),
            DistrictEnvValue.method.label("method"),
        )
        .join(EnvDataset, EnvDataset.id == DistrictEnvValue.datasetId)
        .where(not_(DistrictEnvValue.variable.startswith(LITHOLOGY_TWIN_PREFIX, autoescape=True)))
    )
    geology = (
        select(
            DistrictGeology.districtLgd,
            EnvDataset.code,
            cast(literal(GEOLOGY_VARIABLE), String),
            cast(literal(""), String),
            cast(literal(GEOLOGY_STAT), Text),
            cast(DistrictGeology.areaShare, Float),
            cast(func.coalesce(DistrictGeology.lithologyName, DistrictGeology.lithology), Text),
            cast(literal(GEOLOGY_UNIT), Text),
            cast(null(), Text),
            DistrictGeology.method,
        )
        .join(EnvDataset, EnvDataset.id == DistrictGeology.datasetId)
        .where(DistrictGeology.areaShare.is_not(None))
    )
    return stored.union_all(geology).subquery("region_value")


async def _place_sources(session: AsyncSession, places: Iterable[PlaceRecord]) -> dict[str, SourceRef]:
    wanted = sorted({uuid.UUID(place.source_id) for place in places if place.source_id})
    if not wanted:
        return {}
    statement = select(Source).where(Source.id.in_(wanted), Source.sensitivity != RESTRICTED_SENSITIVITY)
    rows = (await session.scalars(statement)).all()
    return {str(row.id): SourceRef.model_validate(source_ref(row)) for row in rows}


async def _states(session: AsyncSession) -> Sequence[tuple[int, str]]:
    return [
        (lgd, name) for lgd, name in (await session.execute(select(AdminState.lgd, AdminState.name))).all()
    ]


async def _locations(session: AsyncSession, craft: Craft) -> list[LocationRecord]:
    located = located_places(CraftLocation.craftId == craft.id)
    district, state = aliased(AdminDistrict), aliased(AdminState)
    statement = (
        select(
            located,
            district.name.label("district_name"),
            district.geom.is_not(None).label("has_polygon"),
            state.lgd.label("state_lgd"),
            state.name.label("state_name"),
            Source.id.label("visible_source_id"),
            Source.title.label("source_title"),
        )
        .select_from(located)
        .outerjoin(district, district.lgd == located.c.located_lgd)
        .outerjoin(state, state.lgd == func.coalesce(district.stateLgd, located.c.stateLgd))
        .outerjoin(
            Source, and_(Source.id == located.c.sourceId, Source.sensitivity != RESTRICTED_SENSITIVITY)
        )
    )
    return [_location(row) for row in (await session.execute(statement)).all()]


def located_places(condition: ColumnElement[bool]) -> Subquery:
    holder = (
        select(AdminDistrict.lgd)
        .where(
            AdminDistrict.geom.is_not(None),
            func.ST_Covers(AdminDistrict.geom, func.geometry(CraftLocation.geom)),
        )
        .order_by(AdminDistrict.lgd)
        .limit(1)
        .correlate(CraftLocation)
        .scalar_subquery()
    )
    district_lgd = case(
        (CraftLocation.precision == "POINT", func.coalesce(holder, CraftLocation.districtLgd)),
        else_=CraftLocation.districtLgd,
    )
    return (
        select(
            CraftLocation.id,
            CraftLocation.craftId,
            CraftLocation.precision,
            CraftLocation.placeLabel,
            CraftLocation.evidenceLevel,
            CraftLocation.sourceId,
            CraftLocation.stateLgd,
            CraftLocation.role,
            district_lgd.label("located_lgd"),
        )
        .where(condition)
        .subquery("located")
    )


def _location(row: Row[Any]) -> LocationRecord:
    found = row._mapping
    return LocationRecord(
        id=str(found["id"]),
        precision=found["precision"],
        state=StateRecord(found["state_lgd"], found["state_name"])
        if found["state_lgd"] is not None
        else None,
        district_lgd=found["located_lgd"] if found["district_name"] is not None else None,
        district_name=found["district_name"],
        has_polygon=bool(found["has_polygon"]) if found["district_name"] is not None else False,
        place_label=found["placeLabel"],
        source_id=str(found["visible_source_id"]) if found["visible_source_id"] is not None else None,
        source_title=found["source_title"],
        level=found["evidenceLevel"],
    )


async def district_values(
    session: AsyncSession, districts: Sequence[int], *, codes: Collection[str] | None = None
) -> tuple[ValueRecord, ...]:
    if not districts:
        return ()
    values = region_values()
    statement = select(values).where(values.c.district_lgd.in_(districts))
    if codes is not None:
        statement = statement.where(values.c.dataset_code.in_(sorted(codes)))
    rows = (await session.execute(statement)).all()
    return tuple(
        ValueRecord(
            district_lgd=row.district_lgd,
            dataset_code=row.dataset_code,
            variable=row.variable,
            depth_or_period=row.depth_or_period,
            stat=row.stat,
            value=row.value,
            value_text=row.value_text,
            unit=row.unit,
            resolution=row.resolution,
            method=row.method,
        )
        for row in rows
    )


def _district_areas(states: Sequence[int]) -> CTE:
    return (
        select(
            AdminDistrict.lgd.label("lgd"),
            AdminDistrict.stateLgd.label("state_lgd"),
            func.ST_Area(func.geography(AdminDistrict.geom), False).label("area"),
        )
        .where(AdminDistrict.geom.is_not(None), AdminDistrict.stateLgd.in_(states))
        .cte("district_area")
        .prefix_with("MATERIALIZED")
    )


async def _state_totals(session: AsyncSession, states: Sequence[int]) -> tuple[SeriesTotals, ...]:
    if not states:
        return ()
    values, area = region_values(), _district_areas(states)
    series = (
        area.c.state_lgd,
        values.c.dataset_code,
        values.c.variable,
        values.c.depth_or_period,
        values.c.stat,
        values.c.unit,
        values.c.value_text,
    )
    statement = (
        select(
            *series,
            func.count().label("districts"),
            func.sum(area.c.area * values.c.value).label("weighted_sum"),
            func.sum(area.c.area).label("area"),
            func.sum(values.c.value).label("total"),
            func.min(values.c.value).label("low"),
            func.max(values.c.value).label("high"),
            func.array_agg(distinct(values.c.resolution)).label("resolutions"),
            func.array_agg(distinct(values.c.method)).label("methods"),
        )
        .select_from(values)
        .join(area, area.c.lgd == values.c.district_lgd)
        .where(values.c.value.is_not(None), values.c.stat.in_(AGGREGATED_STATS))
        .group_by(*series)
    )
    return tuple(_series(row) for row in (await session.execute(statement)).all())


def _series(row: Row[Any]) -> SeriesTotals:
    found = row._mapping
    return SeriesTotals(
        state_lgd=found["state_lgd"],
        dataset_code=found["dataset_code"],
        variable=found["variable"],
        depth_or_period=found["depth_or_period"],
        stat=found["stat"],
        unit=found["unit"],
        value_text=found["value_text"],
        districts=int(found["districts"]),
        weighted_sum=float(found["weighted_sum"]),
        area=float(found["area"]),
        total=float(found["total"]),
        low=float(found["low"]),
        high=float(found["high"]),
        resolutions=tuple(found["resolutions"] or ()),
        methods=tuple(method for method in found["methods"] or () if method),
    )


async def _coverage(session: AsyncSession, states: Sequence[int]) -> tuple[Coverage, ...]:
    if not states:
        return ()
    values, area = region_values(), _district_areas(states)
    present = (
        select(area.c.state_lgd, values.c.dataset_code, values.c.district_lgd, area.c.area)
        .select_from(values)
        .join(area, area.c.lgd == values.c.district_lgd)
        .where(values.c.dataset_code.in_(tuple(ABSENT_MEANS_ZERO)))
        .distinct()
        .subquery("present")
    )
    statement = select(
        present.c.state_lgd, present.c.dataset_code, func.count(), func.sum(present.c.area)
    ).group_by(present.c.state_lgd, present.c.dataset_code)
    return tuple(
        Coverage(state_lgd=lgd, dataset_code=code, districts=int(count), area=float(total))
        for lgd, code, count, total in (await session.execute(statement)).all()
    )


async def _district_totals(session: AsyncSession, states: Sequence[int]) -> dict[int, int]:
    if not states:
        return {}
    statement = (
        select(AdminDistrict.stateLgd, func.count())
        .where(AdminDistrict.stateLgd.in_(states))
        .group_by(AdminDistrict.stateLgd)
    )
    return {lgd: int(count) for lgd, count in (await session.execute(statement)).all()}
