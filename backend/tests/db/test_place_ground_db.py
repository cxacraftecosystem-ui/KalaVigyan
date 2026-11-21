import dataclasses
import uuid
from collections.abc import AsyncIterator

import pytest
from geoalchemy2 import WKTElement
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_engine
from app.geo.ground_layers import Deposit
from app.geo.place_ground import direct_measures
from app.models import (
    AdminDistrict,
    AdminState,
    Craft,
    CraftLocation,
    Material,
    Process,
    ProcessStage,
    Source,
    StageMaterial,
)
from app.services import place_ground as service

from ..geo.ground_fixtures import fixture_layers

pytestmark = pytest.mark.db

STATE, DISTRICT = 990, 990001
SPOT = (60.5, 10.5)
ELSEWHERE = (61.2, 11.2)
CRAFT = uuid.UUID("9e0d0000-0000-4000-8000-000000000001")
OPEN_SOURCE = uuid.UUID("9e0d0000-0000-4000-8000-000000000002")
HIDDEN_SOURCE = uuid.UUID("9e0d0000-0000-4000-8000-000000000003")
PROCESS = uuid.UUID("9e0d0000-0000-4000-8000-000000000004")
STAGE = uuid.UUID("9e0d0000-0000-4000-8000-000000000005")
MATERIALS = (
    (uuid.UUID("9e0d0000-0000-4000-8000-000000000011"), "Ground test iron filings", "METAL", "INPUT"),
    (uuid.UUID("9e0d0000-0000-4000-8000-000000000012"), "Ground test river clay", "CLAY", "INPUT"),
    (uuid.UUID("9e0d0000-0000-4000-8000-000000000013"), "Ground test iron hammer", "METAL", "TOOL"),
)


@pytest.fixture
async def session() -> AsyncIterator[AsyncSession]:
    async with get_engine().connect() as connection:
        transaction = await connection.begin()
        try:
            session = AsyncSession(bind=connection, expire_on_commit=False, autoflush=False)
            yield session
            await session.close()
        finally:
            await transaction.rollback()


@pytest.fixture(autouse=True)
def iron_nearby(monkeypatch: pytest.MonkeyPatch) -> None:
    iron = Deposit(7, "Near iron", SPOT[0], SPOT[1] + 0.1, 0, "Occurrence", ("Iron",))
    layers = dataclasses.replace(fixture_layers(), deposits=(iron,))
    monkeypatch.setattr(service, "ground_measures", lambda: direct_measures(layers))


def point(longitude: float, latitude: float) -> WKTElement:
    return WKTElement(f"POINT({longitude} {latitude})", srid=4326)


def district_square() -> WKTElement:
    west, south, east, north = SPOT[0] - 0.5, SPOT[1] - 0.5, SPOT[0] + 0.5, SPOT[1] + 0.5
    ring = f"{west} {south}, {east} {south}, {east} {north}, {west} {north}, {west} {south}"
    return WKTElement(f"MULTIPOLYGON((({ring})))", srid=4326)


def located(role: str, source: uuid.UUID, at: tuple[float, float]) -> CraftLocation:
    return CraftLocation(
        craftId=CRAFT,
        precision="POINT",
        geom=point(*at),
        placeLabel="Test forge village",
        sourceId=source,
        role=role,
        evidenceLevel="PROVISIONAL",
    )


async def seed(session: AsyncSession) -> Craft:
    session.add(AdminState(lgd=STATE, name="Ground Test State"))
    await session.flush()
    session.add(
        AdminDistrict(lgd=DISTRICT, stateLgd=STATE, name="Ground Test District", geom=district_square())
    )
    session.add_all(
        [
            Source(id=OPEN_SOURCE, kind="PAPER", title="Where the forge is", url="https://example.org/forge"),
            Source(id=HIDDEN_SOURCE, kind="PAPER", title="A field note", sensitivity="RESTRICTED"),
        ]
    )
    craft = Craft(id=CRAFT, slug="Ground-Test-Iron-Craft", name="Ground test iron craft")
    session.add(craft)
    await session.flush()
    session.add_all(
        [
            located("PRACTISED", OPEN_SOURCE, SPOT),
            located("ORIGIN", OPEN_SOURCE, SPOT),
            located("PRACTISED", HIDDEN_SOURCE, ELSEWHERE),
        ]
    )
    await _materials(session)
    return craft


async def _materials(session: AsyncSession) -> None:
    session.add(Process(id=PROCESS, craftId=CRAFT, name="Forging"))
    await session.flush()
    session.add(ProcessStage(id=STAGE, processId=PROCESS, ordinal=1, name="Heat and hammer"))
    session.add_all(
        Material(id=key, name=name, nameNorm=name.lower(), kind=kind) for key, name, kind, _ in MATERIALS
    )
    await session.flush()
    session.add_all(StageMaterial(stageId=STAGE, materialId=key, role=role) for key, _, _, role in MATERIALS)
    await session.flush()


async def test_a_craft_s_open_places_are_measured_once_each_with_their_district_and_materials(
    session: AsyncSession,
) -> None:
    craft = await seed(session)
    ground = await service.craft_ground_of(session, craft)
    assert ground is not None
    [place] = ground.places
    assert (place.name, place.roles, place.precision) == (
        "Test forge village",
        ["PRACTISED", "ORIGIN"],
        "POINT",
    )
    assert (place.district, place.state, place.longitude, place.latitude) == (
        "Ground Test District",
        "Ground Test State",
        60.5,
        10.5,
    )
    assert [(m.material, m.count, m.nearest_km) for m in place.materials] == [
        ("Ground test iron filings", 1, 11.1)
    ]
    assert ground.soil_materials == ["Ground test river clay"]
    assert [(d.dep_id, d.matched) for d in ground.deposits] == [(7, True)]
    assert [source.id for source in ground.sources] == [str(OPEN_SOURCE)]


async def test_the_map_reads_the_ground_only_at_a_craft_place(session: AsyncSession) -> None:
    await seed(session)
    found = await service.map_ground_at(session, SPOT)
    assert found is not None
    assert (found.district, found.ground.deposit_total) == ("Ground Test District", 1)
    assert await service.map_ground_at(session, (SPOT[0] + 0.3, SPOT[1])) is None


async def test_a_craft_without_an_open_place_has_no_ground(session: AsyncSession) -> None:
    craft = await seed(session)
    await session.execute(delete(CraftLocation).where(CraftLocation.sourceId == OPEN_SOURCE))
    assert await service.craft_ground_of(session, craft) is None
    assert await service.subject_ground(session, CRAFT) is None
