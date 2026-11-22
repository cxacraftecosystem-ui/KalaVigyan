import pytest

from app.core.errors import InvalidInput
from app.geo.aggregation import ABSENT_MEANS_ZERO, StateAggregate, absent_means_zero, state_aggregate
from app.geo.records import LITHOLOGY_TWIN_PREFIX, SeriesTotals

GUJARAT = 24


def series(stat: str, values: dict[int, tuple[float, float]], **changes: object) -> SeriesTotals:
    areas = [area for area, _ in values.values()]
    readings = [value for _, value in values.values()]
    fields: dict[str, object] = {
        "state_lgd": GUJARAT,
        "dataset_code": "SOILGRIDS_2_0",
        "variable": "phh2o",
        "depth_or_period": "0-5cm",
        "stat": stat,
        "unit": "pH",
        "value_text": None,
        "districts": len(values),
        "weighted_sum": sum(area * value for area, value in values.values()),
        "area": sum(areas),
        "total": sum(readings),
        "low": min(readings),
        "high": max(readings),
        "resolutions": (None,),
        "methods": (),
        "dataset_districts": len(values),
        "dataset_area": sum(areas),
    }
    return SeriesTotals(**(fields | changes))


THREE = {449: (45_652.0, 8.1), 438: (8_707.0, 7.8), 444: (1_764.0, 6.4)}


def test_a_mean_is_weighted_by_district_area() -> None:
    expected = round((45_652 * 8.1 + 8_707 * 7.8 + 1_764 * 6.4) / (45_652 + 8_707 + 1_764), 6)
    assert expected == 8.000025
    assert state_aggregate(series("DISTRICT_MEAN", THREE)) == StateAggregate("STATE_AREA_MEAN", expected, 3)


@pytest.mark.parametrize(
    ("stat", "aggregation", "value"),
    [
        ("NORMAL", "STATE_AREA_MEAN", 8.000025),
        ("SHARE", "STATE_AREA_MEAN", 8.000025),
        ("DENSITY", "STATE_AREA_MEAN", 8.000025),
        ("TOTAL", "STATE_SUM", 22.3),
        ("COUNT", "STATE_SUM", 22.3),
        ("DISTRICT_MIN", "STATE_MIN", 6.4),
        ("DISTRICT_MAX", "STATE_MAX", 8.1),
    ],
)
def test_each_stat_aggregates_to_a_state_its_own_way(stat: str, aggregation: str, value: float) -> None:
    assert state_aggregate(series(stat, THREE)) == StateAggregate(aggregation, value, 3)


@pytest.mark.parametrize(
    "stat", ["DISTRICT_P10", "DISTRICT_P90", "UNCERTAINTY_Q05_MEAN", "CLASS", "DISTANCE"]
)
def test_percentiles_bounds_classes_and_distances_have_no_state_aggregate(stat: str) -> None:
    with pytest.raises(InvalidInput, match="no state aggregate"):
        state_aggregate(series(stat, THREE))


def test_a_rock_type_absent_from_a_covered_district_counts_as_none_of_its_area() -> None:
    sandstone = series(
        "SHARE",
        {449: (3.0, 0.5)},
        dataset_code="GLIM_1_0_05DEG",
        variable="lithology",
        depth_or_period="",
        unit="fraction",
        value_text="Siliciclastic sedimentary rocks",
        dataset_districts=2,
        dataset_area=4.0,
    )
    assert state_aggregate(sandstone) == StateAggregate("STATE_AREA_MEAN", 0.375, 2)


def test_mineral_sites_of_one_commodity_sum_over_every_covered_district() -> None:
    gold = series(
        "COUNT",
        {449: (3.0, 2.0), 438: (1.0, 1.0)},
        dataset_code="USGS_MRDS",
        variable="mineral_occurrences_au",
        dataset_districts=33,
        dataset_area=196_000.0,
    )
    assert state_aggregate(gold) == StateAggregate("STATE_SUM", 3.0, 33)


def test_a_sparse_series_whose_dataset_covers_fewer_districts_fails_loudly() -> None:
    sparse = series(
        "SHARE",
        {449: (3.0, 0.5), 438: (1.0, 0.2)},
        dataset_code="GLIM_1_0_05DEG",
        variable="lithology",
        dataset_districts=1,
        dataset_area=3.0,
    )
    with pytest.raises(InvalidInput, match="covers fewer districts"):
        state_aggregate(sparse)


def test_a_zero_where_a_rock_type_is_absent_lowers_the_state_minimum_to_zero() -> None:
    sparse = series(
        "DISTRICT_MIN",
        {449: (3.0, 0.5)},
        dataset_code="GLIM_1_0_05DEG",
        variable="lithology",
        dataset_districts=2,
        dataset_area=4.0,
    )
    assert state_aggregate(sparse) == StateAggregate("STATE_MIN", 0.0, 2)


def test_only_class_shares_and_commodity_counts_treat_absence_as_zero() -> None:
    assert absent_means_zero("GLIM_1_0_05DEG", "lithology")
    assert absent_means_zero("USGS_MRDS", "mineral_occurrences_cu")
    assert not absent_means_zero("USGS_MRDS", "mineral_occurrences")
    assert not absent_means_zero("ESA_WORLDCOVER_2021_V200", "landcover_cropland")


def test_a_mean_over_no_area_fails_loudly() -> None:
    with pytest.raises(InvalidInput, match="no district area"):
        state_aggregate(series("DISTRICT_MEAN", {449: (0.0, 8.1)}))


def test_the_two_rules_are_read_from_the_file_the_etl_contract_test_reads() -> None:
    assert LITHOLOGY_TWIN_PREFIX == "lithology_"
    assert dict(ABSENT_MEANS_ZERO) == {"GLIM_1_0_05DEG": "lithology", "USGS_MRDS": "mineral_occurrences_"}
