import pandas as pd

from geo_etl.catalog import CHIRPS, GLIM, MRDS, SOILGRIDS, Dataset
from geo_etl.coverage import EXPECTED_WITHOUT_CELLS, coverage_of
from geo_etl.layers import Result
from geo_etl.rows import Rows

STATE_OF = {11: 1, 12: 1, 21: 2, 31: 3, 32: 3}
LAKSHADWEEP = {553: 31}
MUMBAI_AND_SUBURBAN = {482: 27, 483: 27}


def selection(state_of: dict[int, int] = STATE_OF) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "districtLgd": list(state_of),
            "stateLgd": list(state_of.values()),
            "districtName": [f"d{lgd}" for lgd in state_of],
        }
    )


def result_with_values(
    lgds: list[int],
    failures: list[dict] | None = None,
    without_cells: list[int] | None = None,
    *,
    dataset: Dataset = SOILGRIDS,
    state_of: dict[int, int] = STATE_OF,
) -> Result:
    rows = Rows(dataset, "fixture")
    frame = selection(state_of).set_index("districtLgd", drop=False)
    for lgd in lgds:
        rows.add(frame.loc[lgd], "clay", "0-5cm", "DISTRICT_MEAN", 20.0, "%")
    return Result(dataset, rows.frame(), failures=failures or [], districts_without_cells=without_cells or [])


def test_full_coverage_loses_nothing():
    reach = coverage_of(selection(), result_with_values(list(STATE_OF)))
    assert reach.districts_without_values == []
    assert reach.silent_districts == []
    assert reach.lost_states == []


def test_a_scattered_district_failure_loses_no_state_and_is_not_silent():
    failures = [{"step": "worldcover", "districtLgds": [12], "error": "boom"}]
    reach = coverage_of(selection(), result_with_values([11, 21, 31, 32], failures))
    assert reach.districts_without_values == [12]
    assert reach.silent_districts == []
    assert reach.lost_states == []


def test_a_state_with_no_values_is_lost_even_without_a_failure():
    reach = coverage_of(selection(), result_with_values([11, 12, 31, 32]))
    assert reach.districts_without_values == [21]
    assert reach.silent_districts == [21]
    assert reach.lost_states == [2]


def test_a_silent_district_is_listed_when_its_state_has_another_district_with_values():
    reach = coverage_of(selection(), result_with_values([11, 21, 31, 32]))
    assert reach.districts_without_values == [12]
    assert reach.silent_districts == [12]
    assert reach.lost_states == []


def test_a_step_failed_for_every_district_of_a_state_loses_it_despite_other_values():
    failures = [{"step": "clay 0-5cm Q0.05", "districtLgds": [31, 32], "error": "boom"}]
    reach = coverage_of(selection(), result_with_values(list(STATE_OF), failures))
    assert reach.districts_without_values == []
    assert reach.lost_states == [3]


def test_a_whole_shard_failure_loses_every_state_in_it():
    failures = [{"step": "chelsa bio1 1981-2010", "districtLgds": list(STATE_OF), "error": "Mixed-type"}]
    reach = coverage_of(selection(), result_with_values([], failures))
    assert reach.districts_without_values == [11, 12, 21, 31, 32]
    assert reach.silent_districts == []
    assert reach.lost_states == [1, 2, 3]


def test_geology_rows_count_as_coverage():
    geology = pd.DataFrame({"districtLgd": [21], "datasetCode": [MRDS.code]})
    result = Result(MRDS, result_with_values([11, 12, 31, 32]).values, geology=geology)
    reach = coverage_of(selection(), result)
    assert reach.districts_without_values == []
    assert reach.silent_districts == []
    assert reach.lost_states == []


def test_a_one_district_state_without_valid_cells_is_not_lost_and_is_listed():
    reach = coverage_of(selection(), result_with_values([11, 12, 31, 32], without_cells=[21]))
    assert reach.districts_without_values == [21]
    assert reach.districts_without_cells == [21]
    assert reach.silent_districts == []
    assert reach.lost_states == []


def test_a_state_whose_districts_silently_produced_nothing_is_still_lost():
    reach = coverage_of(selection(), result_with_values([11, 12], without_cells=[21]))
    assert reach.districts_without_values == [21, 31, 32]
    assert reach.districts_without_cells == [21]
    assert reach.silent_districts == [31, 32]
    assert reach.lost_states == [3]


def test_a_failure_covering_a_whole_state_loses_it_despite_no_cells_records():
    failures = [{"step": "glim", "districtLgds": [31, 32], "error": "boom"}]
    reach = coverage_of(selection(), result_with_values([11, 12, 21], failures, without_cells=[31, 32]))
    assert reach.districts_without_values == [31, 32]
    assert reach.districts_without_cells == [31, 32]
    assert reach.silent_districts == []
    assert reach.lost_states == [3]


def test_a_district_without_cells_inside_a_covered_state_is_listed_and_loses_nothing():
    reach = coverage_of(selection(), result_with_values([11, 21, 31, 32], without_cells=[12]))
    assert reach.districts_without_values == [12]
    assert reach.districts_without_cells == [12]
    assert reach.lost_states == []


def test_a_silent_district_is_listed_even_when_another_district_of_its_state_has_no_cells():
    reach = coverage_of(selection(), result_with_values([11, 12, 21], without_cells=[31]))
    assert reach.districts_without_values == [31, 32]
    assert reach.districts_without_cells == [31]
    assert reach.silent_districts == [32]
    assert reach.lost_states == []


def test_a_no_cells_record_is_ignored_for_a_district_with_values_or_outside_the_selection():
    reach = coverage_of(selection(), result_with_values(list(STATE_OF), without_cells=[11, 99]))
    assert reach.districts_without_values == []
    assert reach.districts_without_cells == []
    assert reach.unexpected_without_cells == []
    assert reach.lost_states == []


def test_the_reviewed_districts_without_cells_are_lakshadweep_in_glim_and_mumbai_in_soilgrids():
    assert {code: sorted(reviewed) for code, reviewed in EXPECTED_WITHOUT_CELLS.items()} == {
        "GLIM_1_0_05DEG": [553],
        "SOILGRIDS_2_0": [482],
    }


def test_lakshadweep_without_glim_cells_is_expected():
    result = result_with_values([], without_cells=[553], dataset=GLIM, state_of=LAKSHADWEEP)
    reach = coverage_of(selection(LAKSHADWEEP), result)
    assert reach.districts_without_cells == [553]
    assert reach.unexpected_without_cells == []
    assert reach.silent_districts == []
    assert reach.lost_states == []


def test_mumbai_without_soilgrids_cells_is_expected_beside_mumbai_suburban_with_values():
    result = result_with_values([483], without_cells=[482], state_of=MUMBAI_AND_SUBURBAN)
    reach = coverage_of(selection(MUMBAI_AND_SUBURBAN), result)
    assert reach.districts_without_values == [482]
    assert reach.unexpected_without_cells == []
    assert reach.silent_districts == []


def test_a_district_reviewed_for_one_dataset_is_unexpected_in_another():
    result = result_with_values([], without_cells=[553], dataset=CHIRPS, state_of=LAKSHADWEEP)
    reach = coverage_of(selection(LAKSHADWEEP), result)
    assert reach.districts_without_cells == [553]
    assert reach.unexpected_without_cells == [553]
    assert reach.lost_states == []


def test_a_grid_read_as_nodata_everywhere_lists_every_district_as_unexpected():
    reach = coverage_of(selection(), result_with_values([], without_cells=list(STATE_OF)))
    assert reach.districts_without_cells == [11, 12, 21, 31, 32]
    assert reach.unexpected_without_cells == [11, 12, 21, 31, 32]
    assert reach.lost_states == []


def test_a_dataset_of_named_states_is_judged_only_over_their_districts():
    result = result_with_values([11])
    named = Result(result.dataset, result.values, states=frozenset({1}))
    reach = coverage_of(selection(), named)
    assert reach.districts_without_values == [12]
    assert reach.silent_districts == [12]
    assert reach.lost_states == []
    assert coverage_of(selection(), result).lost_states == [2, 3]
