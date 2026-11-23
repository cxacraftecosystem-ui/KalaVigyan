import ast
import logging
from pathlib import Path
from typing import Any

import pytest

from app.geo.climate import ClimateTrends
from app.geo.datasets import region_dataset
from app.geo.groundwater import (
    GROUNDWATER_DATASETS,
    GROUNDWATER_VARIABLES,
    groundwater_values,
    with_groundwater,
)
from app.geo.records import DatasetRecord, ValueRecord
from app.research.blocks_climate import GroundwaterValue
from app.research.blocks_place import DistrictRef

from ..contracts.golden import REPO
from ..contracts.phase_b_golden import catalog_dataset
from .golden_region import dataset_record

LAYER = REPO / "etl" / "geo" / "geo_etl" / "layers" / "groundwater.py"
CATALOG = REPO / "etl" / "geo" / "geo_etl" / "catalog.py"
CODE = "OGD_GW_RESOURCES_RAJASTHAN_2023"
JAIPUR = DistrictRef(district_lgd=102, name="Jaipur", state_name="Rajasthan")
AJMER = DistrictRef(district_lgd=86, name="Ajmer", state_name="Rajasthan")
GRID = "district, as in the list of districts before the reorganisation"
CHIRPS = "CHIRPS_3_0"


def groundwater_dataset() -> DatasetRecord:
    return dataset_record(catalog_dataset(CODE))


def row(variable: str, stat: str, value: float | None, unit: str | None, **changes: object) -> ValueRecord:
    fields: dict[str, object] = {
        "district_lgd": JAIPUR.district_lgd,
        "dataset_code": CODE,
        "variable": variable,
        "depth_or_period": "2023",
        "stat": stat,
        "value": value,
        "value_text": None,
        "unit": unit,
        "resolution": None,
        "method": "the district's figure as the table states it",
    }
    return ValueRecord(**(fields | changes))


def jaipur_rows() -> list[ValueRecord]:
    return [
        row("stage_of_groundwater_extraction", "SHARE", 225.93, "%"),
        row("annual_groundwater_extraction_domestic", "TOTAL", 38927.03, "ham"),
        row("annual_groundwater_extraction", "TOTAL", 147594.63, "ham"),
        row("annual_extractable_groundwater", "TOTAL", 65328.4, "ham"),
        row("annual_groundwater_recharge", "TOTAL", 72587.12, "ham"),
    ]


def shown(value: GroundwaterValue) -> tuple[Any, ...]:
    return (value.district.name, value.variable, value.value, value.unit, value.period, value.resolution)


def test_a_district_s_stored_figures_are_read_in_the_block_s_order_with_their_period_and_grid() -> None:
    found = groundwater_values([JAIPUR], jaipur_rows(), {CODE: groundwater_dataset()})
    assert [shown(value) for value in found] == [
        ("Jaipur", "annual_groundwater_recharge", 72587.12, "ham", "2023", GRID),
        ("Jaipur", "annual_extractable_groundwater", 65328.4, "ham", "2023", GRID),
        ("Jaipur", "annual_groundwater_extraction", 147594.63, "ham", "2023", GRID),
        ("Jaipur", "stage_of_groundwater_extraction", 225.93, "%", "2023", GRID),
    ]
    assert {value.dataset_code for value in found} == {CODE}


def test_a_figure_in_another_unit_another_period_or_without_its_dataset_row_is_not_shown(
    caplog: pytest.LogCaptureFixture,
) -> None:
    rows = [
        row("annual_groundwater_recharge", "TOTAL", 725.87, "MCM"),
        row("annual_extractable_groundwater", "TOTAL", 65328.4, "ham", depth_or_period="2022"),
        row("annual_groundwater_extraction", "SHARE", 147594.63, "ham"),
    ]
    with caplog.at_level(logging.WARNING, logger="app.geo.groundwater"):
        assert groundwater_values([JAIPUR], rows, {CODE: groundwater_dataset()}) == ()
    assert "stored in MCM, not ham" in caplog.text
    assert groundwater_values([JAIPUR], jaipur_rows(), {}) == ()
    assert groundwater_values([AJMER], jaipur_rows(), {CODE: groundwater_dataset()}) == ()


def test_the_climate_block_cites_the_groundwater_row_after_the_trend_rows_once() -> None:
    chirps = region_dataset(dataset_record(catalog_dataset(CHIRPS) | {"period": "1981-2025"}))
    climate = ClimateTrends((), (chirps,))
    datasets = {CODE: groundwater_dataset()}
    found = with_groundwater(climate, [JAIPUR, AJMER], jaipur_rows(), datasets)
    assert [dataset.code for dataset in found.datasets] == [CHIRPS, CODE]
    assert (len(found.groundwater), found.trends) == (4, ())
    again = with_groundwater(found, [JAIPUR], jaipur_rows(), datasets)
    assert [dataset.code for dataset in again.datasets] == [CHIRPS, CODE]
    assert with_groundwater(climate, [AJMER], jaipur_rows(), datasets) is climate


def literal_constants(path: Path) -> dict[str, Any]:
    found: dict[str, Any] = {}
    for node in ast.parse(path.read_text(encoding="utf-8")).body:
        target = node.target if isinstance(node, ast.AnnAssign) else None
        if isinstance(node, ast.Assign) and len(node.targets) == 1:
            target = node.targets[0]
        value = getattr(node, "value", None)
        if isinstance(target, ast.Name) and value is not None:
            try:
                found[target.id] = ast.literal_eval(value)
            except TypeError, ValueError:
                found[target.id] = value
    return found


def test_the_etl_writes_every_figure_the_block_reads_in_the_same_stat_and_unit() -> None:
    layer = literal_constants(LAYER)
    written = {variable: (stat, unit) for variable, stat, unit in layer["FIELDS"].values()}
    read = {variable: (reading.stat, reading.unit) for variable, reading in GROUNDWATER_VARIABLES.items()}
    assert read.items() <= written.items()
    catalogued = literal_constants(CATALOG)["GROUNDWATER"]
    assert isinstance(catalogued, ast.Subscript) and ast.literal_eval(catalogued.slice) == CODE
    assert GROUNDWATER_DATASETS == (CODE,)
    assert catalog_dataset(CODE)["period"] == layer["PERIOD"] == "2023"
