from dataclasses import dataclass

import pandas as pd

from geo_etl.catalog import GLIM, SOILGRIDS
from geo_etl.layers import Result

__all__ = ["EXPECTED_WITHOUT_CELLS", "Coverage", "coverage_of", "covered_districts", "state_members"]

EXPECTED_WITHOUT_CELLS: dict[str, dict[int, str]] = {
    GLIM.code: {
        553: "Lakshadweep lies on no land cell of the 0.5 degree GLiM grid (Actions run 43949571146)",
    },
    SOILGRIDS.code: {
        482: "SoilGrids masks every cell of Mumbai: 0 of 2,720 cells unmasked in a WCS read on 2026-11-17",
    },
}


@dataclass(frozen=True)
class Coverage:
    districts_without_values: list[int]
    districts_without_cells: list[int]
    unexpected_without_cells: list[int]
    silent_districts: list[int]
    lost_states: list[int]


def coverage_of(districts: pd.DataFrame, result: Result) -> Coverage:
    if result.states is not None:
        districts = districts[districts["stateLgd"].isin(sorted(result.states))]
    members = state_members(districts)
    selected = set().union(*members.values()) if members else set()
    covered = covered_districts(result)
    without_cells = (set(result.districts_without_cells) & selected) - covered
    accounted = covered | without_cells
    lost = {state for state, lgds in members.items() if not lgds & accounted}
    for named in failed_groups(result):
        lost |= {state for state, lgds in members.items() if lgds <= named}
    failed = set().union(*failed_groups(result))
    expected = set(EXPECTED_WITHOUT_CELLS.get(result.dataset.code, {}))
    return Coverage(
        districts_without_values=sorted(selected - covered),
        districts_without_cells=sorted(without_cells),
        unexpected_without_cells=sorted(without_cells - expected),
        silent_districts=sorted(selected - accounted - failed),
        lost_states=sorted(lost),
    )


def state_members(districts: pd.DataFrame) -> dict[int, set[int]]:
    members: dict[int, set[int]] = {}
    for lgd, state in zip(districts["districtLgd"], districts["stateLgd"], strict=True):
        members.setdefault(int(state), set()).add(int(lgd))
    return members


def covered_districts(result: Result) -> set[int]:
    covered = {int(v) for v in result.values["districtLgd"]}
    if result.geology is not None:
        covered |= {int(v) for v in result.geology["districtLgd"]}
    return covered


def failed_groups(result: Result) -> list[set[int]]:
    return [{int(v) for v in item["districtLgds"]} for item in result.failures]
