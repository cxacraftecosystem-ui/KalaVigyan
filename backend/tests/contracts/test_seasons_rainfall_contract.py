from app.research.blocks_place import MonthlyRain, SeasonsBlock

from ..geo.golden_region import KACHCHH, kachchh_monthly_rain, kachchh_rainfall, stored_row
from .phase_b_golden import catalog_dataset, geo_etl_datasets, phase_b_blocks
from .phase_d_golden import phase_d_blocks

CHIRPS = "CHIRPS_3_0"
PERIOD = "1981-2025"
JULY = 6
JULY_STORED = 181.45751
ANNUAL_NORMAL = ("CHIRPS_3_0", "annual_precipitation", PERIOD, "NORMAL")


def rainfall() -> MonthlyRain:
    found = SeasonsBlock.model_validate(phase_b_blocks()["s3.b1"]).rainfall
    assert found is not None
    return found


def test_the_seasons_fixture_draws_kachchh_s_recorded_chirps_monthly_normals() -> None:
    rain = rainfall()
    assert (rain.district.district_lgd, rain.district.name, rain.district.state_name) == (
        449,
        "Kachchh",
        "Gujarat",
    )
    assert (rain.dataset_code, rain.period) == (CHIRPS, PERIOD)
    months = kachchh_monthly_rain()
    assert [month.depth_or_period for month in months] == [f"{PERIOD}-{n:02d}" for n in range(1, 13)]
    assert rain.millimetres == [month.value for month in months]
    assert rain.millimetres[JULY] == JULY_STORED
    assert rain == kachchh_rainfall().rain


def test_the_monthly_normals_add_up_to_the_annual_normal_the_climate_fixture_shows() -> None:
    annual = stored_row(KACHCHH, ANNUAL_NORMAL).value
    assert annual == phase_d_blocks()["s6.b1"]["trends"][0]["mean"] == 449.356389
    assert abs(sum(rainfall().millimetres) - annual) < 0.05


def test_the_seasons_fixture_cites_the_chirps_row_the_climate_fixture_cites() -> None:
    seasons = phase_b_blocks()["s3.b1"]
    expected = catalog_dataset(CHIRPS) | {"period": PERIOD, "doi": geo_etl_datasets()[CHIRPS]["doi"]}
    assert seasons["datasets"] == phase_d_blocks()["s6.b1"]["datasets"] == [expected]
    assert kachchh_rainfall().dataset.model_dump(mode="json", by_alias=True) == expected
