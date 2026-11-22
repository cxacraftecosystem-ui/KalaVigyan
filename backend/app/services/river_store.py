from __future__ import annotations

from collections.abc import Collection, Sequence
from dataclasses import dataclass

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.geo.river_trace import (
    TRACE_REACHES_MAX,
    DistrictHit,
    ReachLink,
    RiverNetworkError,
    districts_in_path_order,
    river_trace,
    traced_reach_ids,
)
from app.models import EnvDataset, RiverBasin, RiverReach, RiverReachDistrict
from app.research.rivers import RiverTrace, trace_problems

__all__ = [
    "BASIN_REACHES_MAX",
    "RIVERS_CROSSING_MAX",
    "BasinFile",
    "RiverCrossing",
    "basin_file",
    "basin_links",
    "district_hits",
    "named_crossing",
    "rivers_crossing",
    "rivers_loaded",
    "stored_trace_problems",
    "trace_river",
]

BASIN_REACHES_MAX = 250_000
RIVERS_CROSSING_MAX = 5

DISTRICT_HITS = text(
    """
    SELECT p.ord AS position, h."districtLgd" AS district_lgd, h."entry" AS entry
    FROM unnest(CAST(:reach_ids AS integer[])) WITH ORDINALITY AS p(id, ord)
    JOIN "RiverReachDistrict" h ON h."hyrivId" = p.id
    """
)

RIVERS_CROSSING = text(
    """
    SELECT main_riv, hyriv_id, upland_skm, ord_stra, dis_av_cms FROM (
        SELECT DISTINCT ON (r."mainRiv") r."mainRiv" AS main_riv, r."hyrivId" AS hyriv_id,
               r."uplandSkm" AS upland_skm, r."ordStra" AS ord_stra, r."disAvCms" AS dis_av_cms
        FROM "RiverReach" r
        JOIN "RiverReachDistrict" h ON h."hyrivId" = r."hyrivId"
        WHERE h."districtLgd" = ANY(CAST(:district_lgds AS integer[]))
        ORDER BY r."mainRiv", r."uplandSkm" DESC, r."hyrivId"
    ) crossing
    ORDER BY ord_stra DESC, dis_av_cms DESC, upland_skm DESC, main_riv
    LIMIT :limit
    """
)

NAMED_CROSSING = text(
    """
    SELECT r."mainRiv" AS main_riv, r."hyrivId" AS hyriv_id, r."uplandSkm" AS upland_skm,
           r."ordStra" AS ord_stra, r."disAvCms" AS dis_av_cms
    FROM "RiverReach" r
    JOIN "RiverReachDistrict" h ON h."hyrivId" = r."hyrivId"
    WHERE h."districtLgd" = ANY(CAST(:district_lgds AS integer[]))
      AND r."hyrivId" = ANY(CAST(:reach_ids AS integer[]))
    ORDER BY r."uplandSkm" DESC, r."hyrivId"
    LIMIT 1
    """
)

PATH_LINKS = text(
    """
    SELECT "hyrivId" AS hyriv_id, "nextDown" AS next_down, "mainRiv" AS main_riv, "uplandSkm" AS upland_skm
    FROM "RiverReach"
    WHERE "hyrivId" = ANY(CAST(:reach_ids AS integer[])) OR "nextDown" = :headwater
    """
)


@dataclass(frozen=True)
class RiverCrossing:
    main_riv: int
    hyriv_id: int
    upland_skm: float
    ord_stra: int
    dis_av_cms: float


@dataclass(frozen=True)
class BasinFile:
    main_riv: int
    edition: str
    sha256: str


async def basin_links(session: AsyncSession, reach_id: int) -> dict[int, ReachLink]:
    basin = select(RiverReach.mainRiv).where(RiverReach.hyrivId == reach_id).scalar_subquery()
    statement = (
        select(RiverReach.hyrivId, RiverReach.nextDown, RiverReach.mainRiv, RiverReach.uplandSkm)
        .where(RiverReach.mainRiv == basin)
        .limit(BASIN_REACHES_MAX + 1)
    )
    rows = (await session.execute(statement)).all()
    if len(rows) > BASIN_REACHES_MAX:
        raise RiverNetworkError(f"the river of reach {reach_id} has more than {BASIN_REACHES_MAX} reaches")
    return {
        row[0]: ReachLink(hyriv_id=row[0], next_down=row[1], main_riv=row[2], upland_skm=row[3])
        for row in rows
    }


async def district_hits(session: AsyncSession, reach_ids: Sequence[int]) -> list[DistrictHit]:
    if len(reach_ids) > TRACE_REACHES_MAX:
        raise RiverNetworkError(f"a traced river holds at most {TRACE_REACHES_MAX} reaches")
    rows = (await session.execute(DISTRICT_HITS, {"reach_ids": list(reach_ids)})).all()
    return [
        DistrictHit(position=row.position, district_lgd=row.district_lgd, entry=row.entry) for row in rows
    ]


async def trace_river(
    session: AsyncSession, reach_id: int, *, named: Collection[int] = ()
) -> RiverTrace | None:
    links = await basin_links(session, reach_id)
    if not links:
        return None
    path = traced_reach_ids(reach_id, links, named=named)
    districts = districts_in_path_order(await district_hits(session, path))
    return river_trace(path, links, districts)


async def rivers_crossing(
    session: AsyncSession, district_lgds: Sequence[int], *, limit: int = RIVERS_CROSSING_MAX
) -> list[RiverCrossing]:
    if not district_lgds:
        return []
    found = await session.execute(RIVERS_CROSSING, {"district_lgds": list(district_lgds), "limit": limit})
    return [
        RiverCrossing(
            main_riv=r.main_riv,
            hyriv_id=r.hyriv_id,
            upland_skm=r.upland_skm,
            ord_stra=r.ord_stra,
            dis_av_cms=r.dis_av_cms,
        )
        for r in found
    ]


async def named_crossing(
    session: AsyncSession, district_lgds: Sequence[int], reach_ids: Sequence[int]
) -> RiverCrossing | None:
    if not district_lgds or not reach_ids:
        return None
    params = {"district_lgds": list(district_lgds), "reach_ids": list(reach_ids)}
    row = (await session.execute(NAMED_CROSSING, params)).first()
    if row is None:
        return None
    return RiverCrossing(
        main_riv=row.main_riv,
        hyriv_id=row.hyriv_id,
        upland_skm=row.upland_skm,
        ord_stra=row.ord_stra,
        dis_av_cms=row.dis_av_cms,
    )


async def rivers_loaded(session: AsyncSession) -> bool:
    return (await session.scalar(select(RiverReachDistrict.hyrivId).limit(1))) is not None


async def stored_trace_problems(session: AsyncSession, trace: RiverTrace) -> list[str]:
    if len(trace.reach_ids) > TRACE_REACHES_MAX:
        return [f"a traced river holds at most {TRACE_REACHES_MAX} reaches"]
    params = {"reach_ids": list(trace.reach_ids), "headwater": trace.reach_ids[0]}
    rows = (await session.execute(PATH_LINKS, params)).all()
    links = {
        row.hyriv_id: ReachLink(
            hyriv_id=row.hyriv_id, next_down=row.next_down, main_riv=row.main_riv, upland_skm=row.upland_skm
        )
        for row in rows
    }
    return trace_problems(trace, links)


async def basin_file(session: AsyncSession, main_riv: int) -> BasinFile | None:
    statement = (
        select(RiverBasin.mainRiv, EnvDataset.edition, RiverBasin.topologySha256)
        .join(EnvDataset, EnvDataset.id == RiverBasin.datasetId)
        .where(RiverBasin.mainRiv == main_riv)
    )
    row = (await session.execute(statement)).first()
    if row is None or not row.edition:
        return None
    return BasinFile(main_riv=row.mainRiv, edition=row.edition, sha256=row.topologySha256)
