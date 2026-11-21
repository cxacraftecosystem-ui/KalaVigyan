from app.geo.ground_readings import cited_readings, reading_codes
from app.geo.records import DatasetRecord, ValueRecord

CHIRPS, SOIL, COVER = "CHIRPS_3_0", "SOILGRIDS_2_0", "ESA_WORLDCOVER_2021_V200"


def dataset(code: str, period: str, grid: str | None) -> DatasetRecord:
    return DatasetRecord(
        code=code,
        title=f"{code} title",
        publisher="A publisher",
        edition="1",
        period=period,
        native_resolution=grid,
        licence="CC BY 4.0",
        licence_url=None,
        attribution=None,
        citation=None,
        url=None,
    )


def value(
    lgd: int, code: str, variable: str, stored: str, reading: tuple[str, float | None, str]
) -> ValueRecord:
    stat, number, unit = reading
    return ValueRecord(lgd, code, variable, stored, stat, number, None, unit, None, None)


DATASETS = {
    CHIRPS: dataset(CHIRPS, "1981-2025", "0.05 degree"),
    SOIL: dataset(SOIL, "2020", "250 m"),
    COVER: dataset(COVER, "2021", "10 m"),
}
ROWS = (
    value(449, COVER, "landcover_cropland", "2021", ("SHARE", 0.236, "fraction")),
    value(449, SOIL, "clay", "0-5cm", ("DISTRICT_MEAN", 27.4, "%")),
    value(449, CHIRPS, "annual_precipitation", "1981-2025", ("NORMAL", 449.0, "mm")),
    value(449, CHIRPS, "annual_precipitation", "1981-2025", ("TREND_PER_DECADE", 70.8, "mm/decade")),
    value(449, SOIL, "phh2o", "0-5cm", ("DISTRICT_MEAN", None, "pH")),
    value(123, SOIL, "phh2o", "0-5cm", ("DISTRICT_MEAN", 7.2, "pH")),
)


def test_the_readings_come_from_rainfall_soil_and_cover_datasets() -> None:
    assert reading_codes() == {CHIRPS, SOIL, COVER}


def test_each_district_lists_its_rainfall_soil_and_cover_in_that_order_with_its_dataset() -> None:
    readings, datasets = cited_readings(ROWS, DATASETS)
    shown = {
        lgd: [(r.reading, r.variable, r.depth, r.period, r.value, r.unit, r.resolution) for r in rows]
        for lgd, rows in readings.items()
    }
    assert shown == {
        449: [
            ("rainfall", "annual_precipitation", None, "1981-2025", 449.0, "mm", "0.05 degree"),
            ("soil", "clay", "0-5cm", "2020", 27.4, "%", "250 m"),
            ("cover", "landcover_cropland", None, "2021", 0.236, "fraction", "10 m"),
        ],
        123: [("soil", "phh2o", "0-5cm", "2020", 7.2, "pH", "250 m")],
    }
    assert [ref.code for ref in datasets] == [CHIRPS, COVER, SOIL]


def test_a_dataset_without_its_record_gives_no_reading() -> None:
    readings, datasets = cited_readings(ROWS, {SOIL: DATASETS[SOIL]})
    assert {lgd: [r.variable for r in rows] for lgd, rows in readings.items()} == {
        449: ["clay"],
        123: ["phh2o"],
    }
    assert [ref.code for ref in datasets] == [SOIL]
