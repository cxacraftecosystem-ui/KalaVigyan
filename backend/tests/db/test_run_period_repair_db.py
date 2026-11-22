import uuid
from collections.abc import AsyncIterator

import pytest
from sqlalchemy import delete, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_engine
from app.models import DistrictEnvValue, EnvDataset

from ..migration_scripts import migration

pytestmark = pytest.mark.db

KACHCHH = 449
OVERWRITTEN = "set per run"


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


def dataset(code: str, period: str) -> EnvDataset:
    return EnvDataset(id=uuid.uuid4(), code=code, title=code, licence="CC BY 4.0", period=period)


def trend(dataset_id: uuid.UUID, period: str) -> DistrictEnvValue:
    return DistrictEnvValue(
        districtLgd=KACHCHH,
        datasetId=dataset_id,
        variable="annual_precipitation",
        depthOrPeriod=period,
        stat="TREND_PER_DECADE",
        value=70.76,
        unit="mm/year per decade",
    )


async def test_a_period_the_registry_overwrote_is_restored_from_the_loaded_trend(
    session: AsyncSession,
) -> None:
    chirps = dataset("CHIRPS_3_0", OVERWRITTEN)
    ghcn = dataset("GHCN_CAMS_T2M", "1981-2025")
    soil = dataset("SOILGRIDS_2_0", OVERWRITTEN)
    session.add_all([chirps, ghcn, soil])
    await session.flush()
    session.add_all([trend(chirps.id, "1981-2024"), trend(chirps.id, "1981-2025"), trend(soil.id, "2020")])
    await session.flush()
    await session.execute(text(migration("0077_state_and_reach_districts").RUN_PERIOD_REPAIR))
    periods = dict((await session.execute(select(EnvDataset.code, EnvDataset.period))).all())
    assert periods == {"CHIRPS_3_0": "1981-2025", "GHCN_CAMS_T2M": "1981-2025", "SOILGRIDS_2_0": OVERWRITTEN}
