import uuid
from collections.abc import AsyncIterator

import pytest
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_engine
from app.models import Craft, CraftLocation, DistrictEnvValue, EnvDataset
from app.services.climate_store import craft_climate

from ..contracts.phase_b_golden import catalog_dataset
from ..geo.golden_region import GI_JOURNAL

pytestmark = pytest.mark.db

BAGRU = "Bagru-Hand-Block-Print"
JAIPUR = 102
CODE = "OGD_GW_RESOURCES_RAJASTHAN_2023"
GRID = "district, as in the list of districts before the reorganisation"
JAIPUR_ROWS = (
    ("annual_groundwater_recharge", "TOTAL", 72587.12, "ham"),
    ("annual_extractable_groundwater", "TOTAL", 65328.4, "ham"),
    ("annual_groundwater_extraction", "TOTAL", 147594.63, "ham"),
    ("annual_groundwater_extraction_irrigation", "TOTAL", 107004.97, "ham"),
    ("stage_of_groundwater_extraction", "SHARE", 225.93, "%"),
)


@pytest.fixture
async def session() -> AsyncIterator[AsyncSession]:
    async with get_engine().connect() as connection:
        transaction = await connection.begin()
        try:
            session = AsyncSession(bind=connection, expire_on_commit=False, autoflush=False)
            await session.execute(delete(EnvDataset))
            yield session
            await session.close()
        finally:
            await transaction.rollback()


async def locate_bagru_in_jaipur(session: AsyncSession) -> None:
    craft = (await session.execute(select(Craft).where(Craft.slug == BAGRU))).scalar_one()
    await session.execute(delete(CraftLocation).where(CraftLocation.craftId == craft.id))
    session.add(
        CraftLocation(
            id=uuid.uuid4(),
            craftId=craft.id,
            precision="DISTRICT",
            districtLgd=JAIPUR,
            sourceId=uuid.UUID(GI_JOURNAL),
            evidenceLevel="PROVISIONAL",
        )
    )


async def store_jaipur_groundwater(session: AsyncSession) -> None:
    record = catalog_dataset(CODE)
    table = EnvDataset(
        id=uuid.uuid4(),
        code=CODE,
        title=record["title"],
        edition=record["edition"],
        period=record["period"],
        nativeResolution=record["nativeResolution"],
        licence=record["licence"],
        redistributable=True,
    )
    session.add(table)
    await session.flush()
    session.add_all(
        DistrictEnvValue(
            districtLgd=JAIPUR,
            datasetId=table.id,
            variable=variable,
            depthOrPeriod="2023",
            stat=stat,
            value=value,
            unit=unit,
            resolution=GRID,
        )
        for variable, stat, value, unit in JAIPUR_ROWS
    )
    await session.flush()


async def test_the_craft_s_district_shows_its_stored_groundwater_and_cites_the_table(
    session: AsyncSession,
) -> None:
    await locate_bagru_in_jaipur(session)
    await store_jaipur_groundwater(session)
    found = await craft_climate(session, BAGRU)
    assert found.trends == ()
    assert [(v.district.district_lgd, v.variable, v.value, v.unit, v.period) for v in found.groundwater] == [
        (JAIPUR, "annual_groundwater_recharge", 72587.12, "ham", "2023"),
        (JAIPUR, "annual_extractable_groundwater", 65328.4, "ham", "2023"),
        (JAIPUR, "annual_groundwater_extraction", 147594.63, "ham", "2023"),
        (JAIPUR, "stage_of_groundwater_extraction", 225.93, "%", "2023"),
    ]
    assert {v.resolution for v in found.groundwater} == {GRID}
    assert [(row.code, row.period) for row in found.datasets] == [(CODE, "2023")]
