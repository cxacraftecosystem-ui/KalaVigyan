import uuid
from collections.abc import AsyncIterator, Sequence

import pytest
from geoalchemy2 import WKTElement
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AdminDistrict, AdminState, Craft, CraftLocation, Source
from app.services.place_offers import mapped_districts

from .testimony_seed import rolled_back_session

pytestmark = pytest.mark.db

GUJARAT, UTTAR_PRADESH = 24, 9
KACHCHH, AZAMGARH = 449, 123
JOURNAL = uuid.UUID("9e1b0000-0000-4000-8000-000000000001")


def square(west: float) -> WKTElement:
    east = west + 1.0
    ring = f"{west} 23.0, {east} 23.0, {east} 24.0, {west} 24.0, {west} 23.0"
    return WKTElement(f"MULTIPOLYGON((({ring})))", srid=4326)


@pytest.fixture
async def session() -> AsyncIterator[AsyncSession]:
    async for opened in rolled_back_session():
        await opened.merge(AdminState(lgd=GUJARAT, name="Gujarat"))
        await opened.merge(AdminState(lgd=UTTAR_PRADESH, name="Uttar Pradesh"))
        await opened.flush()
        await opened.merge(AdminDistrict(lgd=KACHCHH, stateLgd=GUJARAT, name="Kachchh", geom=square(69.0)))
        await opened.merge(
            AdminDistrict(lgd=AZAMGARH, stateLgd=UTTAR_PRADESH, name="Azamgarh", geom=square(83.0))
        )
        opened.add(Source(id=JOURNAL, kind="PAPER", title="A journal naming both districts", year=2013))
        await opened.flush()
        yield opened


async def located_craft(session: AsyncSession, slug: str, states: Sequence[str]) -> Craft:
    craft = Craft(id=uuid.uuid4(), slug=slug, name=slug.replace("-", " "), stateOfPractice=list(states))
    session.add(craft)
    await session.flush()
    session.add_all(
        CraftLocation(
            id=uuid.uuid4(),
            craftId=craft.id,
            precision="DISTRICT",
            districtLgd=district,
            sourceId=JOURNAL,
            evidenceLevel="PROVISIONAL",
        )
        for district in (KACHCHH, AZAMGARH)
    )
    await session.flush()
    return craft


async def test_a_craft_s_own_maps_and_climate_keep_to_the_districts_of_its_states_of_practice(
    session: AsyncSession,
) -> None:
    pottery = await located_craft(session, "Practised-Test-Azamgarh-Pottery", ["Uttar Pradesh"])
    assert await mapped_districts(session, pottery) == (AZAMGARH,)


async def test_a_craft_practised_in_both_states_keeps_both_districts(session: AsyncSession) -> None:
    craft = await located_craft(session, "Practised-Test-Two-State-Craft", ["Gujarat", "Uttar Pradesh"])
    assert set(await mapped_districts(session, craft)) == {KACHCHH, AZAMGARH}


async def test_a_craft_naming_no_known_state_keeps_every_located_district(session: AsyncSession) -> None:
    craft = await located_craft(session, "Practised-Test-Anywhere-Craft", ["All India"])
    assert set(await mapped_districts(session, craft)) == {KACHCHH, AZAMGARH}
