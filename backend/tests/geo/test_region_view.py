import dataclasses
import logging

import pytest
from pydantic import ValidationError

from app.core.errors import InvalidInput
from app.geo.climate import climate_trends
from app.geo.places import region_places
from app.geo.records import RegionRecords, SeriesTotals, ValueRecord
from app.geo.region_view import craft_region, district_value, region_facets
from app.research.blocks_place import DistrictRef
from app.schemas.region import CraftRegion

from ..contracts.golden import dumped, golden_text
from ..contracts.phase_b_golden import catalog_dataset
from .golden_region import (
    GOLDEN_CRAFT,
    GUJARAT,
    KACHCHH,
    SOIL_PH_SERIES,
    VAV_THARAD,
    WORLDCOVER_READ,
    dataset_record,
    golden_region_records,
    location,
    stored_row,
)

SOIL_METHOD = "ISRIC WCS zonal mean"


def totals(**changes: object) -> SeriesTotals:
    fields: dict[str, object] = {
        "state_lgd": GUJARAT.lgd,
        "dataset_code": "SOILGRIDS_2_0",
        "variable": "phh2o",
        "depth_or_period": "0-5cm",
        "stat": "DISTRICT_MEAN",
        "unit": "pH",
        "value_text": None,
        "districts": 2,
        "weighted_sum": 3 * 7.0 + 1 * 8.0,
        "area": 4.0,
        "total": 15.0,
        "low": 7.0,
        "high": 8.0,
        "resolutions": (None,),
        "methods": (SOIL_METHOD,),
        "dataset_districts": 2,
        "dataset_area": 4.0,
    }
    return SeriesTotals(**(fields | changes))


def inherited_records(*series: SeriesTotals):
    vav = location(id="location-vav", district_lgd=VAV_THARAD, district_name="Vav-Tharad", has_polygon=False)
    return dataclasses.replace(
        golden_region_records(),
        places=region_places([vav], []),
        district_values=(),
        state_totals=series,
        district_totals={GUJARAT.lgd: 34},
    )


def test_stored_kachchh_rows_build_the_golden_region() -> None:
    assert dumped(CraftRegion, craft_region(golden_region_records())) == golden_text(GOLDEN_CRAFT)


def test_values_without_their_own_grid_carry_the_datasets_native_grid() -> None:
    region = craft_region(golden_region_records())
    grids = {v.dataset_code: v.resolution for f in region.places[0].facets for v in f.values}
    assert grids["GLIM_1_0_05DEG"] == "0.5 degree"
    assert grids["ESA_WORLDCOVER_2021_V200"] == WORLDCOVER_READ


def test_a_district_without_a_polygon_shows_its_states_area_weighted_mean_and_says_why() -> None:
    region = craft_region(inherited_records(totals()))
    [place] = region.places
    assert (place.key, place.values_from, place.inherited_reason) == (
        f"district-{VAV_THARAD}",
        "STATE",
        "NO_DISTRICT_POLYGON",
    )
    [value] = place.facets[0].values
    assert (value.aggregation, value.value, value.district_count, value.district_total) == (
        "STATE_AREA_MEAN",
        7.25,
        2,
        34,
    )
    assert (value.depth, value.period, value.resolution, value.method) == (
        "0-5cm",
        "modelled, 2020 release",
        "250 m",
        SOIL_METHOD,
    )


def test_a_state_only_craft_is_practised_across_the_state_with_its_aggregates() -> None:
    sites = totals(
        dataset_code="USGS_MRDS",
        variable="mineral_occurrences",
        depth_or_period="",
        stat="COUNT",
        unit="sites",
    )
    records = dataclasses.replace(inherited_records(sites), places=region_places([], [GUJARAT]))
    [place] = craft_region(records).places
    assert (place.key, place.scope, place.basis.kind, place.basis.level) == (
        "state-24",
        "STATE",
        "MASTER_LIST",
        "REVIEWED",
    )
    assert place.facets[0].values[0].model_dump(include={"aggregation", "value"}) == {
        "aggregation": "STATE_SUM",
        "value": 15.0,
    }


def test_a_state_aggregate_lists_every_grid_its_districts_were_read_at() -> None:
    series = totals(
        dataset_code="ESA_WORLDCOVER_2021_V200",
        variable="landcover_cropland",
        depth_or_period="2021",
        stat="SHARE",
        unit="fraction",
        resolutions=(None, WORLDCOVER_READ),
    )
    value = craft_region(inherited_records(series)).places[0].facets[0].values[0]
    assert value.resolution == f"10 m (1/12000 degree); {WORLDCOVER_READ}"


def test_a_facet_with_no_stored_value_is_left_out() -> None:
    records = dataclasses.replace(
        golden_region_records(),
        district_values=tuple(
            v for v in golden_region_records().district_values if v.dataset_code == "USGS_MRDS"
        ),
    )
    region = craft_region(records)
    assert [f.facet for f in region.places[0].facets] == ["GEOLOGY"]
    assert [d.code for d in region.datasets] == ["USGS_MRDS"]


def test_a_place_with_no_stored_values_has_no_facets_and_cites_no_dataset() -> None:
    region = craft_region(dataclasses.replace(golden_region_records(), district_values=()))
    assert (region.places[0].facets, region.datasets) == ([], [])


def test_a_value_of_a_dataset_without_a_facet_is_left_out_and_logged(
    caplog: pytest.LogCaptureFixture,
) -> None:
    stray = ValueRecord(KACHCHH, "IMD_GRIDDED", "rainfall", "", "NORMAL", 1.0, None, "mm", None, None)
    records = golden_region_records()
    records = dataclasses.replace(records, district_values=(*records.district_values, stray))
    with caplog.at_level(logging.WARNING):
        region = craft_region(records)
    assert "IMD_GRIDDED" not in {d.code for d in region.datasets}
    assert "IMD_GRIDDED has no region facet" in caplog.text


def test_the_district_panel_reads_soil_depths_from_the_surface_down() -> None:
    surface = stored_row(KACHCHH, SOIL_PH_SERIES)
    clay = dataclasses.replace(surface, variable="clay")
    deeper = [dataclasses.replace(surface, depth_or_period=depth) for depth in ("15-30cm", "5-15cm")]
    soil = golden_region_records().datasets["SOILGRIDS_2_0"]
    [facet] = region_facets(district_value(row, soil) for row in (*deeper, surface, clay))
    shown = [(v.variable, v.depth) for v in facet.values]
    assert shown == [("clay", "0-5cm"), ("phh2o", "0-5cm"), ("phh2o", "5-15cm"), ("phh2o", "15-30cm")]


def test_a_stored_value_without_a_unit_fails_loudly() -> None:
    records = golden_region_records()
    broken = dataclasses.replace(stored_row(KACHCHH, SOIL_PH_SERIES), unit=None)
    with pytest.raises(InvalidInput, match="has no unit"):
        craft_region(dataclasses.replace(records, district_values=(broken,)))


def test_a_value_citing_a_dataset_with_no_row_fails_loudly() -> None:
    records = golden_region_records()
    datasets = {code: row for code, row in records.datasets.items() if code != "SOILGRIDS_2_0"}
    with pytest.raises(InvalidInput, match="SOILGRIDS_2_0"):
        craft_region(dataclasses.replace(records, datasets=datasets))


def test_a_state_aggregate_needs_the_states_district_count() -> None:
    records = dataclasses.replace(inherited_records(totals()), district_totals={})
    with pytest.raises(InvalidInput, match="no district count"):
        craft_region(records)


def test_a_dataset_row_without_an_edition_is_refused_by_the_contract() -> None:
    records = golden_region_records()
    soil = dataclasses.replace(records.datasets["SOILGRIDS_2_0"], edition=None)
    with pytest.raises(ValidationError):
        craft_region(dataclasses.replace(records, datasets={**records.datasets, "SOILGRIDS_2_0": soil}))


def test_a_located_place_brings_its_source_and_a_state_of_practice_brings_none() -> None:
    located = craft_region(golden_region_records())
    assert [source.id for source in located.sources] == [located.places[0].basis.source_id]
    state_only = craft_region(
        dataclasses.replace(golden_region_records(), places=region_places([], [GUJARAT]))
    )
    assert state_only.sources == []


ClimateRow = tuple[str, str, str, str, float, str]


def climate_records(*rows: ClimateRow):
    records = golden_region_records()
    values = tuple(
        ValueRecord(KACHCHH, code, variable, period, stat, value, None, unit, None, None)
        for code, variable, period, stat, value, unit in rows
    )
    datasets = {
        **records.datasets,
        "CHIRPS_3_0": dataset_record(catalog_dataset("CHIRPS_3_0") | {"period": "1981-2025"}),
        "GHCN_CAMS_T2M": dataset_record(catalog_dataset("GHCN_CAMS_T2M") | {"period": "1981-2025"}),
    }
    return dataclasses.replace(records, district_values=values, datasets=datasets)


def shown_climate(records: RegionRecords) -> set[tuple[str, str, str, str]]:
    values = (district_value(row, records.datasets[row.dataset_code]) for row in records.district_values)
    return {
        (value.dataset_code, value.variable, value.period, value.stat)
        for facet in region_facets(values)
        for value in facet.values
    }


def test_the_district_panel_shows_the_rainfall_and_temperature_normals_of_their_trend_datasets() -> None:
    records = climate_records(
        ("CHELSA_2_1_1981_2010", "annual_precipitation", "1981-2010", "NORMAL", 434.14, "mm/year"),
        ("CHELSA_2_1_1981_2010", "annual_precipitation", "1981-2010", "DISTRICT_P10", 341.4, "mm/year"),
        ("CHIRPS_3_0", "annual_precipitation", "1981-2025", "NORMAL", 449.36, "mm/year"),
        ("CHIRPS_3_0", "annual_precipitation", "1981", "DISTRICT_MEAN", 518.45, "mm/year"),
        ("CHIRPS_3_0", "annual_precipitation", "1981-2025", "TREND_PER_DECADE", 70.76, "mm/year per decade"),
        ("CHELSA_2_1_1981_2010", "precipitation", "1981-2010-07", "NORMAL", 170.2, "mm/month"),
        ("CHIRPS_3_0", "monthly_precipitation", "1981-2025-07", "NORMAL", 181.46, "mm/month"),
        ("CHELSA_2_1_1981_2010", "precipitation", "1981-2010-08", "NORMAL", 101.0, "mm/month"),
        ("CHELSA_2_1_1981_2010", "annual_mean_temperature", "1981-2010", "NORMAL", 27.2, "degC"),
        ("CHELSA_2_1_1981_2010", "annual_mean_temperature", "1981-2010", "DISTRICT_P90", 28.1, "degC"),
        ("CHELSA_2_1_1981_2010", "max_temperature_warmest_month", "1981-2010", "NORMAL", 40.3, "degC"),
        ("GHCN_CAMS_T2M", "annual_mean_temperature", "1981-2025", "NORMAL", 27.07, "degC"),
        ("GHCN_CAMS_T2M", "annual_mean_temperature", "1981", "DISTRICT_MEAN", 26.66, "degC"),
        ("GHCN_CAMS_T2M", "annual_mean_temperature", "1981-2025", "TREND_P_VALUE", 0.0004, "p-value"),
    )
    assert shown_climate(records) == {
        ("CHIRPS_3_0", "annual_precipitation", "1981-2025", "NORMAL"),
        ("CHIRPS_3_0", "annual_precipitation", "1981", "DISTRICT_MEAN"),
        ("CHIRPS_3_0", "annual_precipitation", "1981-2025", "TREND_PER_DECADE"),
        ("CHIRPS_3_0", "monthly_precipitation", "1981-2025-07", "NORMAL"),
        ("CHELSA_2_1_1981_2010", "precipitation", "1981-2010-08", "NORMAL"),
        ("CHELSA_2_1_1981_2010", "max_temperature_warmest_month", "1981-2010", "NORMAL"),
        ("GHCN_CAMS_T2M", "annual_mean_temperature", "1981-2025", "NORMAL"),
        ("GHCN_CAMS_T2M", "annual_mean_temperature", "1981", "DISTRICT_MEAN"),
        ("GHCN_CAMS_T2M", "annual_mean_temperature", "1981-2025", "TREND_P_VALUE"),
    }


def test_the_district_panel_keeps_a_normal_when_the_trend_dataset_has_none_for_the_place() -> None:
    records = climate_records(
        ("CHELSA_2_1_1981_2010", "annual_precipitation", "1981-2010", "NORMAL", 434.14, "mm/year"),
        ("CHELSA_2_1_1981_2010", "annual_mean_temperature", "1981-2010", "NORMAL", 27.2, "degC"),
        ("GHCN_CAMS_T2M", "annual_mean_temperature", "1981", "DISTRICT_MEAN", 26.66, "degC"),
    )
    assert shown_climate(records) == {
        ("CHELSA_2_1_1981_2010", "annual_precipitation", "1981-2010", "NORMAL"),
        ("CHELSA_2_1_1981_2010", "annual_mean_temperature", "1981-2010", "NORMAL"),
        ("GHCN_CAMS_T2M", "annual_mean_temperature", "1981", "DISTRICT_MEAN"),
    }


def test_the_region_card_states_the_same_normal_as_the_answer_s_climate_card() -> None:
    records = climate_records(
        ("CHELSA_2_1_1981_2010", "annual_precipitation", "1981-2010", "NORMAL", 434.14, "mm/year"),
        ("CHIRPS_3_0", "annual_precipitation", "1981-2025", "NORMAL", 449.36, "mm/year"),
        ("CHIRPS_3_0", "annual_precipitation", "1981-2025", "TREND_PER_DECADE", 70.76, "mm/year per decade"),
        ("CHIRPS_3_0", "annual_precipitation", "1981-2025", "TREND_P_VALUE", 0.02, "p-value"),
        ("CHELSA_2_1_1981_2010", "annual_mean_temperature", "1981-2010", "NORMAL", 27.2, "degC"),
        ("GHCN_CAMS_T2M", "annual_mean_temperature", "1981-2025", "NORMAL", 27.07, "degC"),
        (
            "GHCN_CAMS_T2M",
            "annual_mean_temperature",
            "1981-2025",
            "TREND_PER_DECADE",
            0.21,
            "degC per decade",
        ),
        ("GHCN_CAMS_T2M", "annual_mean_temperature", "1981-2025", "TREND_P_VALUE", 0.0004, "p-value"),
    )
    district = DistrictRef(district_lgd=KACHCHH, name="Kachchh", state_name="Gujarat")
    trends = climate_trends([district], records.district_values, records.datasets).trends
    card = {(t.dataset_code, t.variable): (t.period, t.mean) for t in trends}
    region = {
        (value.dataset_code, value.variable): (value.period, value.value)
        for facet in craft_region(records).places[0].facets
        for value in facet.values
        if value.stat == "NORMAL"
    }
    trend_normals = {
        ("CHIRPS_3_0", "annual_precipitation"): ("1981-2025", 449.36),
        ("GHCN_CAMS_T2M", "annual_mean_temperature"): ("1981-2025", 27.07),
    }
    assert card == region == trend_normals


def test_a_place_source_that_was_not_loaded_fails_loudly() -> None:
    with pytest.raises(InvalidInput, match="were not loaded"):
        craft_region(dataclasses.replace(golden_region_records(), sources={}))
