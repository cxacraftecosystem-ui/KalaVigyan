import pytest

from app.geo.river_trace import (
    TRACE_REACHES_MAX,
    DistrictHit,
    ReachLink,
    RiverNetworkError,
    districts_in_path_order,
    river_trace,
    traced_reach_ids,
)

SOURCE_A, SOURCE_B, JUNCTION, TRIBUTARY, OUTLET = 11, 12, 13, 14, 15


def link(hyriv_id: int, next_down: int, upland: float, main_riv: int = OUTLET) -> ReachLink:
    return ReachLink(hyriv_id=hyriv_id, next_down=next_down, main_riv=main_riv, upland_skm=upland)


def branching(*extra: ReachLink) -> dict[int, ReachLink]:
    reaches = [
        link(SOURCE_A, JUNCTION, 120.0),
        link(SOURCE_B, JUNCTION, 150.0),
        link(JUNCTION, OUTLET, 300.0),
        link(TRIBUTARY, OUTLET, 450.0),
        link(OUTLET, 0, 900.0),
        *extra,
    ]
    return {reach.hyriv_id: reach for reach in reaches}


def test_from_the_outlet_the_river_climbs_the_branch_with_the_largest_upstream_area() -> None:
    assert traced_reach_ids(OUTLET, branching()) == [TRIBUTARY, OUTLET]


def test_from_a_middle_reach_the_river_runs_from_its_source_to_the_mouth() -> None:
    assert traced_reach_ids(JUNCTION, branching()) == [SOURCE_B, JUNCTION, OUTLET]
    assert traced_reach_ids(SOURCE_A, branching()) == [SOURCE_A, JUNCTION, OUTLET]


def test_equal_upstream_areas_take_the_lowest_reach_id() -> None:
    assert traced_reach_ids(JUNCTION, branching(link(10, JUNCTION, 150.0))) == [10, JUNCTION, OUTLET]
    assert traced_reach_ids(JUNCTION, branching(link(16, JUNCTION, 150.0))) == [SOURCE_B, JUNCTION, OUTLET]


def test_a_named_river_is_climbed_along_its_own_reaches_before_the_largest_branch() -> None:
    assert traced_reach_ids(OUTLET, branching(), named=[SOURCE_A, JUNCTION, OUTLET]) == [
        SOURCE_A,
        JUNCTION,
        OUTLET,
    ]
    assert traced_reach_ids(OUTLET, branching(), named=[OUTLET]) == [TRIBUTARY, OUTLET]


def test_a_reach_with_no_next_down_ends_the_river_where_it_starts() -> None:
    assert traced_reach_ids(41, {41: link(41, 0, 130.0, main_riv=41)}) == [41]


def test_a_cycle_is_refused_from_either_side() -> None:
    looped = {21: link(21, 22, 100.0, main_riv=23), 22: link(22, 21, 100.0, main_riv=23)}
    with pytest.raises(RiverNetworkError, match="cycle"):
        traced_reach_ids(21, looped)
    below = {31: link(31, 32, 100.0, main_riv=34), 32: link(32, 33, 100.0, main_riv=34)}
    below[33] = link(33, 32, 50.0, main_riv=34)
    with pytest.raises(RiverNetworkError, match="cycle"):
        traced_reach_ids(31, below)


def test_a_reach_flowing_into_an_unstored_reach_is_refused() -> None:
    with pytest.raises(RiverNetworkError, match="reach 31 flows into 99, which is not stored"):
        traced_reach_ids(31, {31: link(31, 99, 100.0, main_riv=32)})
    with pytest.raises(RiverNetworkError, match="reach 77 is not stored"):
        traced_reach_ids(77, branching())


def test_a_river_longer_than_the_bound_is_refused() -> None:
    last = TRACE_REACHES_MAX + 2
    chain = {i: link(i, i + 1, float(i), main_riv=last) for i in range(1, last)}
    chain[last] = link(last, 0, float(last), main_riv=last)
    with pytest.raises(RiverNetworkError, match=f"runs past {TRACE_REACHES_MAX} reaches"):
        traced_reach_ids(last, chain)


def test_a_trace_carries_its_outlet_and_districts_and_passes_the_contract_check() -> None:
    links = branching()
    trace = river_trace([SOURCE_B, JUNCTION, OUTLET], links, [449, 673])
    assert (trace.main_riv, trace.reach_ids, trace.district_lgds) == (OUTLET, [12, 13, 15], [449, 673])
    assert trace.dataset_code == "HYDRORIVERS_1_0"


def test_a_trace_over_a_reach_of_another_river_is_refused() -> None:
    links = branching() | {JUNCTION: link(JUNCTION, OUTLET, 300.0, main_riv=99)}
    with pytest.raises(RiverNetworkError, match="reach 13 belongs to river 99, not 15"):
        river_trace([SOURCE_B, JUNCTION, OUTLET], links, [])


def test_districts_are_listed_once_in_the_order_the_river_first_enters_them() -> None:
    hits = [
        DistrictHit(position=2, district_lgd=9, entry=0.5),
        DistrictHit(position=1, district_lgd=8, entry=0.6),
        DistrictHit(position=3, district_lgd=7, entry=0.3),
        DistrictHit(position=1, district_lgd=7, entry=0.0),
        DistrictHit(position=2, district_lgd=8, entry=0.0),
        DistrictHit(position=4, district_lgd=6, entry=0.2),
        DistrictHit(position=4, district_lgd=5, entry=0.2),
    ]
    assert districts_in_path_order(hits) == [7, 8, 9, 5, 6]
    assert districts_in_path_order([]) == []
