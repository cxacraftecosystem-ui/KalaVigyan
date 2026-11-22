import uuid
from collections.abc import AsyncIterator
from typing import Any

import httpx
import pytest
from geoalchemy2 import WKTElement
from sqlalchemy import delete
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_engine, get_session
from app.core.deps import get_current_user, get_optional_user
from app.main import app
from app.models import (
    AdminDistrict,
    AdminState,
    DistrictEnvValue,
    EnvDataset,
    RiverBasin,
    RiverReach,
    RiverReachDistrict,
    User,
)
from app.research.blocks_place import DistrictRef
from app.services.monthly_rain import district_rainfall
from app.services.river_store import (
    BasinFile,
    RiverCrossing,
    basin_file,
    named_crossing,
    rivers_crossing,
    rivers_loaded,
    trace_river,
)

from ..readers import sign_in_as

pytestmark = pytest.mark.db

STATE = 99901
WEST, MIDDLE, EAST = 99911, 99912, 99913
SOURCE_A, SOURCE_B, JUNCTION, OUTLET, COAST = 90000001, 90000002, 90000003, 90000004, 90000010
SHA = "a" * 64
HITS = (
    (SOURCE_A, WEST, 0.0),
    (SOURCE_B, MIDDLE, 0.0),
    (SOURCE_B, WEST, 0.7143),
    (JUNCTION, WEST, 0.0),
    (JUNCTION, MIDDLE, 0.2857),
    (OUTLET, MIDDLE, 0.0),
    (OUTLET, EAST, 0.5),
    (COAST, EAST, 0.0),
)
MONTHLY_MM = [0.4, 0.9, 0.3, 0.2, 2.1, 38.5, 141.2, 112.6, 61.3, 9.8, 2.4, 0.6]


def district_ref(lgd: int) -> DistrictRef:
    return DistrictRef(district_lgd=lgd, name=f"Test {lgd}", state_name="Test Ocean State")


def square(west: float) -> WKTElement:
    east = west + 1.0
    ring = f"{west} -30.5, {east} -30.5, {east} -29.5, {west} -29.5, {west} -30.5"
    return WKTElement(f"MULTIPOLYGON((({ring})))", srid=4326)


def reach(hyriv_id: int, next_down: int, main_riv: int, line: str, upland: float) -> RiverReach:
    return RiverReach(
        hyrivId=hyriv_id,
        nextDown=next_down,
        mainRiv=main_riv,
        ordStra=2,
        uplandSkm=upland,
        disAvCms=0.4,
        lengthKm=50.0,
        geom=WKTElement(f"LINESTRING({line})", srid=4326),
    )


def crossing(main_riv: int, hyriv_id: int, upland: float) -> RiverCrossing:
    return RiverCrossing(main_riv=main_riv, hyriv_id=hyriv_id, upland_skm=upland, ord_stra=2, dis_av_cms=0.4)


def dataset(code: str, edition: str, period: str) -> EnvDataset:
    return EnvDataset(
        id=uuid.uuid4(),
        code=code,
        title=code,
        edition=edition,
        period=period,
        nativeResolution="0.05 degree",
        licence="CC BY 4.0",
    )


@pytest.fixture
async def session() -> AsyncIterator[AsyncSession]:
    async with get_engine().connect() as connection:
        transaction = await connection.begin()
        try:
            session = AsyncSession(bind=connection, expire_on_commit=False, autoflush=False)
            await session.execute(delete(RiverBasin))
            await session.execute(
                delete(EnvDataset).where(EnvDataset.code.in_(["HYDRORIVERS_1_0", "CHIRPS_3_0"]))
            )
            await store_network(session)
            yield session
            await session.close()
        finally:
            await transaction.rollback()


async def store_network(session: AsyncSession) -> None:
    session.add(AdminState(lgd=STATE, name="Test Ocean State"))
    await session.flush()
    session.add_all(
        AdminDistrict(lgd=lgd, stateLgd=STATE, name=f"Test {lgd}", geom=square(west))
        for lgd, west in ((WEST, 60.0), (MIDDLE, 61.0), (EAST, 62.0))
    )
    rivers = dataset("HYDRORIVERS_1_0", "v10", "static")
    session.add(rivers)
    await session.flush()
    session.add_all(
        RiverBasin(mainRiv=main, datasetId=rivers.id, reachCount=count, topologySha256=SHA)
        for main, count in ((OUTLET, 4), (COAST, 1))
    )
    await session.flush()
    session.add_all(
        [
            reach(SOURCE_A, JUNCTION, OUTLET, "60.2 -29.8, 60.8 -30.0", 120.0),
            reach(SOURCE_B, JUNCTION, OUTLET, "61.5 -29.6, 60.8 -30.0", 200.0),
            reach(JUNCTION, OUTLET, OUTLET, "60.8 -30.0, 61.5 -30.0", 400.0),
            reach(OUTLET, 0, OUTLET, "61.5 -30.0, 62.5 -30.0", 600.0),
            reach(COAST, 0, COAST, "62.2 -29.8, 62.4 -29.9", 150.0),
        ]
    )
    await session.flush()
    session.add_all(RiverReachDistrict(hyrivId=rid, districtLgd=lgd, entry=entry) for rid, lgd, entry in HITS)
    await session.flush()


async def test_the_main_stem_is_traced_from_the_outlet_with_districts_in_path_order(
    session: AsyncSession,
) -> None:
    trace = await trace_river(session, OUTLET)
    assert trace is not None
    assert (trace.main_riv, trace.reach_ids) == (OUTLET, [SOURCE_B, JUNCTION, OUTLET])
    assert trace.district_lgds == [MIDDLE, WEST, EAST]


async def test_a_tributary_is_traced_from_its_own_source_to_the_mouth(session: AsyncSession) -> None:
    trace = await trace_river(session, SOURCE_A)
    assert trace is not None
    assert trace.reach_ids == [SOURCE_A, JUNCTION, OUTLET]
    assert trace.district_lgds == [WEST, MIDDLE, EAST]
    assert await trace_river(session, 12345) is None


async def test_rivers_crossing_districts_offer_each_basin_by_its_largest_reach(session: AsyncSession) -> None:
    assert await rivers_crossing(session, [WEST]) == [crossing(OUTLET, JUNCTION, 400.0)]
    assert await rivers_crossing(session, [EAST]) == [
        crossing(OUTLET, OUTLET, 600.0),
        crossing(COAST, COAST, 150.0),
    ]
    assert await rivers_crossing(session, [EAST], limit=1) == [crossing(OUTLET, OUTLET, 600.0)]
    assert await rivers_crossing(session, []) == []


async def test_a_named_river_is_traced_up_its_own_reaches_and_crossed_where_it_is_largest(
    session: AsyncSession,
) -> None:
    trace = await trace_river(session, OUTLET, named=[SOURCE_A, JUNCTION, OUTLET])
    assert trace is not None and trace.reach_ids == [SOURCE_A, JUNCTION, OUTLET]
    assert await named_crossing(session, [WEST], [SOURCE_A, JUNCTION]) == crossing(OUTLET, JUNCTION, 400.0)
    assert await named_crossing(session, [EAST], [SOURCE_A, JUNCTION]) is None
    assert await named_crossing(session, [WEST], []) is None


async def test_rivers_are_loaded_only_with_the_districts_each_reach_crosses(session: AsyncSession) -> None:
    assert await rivers_loaded(session) is True
    await session.execute(delete(RiverReachDistrict))
    assert await rivers_loaded(session) is False


async def test_a_basin_file_names_its_edition_and_hash(session: AsyncSession) -> None:
    assert await basin_file(session, OUTLET) == BasinFile(main_riv=OUTLET, edition="v10", sha256=SHA)
    assert await basin_file(session, SOURCE_A) is None


async def test_the_database_refuses_a_reach_that_breaks_the_outlet_rule(session: AsyncSession) -> None:
    with pytest.raises(IntegrityError, match="RiverReach_outlet_check"):
        async with session.begin_nested():
            session.add(reach(90000099, 0, OUTLET, "61.1 -30.1, 61.2 -30.2", 130.0))
            await session.flush()


async def test_the_basin_route_revalidates_from_the_stored_hash(session: AsyncSession) -> None:
    async def this_session() -> AsyncIterator[Any]:
        yield session

    reader = User(id=uuid.uuid4(), name="Reader", email="reader@example.com", role="STUDENT")
    app.dependency_overrides[get_session] = this_session
    sign_in_as(app, lambda: reader)
    try:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            same = await client.get(
                f"/api/rivers/{OUTLET}", headers={"If-None-Match": f'"{SHA}"', "Accept-Encoding": "identity"}
            )
            unknown = await client.get(f"/api/rivers/{SOURCE_A}")
    finally:
        app.dependency_overrides.pop(get_session, None)
        app.dependency_overrides.pop(get_current_user, None)
        app.dependency_overrides.pop(get_optional_user, None)
    assert (same.status_code, same.headers["etag"]) == (304, f'"{SHA}"')
    assert unknown.status_code == 404


async def test_twelve_stored_monthly_normals_are_the_district_s_rainfall(session: AsyncSession) -> None:
    chirps = dataset("CHIRPS_3_0", "3.0", "2016-2025")
    session.add(chirps)
    await session.flush()
    session.add_all(
        DistrictEnvValue(
            districtLgd=WEST,
            datasetId=chirps.id,
            variable="monthly_precipitation",
            depthOrPeriod=f"2016-2025-{month:02d}",
            stat="NORMAL",
            value=value,
            unit="mm/month",
            resolution="0.05 degree",
        )
        for month, value in enumerate(MONTHLY_MM, start=1)
    )
    await session.flush()
    found = await district_rainfall(session, district_ref(WEST))
    assert found is not None
    assert (found.rain.period, found.rain.millimetres) == ("2016-2025", MONTHLY_MM)
    assert (found.dataset.code, found.dataset.native_resolution) == ("CHIRPS_3_0", "0.05 degree")
    assert await district_rainfall(session, district_ref(MIDDLE)) is None
    await session.execute(
        delete(DistrictEnvValue).where(
            DistrictEnvValue.districtLgd == WEST, DistrictEnvValue.depthOrPeriod == "2016-2025-07"
        )
    )
    assert await district_rainfall(session, district_ref(WEST)) is None
