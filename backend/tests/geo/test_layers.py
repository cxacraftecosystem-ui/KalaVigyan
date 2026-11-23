import dataclasses
import hashlib
import json
import re

import pytest

from app.core.errors import InvalidInput
from app.geo.layers import (
    LAYERS_BY_ID,
    MAP_LAYERS,
    layer_unit,
    map_layer,
    map_layer_list,
    quantile_classes,
    stored_depth_or_period,
)
from app.geo.records import LayerRow, ValueRecord
from app.geo.region_view import district_value, region_facets
from app.schemas.region import (
    DATASET_FACETS,
    DEPTH_PATTERN,
    LAYER_ID_PATTERN,
    REGION_FACETS,
    MapLayer,
    MapLayerList,
)

from ..contracts.golden import dumped, golden_json, golden_text
from ..contracts.phase_b_golden import catalog_dataset
from .golden_region import (
    GOLDEN_LAYER,
    GOLDEN_LAYERS,
    KACHCHH,
    SOIL_PH,
    dataset_record,
    golden_datasets,
    golden_layer_values,
    golden_listing,
)


def bounds(values: list[float]) -> list[tuple[float, float]]:
    return [(band.min, band.max) for band in quantile_classes(values)]


def test_stored_soil_ph_rows_build_the_golden_layer() -> None:
    assert dumped(MapLayer, map_layer(golden_layer_values())) == golden_text(GOLDEN_LAYER)


def test_the_listed_layers_build_the_golden_layer_list() -> None:
    assert dumped(MapLayerList, map_layer_list(golden_listing())) == golden_text(GOLDEN_LAYERS)


def test_the_layer_version_is_the_sha256_of_everything_else_it_sends() -> None:
    body = golden_json(GOLDEN_LAYER)
    rest = {key: value for key, value in body.items() if key != "version"}
    canonical = json.dumps(rest, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    assert body["version"] == hashlib.sha256(canonical).hexdigest()
    renamed = dataclasses.replace(
        golden_layer_values(),
        dataset=dataclasses.replace(golden_layer_values().dataset, licence="CC BY 4.0 International"),
    )
    assert map_layer(renamed).version != body["version"]


def test_quintile_breaks_interpolate_between_the_sorted_values() -> None:
    assert sorted(SOIL_PH.values()) == [
        6.673111,
        6.780816,
        6.947537,
        7.04553,
        7.281044,
        7.281131,
        7.281387,
        7.343617,
        7.350742,
    ]
    assert bounds(list(SOIL_PH.values())) == [
        (6.673111, 6.88),
        (6.88, 7.09),
        (7.09, 7.28),
        (7.28, 7.31),
        (7.31, 7.350742),
    ]


def test_breaks_keep_three_significant_figures() -> None:
    assert bounds([0.0, 1234.0, 2346.0, 3456.0, 4567.0, 5678.0]) == [
        (0.0, 1230.0),
        (1230.0, 2350.0),
        (2350.0, 3460.0),
        (3460.0, 4570.0),
        (4570.0, 5678.0),
    ]


def test_fewer_distinct_values_make_fewer_classes() -> None:
    assert bounds([5.0, 5.0, 5.0]) == [(5.0, 5.0)]
    assert bounds([1.0, 2.0]) == [(1.0, 1.5), (1.5, 2.0)]
    assert bounds([0.0, 0.0, 0.0, 0.0, 1.0, 2.0]) == [(0.0, 0.333), (0.333, 2.0)]


def test_an_empty_layer_is_refused() -> None:
    with pytest.raises(InvalidInput, match="no district values"):
        map_layer(dataclasses.replace(golden_layer_values(), rows=()))
    with pytest.raises(InvalidInput, match="at least one value"):
        quantile_classes([])


def test_a_layer_states_every_grid_its_values_were_read_at() -> None:
    stored = golden_layer_values()
    mixed = dataclasses.replace(stored, rows=(*stored.rows[:-1], LayerRow(462, 6.9, "1 km (resampled)")))
    assert map_layer(mixed).resolution == "1 km (resampled); 250 m"


def test_a_layer_has_exactly_one_unit() -> None:
    spec = LAYERS_BY_ID["soil-ph-0-5cm"]
    assert layer_unit(spec, ["pH", "pH"]) == "pH"
    with pytest.raises(InvalidInput, match="exactly one"):
        layer_unit(spec, ["pH", "pH units"])
    with pytest.raises(InvalidInput, match="exactly one"):
        layer_unit(spec, [None])


def test_the_list_cannot_be_drawn_without_the_boundary_it_cites() -> None:
    with pytest.raises(InvalidInput, match="DR_DISTRICT_SHAPES"):
        map_layer_list(dataclasses.replace(golden_listing(), boundary=None))


def test_registry_ids_are_unique_slugs_grouped_by_facet() -> None:
    ids = [spec.id for spec in MAP_LAYERS]
    assert len(set(ids)) == len(ids)
    assert all(re.fullmatch(LAYER_ID_PATTERN, layer_id) for layer_id in ids)
    facets = [REGION_FACETS.index(spec.facet) for spec in MAP_LAYERS]
    assert facets == sorted(facets)
    assert all(spec.dataset_code in DATASET_FACETS for spec in MAP_LAYERS)


def test_registry_depths_and_periods_are_the_stored_ones() -> None:
    datasets = golden_datasets()
    for spec in MAP_LAYERS:
        stored = spec.depth_or_period
        assert (
            stored is None
            or stored == ""
            or re.fullmatch(DEPTH_PATTERN, stored)
            or re.fullmatch(r"\d{4}(-\d{4})?", stored)
        )
    chirps = dataclasses.replace(datasets["SOILGRIDS_2_0"], code="CHIRPS_3_0", period="2016-2025")
    assert stored_depth_or_period(LAYERS_BY_ID["monsoon-share"], chirps) == "2016-2025"
    assert stored_depth_or_period(LAYERS_BY_ID["soil-ph-0-5cm"], datasets["SOILGRIDS_2_0"]) == "0-5cm"


def test_a_climate_layer_draws_the_normal_the_district_panel_shows() -> None:
    datasets = {
        code: dataset_record(catalog_dataset(code) | {"period": period})
        for code, period in (
            ("CHELSA_2_1_1981_2010", "1981-2010"),
            ("CHIRPS_3_0", "1981-2025"),
            ("GHCN_CAMS_T2M", "1981-2025"),
        )
    }
    stored = (
        ("CHELSA_2_1_1981_2010", "annual_precipitation", "1981-2010", 434.14, "mm/year"),
        ("CHIRPS_3_0", "annual_precipitation", "1981-2025", 449.36, "mm/year"),
        ("CHELSA_2_1_1981_2010", "annual_mean_temperature", "1981-2010", 27.2, "degC"),
        ("GHCN_CAMS_T2M", "annual_mean_temperature", "1981-2025", 27.07, "degC"),
    )
    rows = [
        ValueRecord(KACHCHH, code, variable, period, "NORMAL", value, None, unit, None, None)
        for code, variable, period, value, unit in stored
    ]
    facets = region_facets(district_value(row, datasets[row.dataset_code]) for row in rows)
    panel = {(value.dataset_code, value.variable, value.period) for facet in facets for value in facet.values}
    specs = (LAYERS_BY_ID["annual-precipitation"], LAYERS_BY_ID["annual-mean-temperature"])
    drawn = {
        (spec.dataset_code, spec.variable, stored_depth_or_period(spec, datasets[spec.dataset_code]))
        for spec in specs
    }
    trend_normals = {
        ("CHIRPS_3_0", "annual_precipitation", "1981-2025"),
        ("GHCN_CAMS_T2M", "annual_mean_temperature", "1981-2025"),
    }
    assert panel == drawn == trend_normals
