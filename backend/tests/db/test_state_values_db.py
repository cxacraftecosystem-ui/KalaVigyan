import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import DistrictGeology, EnvDataset, StateEnvValue
from app.services.state_values import refresh_state_values

from .test_region_db import (
    AHMEDABAD,
    GLIM,
    KACHCHH,
    areas,
    env_row,
    refresh_states,
    session,
    stat_row,
    store_datasets,
)

__all__ = ["session"]

pytestmark = pytest.mark.db

GUJARAT = 24
StoredSeries = tuple[str, str, int, float, float, float, float, float, int, float]


async def stored_series(session: AsyncSession) -> dict[tuple[str, str, str], StoredSeries]:
    statement = select(StateEnvValue, EnvDataset.code).join(
        EnvDataset, EnvDataset.id == StateEnvValue.datasetId
    )
    rows = (await session.execute(statement)).all()
    assert {row.stateLgd for row, _ in rows} <= {GUJARAT}
    return {
        (code, row.variable, row.stat): (
            row.depthOrPeriod,
            row.unit,
            row.districts,
            row.weightedSum,
            row.area,
            row.total,
            row.low,
            row.high,
            row.datasetDistricts,
            row.datasetArea,
        )
        for row, code in rows
    }


async def store_two_districts(session: AsyncSession) -> None:
    ids = await store_datasets(session)
    rows = (
        stat_row(KACHCHH, ("SOILGRIDS_2_0", "phh2o", "DISTRICT_MEAN"), 8.1, "pH"),
        stat_row(AHMEDABAD, ("SOILGRIDS_2_0", "phh2o", "DISTRICT_MEAN"), 7.8, "pH"),
        stat_row(KACHCHH, ("SOILGRIDS_2_0", "phh2o", "DISTRICT_P10"), 7.5, "pH"),
        stat_row(KACHCHH, ("USGS_MRDS", "mineral_occurrences", "COUNT"), 2.0, "sites"),
        stat_row(AHMEDABAD, ("USGS_MRDS", "mineral_occurrences", "COUNT"), 0.0, "sites"),
        stat_row(KACHCHH, ("USGS_MRDS", "mineral_occurrences_au", "COUNT"), 2.0, "sites"),
        stat_row(KACHCHH, (GLIM, "lithology_su", "SHARE"), 1.0, "fraction"),
    )
    session.add_all(env_row(ids, row) for row in rows)
    session.add(DistrictGeology(districtLgd=KACHCHH, datasetId=ids[GLIM], lithology="su", areaShare=1.0))
    await session.flush()


async def test_the_load_s_refresh_stores_each_state_series_with_its_dataset_s_coverage(
    session: AsyncSession,
) -> None:
    await store_two_districts(session)
    await refresh_states(session)
    weights = await areas(session, [KACHCHH, AHMEDABAD])
    kachchh, ahmedabad = weights[KACHCHH], weights[AHMEDABAD]
    both = kachchh + ahmedabad
    assert await stored_series(session) == {
        ("SOILGRIDS_2_0", "phh2o", "DISTRICT_MEAN"): (
            "0-5cm",
            "pH",
            2,
            pytest.approx(kachchh * 8.1 + ahmedabad * 7.8),
            pytest.approx(both),
            pytest.approx(15.9),
            7.8,
            8.1,
            2,
            pytest.approx(both),
        ),
        ("USGS_MRDS", "mineral_occurrences", "COUNT"): (
            "",
            "sites",
            2,
            2 * kachchh,
            both,
            2.0,
            0.0,
            2.0,
            2,
            both,
        ),
        ("USGS_MRDS", "mineral_occurrences_au", "COUNT"): (
            "",
            "sites",
            1,
            2 * kachchh,
            kachchh,
            2.0,
            2.0,
            2.0,
            2,
            both,
        ),
        (GLIM, "lithology", "SHARE"): ("", "fraction", 1, kachchh, kachchh, 1.0, 1.0, 1.0, 1, kachchh),
    }


async def test_a_second_refresh_replaces_the_series_instead_of_adding_to_them(session: AsyncSession) -> None:
    await store_two_districts(session)
    await refresh_states(session)
    first = await stored_series(session)
    await refresh_states(session)
    assert await stored_series(session) == first
    assert (await session.execute(select(func.count()).select_from(StateEnvValue))).scalar_one() == len(first)


async def test_the_backend_s_refresh_stores_what_the_load_s_file_stores(session: AsyncSession) -> None:
    await store_two_districts(session)
    await refresh_states(session)
    from_file = await stored_series(session)
    assert await refresh_state_values(session) == len(from_file)
    assert await stored_series(session) == from_file
