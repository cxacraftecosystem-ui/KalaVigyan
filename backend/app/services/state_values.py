from __future__ import annotations

from sqlalchemy import CTE, Insert, and_, delete, distinct, func, insert, select
from sqlalchemy.dialects import postgresql
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.selectable import Subquery

from app.geo.aggregation import AGGREGATED_STATS
from app.models import AdminDistrict, StateEnvValue

from .region_records import region_values

__all__ = ["STATE_SERIES_COLUMNS", "refresh_state_values", "state_values_insert", "state_values_sql"]

PARAMSTYLE = "named"
STATE_SERIES_COLUMNS = (
    "stateLgd",
    "datasetId",
    "variable",
    "depthOrPeriod",
    "stat",
    "unit",
    "valueText",
    "districts",
    "weightedSum",
    "area",
    "total",
    "low",
    "high",
    "resolutions",
    "methods",
    "datasetDistricts",
    "datasetArea",
)


def state_values_insert() -> Insert:
    values, area = region_values(), _district_areas()
    series = _state_series(values, area)
    held = _dataset_coverage(values, area)
    rows = select(
        *(series.c[name] for name in STATE_SERIES_COLUMNS[:-2]),
        held.c.districts.label("datasetDistricts"),
        held.c.area.label("datasetArea"),
    ).join_from(
        series, held, and_(held.c.state_lgd == series.c.stateLgd, held.c.dataset_id == series.c.datasetId)
    )
    return insert(StateEnvValue).from_select(list(STATE_SERIES_COLUMNS), rows)


def state_values_sql() -> str:
    compiled = state_values_insert().compile(
        dialect=postgresql.dialect(paramstyle=PARAMSTYLE), compile_kwargs={"literal_binds": True}
    )
    return "".join(f"{line.rstrip()}\n" for line in str(compiled).splitlines())


async def refresh_state_values(session: AsyncSession) -> int:
    await session.execute(delete(StateEnvValue))
    await session.execute(state_values_insert())
    return int(await session.scalar(select(func.count()).select_from(StateEnvValue)) or 0)


def _district_areas() -> CTE:
    return (
        select(
            AdminDistrict.lgd.label("lgd"),
            AdminDistrict.stateLgd.label("state_lgd"),
            func.ST_Area(func.geography(AdminDistrict.geom), False).label("area"),
        )
        .where(AdminDistrict.geom.is_not(None))
        .cte("district_area")
        .prefix_with("MATERIALIZED")
    )


def _state_series(values: Subquery, area: CTE) -> Subquery:
    keys = (
        area.c.state_lgd.label("stateLgd"),
        values.c.dataset_id.label("datasetId"),
        values.c.variable.label("variable"),
        values.c.depth_or_period.label("depthOrPeriod"),
        values.c.stat.label("stat"),
        values.c.unit.label("unit"),
        values.c.value_text.label("valueText"),
    )
    statement = (
        select(
            *keys,
            func.count().label("districts"),
            func.sum(area.c.area * values.c.value).label("weightedSum"),
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
        .group_by(*(key.element for key in keys))
    )
    return statement.subquery("state_series")


def _dataset_coverage(values: Subquery, area: CTE) -> Subquery:
    held = (
        select(area.c.state_lgd, values.c.dataset_id, values.c.district_lgd, area.c.area)
        .select_from(values)
        .join(area, area.c.lgd == values.c.district_lgd)
        .distinct()
        .subquery("held")
    )
    return (
        select(
            held.c.state_lgd,
            held.c.dataset_id,
            func.count().label("districts"),
            func.sum(held.c.area).label("area"),
        )
        .group_by(held.c.state_lgd, held.c.dataset_id)
        .subquery("dataset_coverage")
    )
