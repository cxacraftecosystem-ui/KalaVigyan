import copy
import re
from typing import Any

import pytest
from pydantic import ValidationError

from app.research.datasets import BOUNDARY_CAPTION, BOUNDARY_DATASET_CODE
from app.schemas.region import (
    DATASET_FACETS,
    CraftRegion,
    MapLayer,
    MapLayerList,
    PlaceBasis,
    RegionPlace,
    RegionValue,
    split_depth_or_period,
)

from .golden import golden_json, plan_text, reproduces
from .phase_b_golden import geo_etl_datasets


def place() -> dict[str, Any]:
    return copy.deepcopy(golden_json("region.craft.golden.json")["places"][0])


def state_value(stat: str, aggregation: str, count: int = 30, total: int = 34) -> dict[str, Any]:
    value = place()["facets"][0]["values"][0]
    return {**value, "stat": stat, "aggregation": aggregation, "districtCount": count, "districtTotal": total}


@pytest.mark.parametrize(
    ("shape", "name"),
    [
        (CraftRegion, "region.craft.golden.json"),
        (MapLayerList, "region.layers.golden.json"),
        (MapLayer, "region.layer.golden.json"),
    ],
)
def test_the_golden_region_files_are_reproduced_byte_for_byte(shape: Any, name: str) -> None:
    assert reproduces(shape, name)


def test_every_region_dataset_cites_edition_resolution_and_period() -> None:
    region = CraftRegion.model_validate(golden_json("region.craft.golden.json"))
    for dataset in region.datasets:
        assert dataset.edition and dataset.native_resolution and dataset.period and dataset.licence
    assert {v.resolution for f in region.places[0].facets for v in f.values} >= {"250 m", "point locations"}


@pytest.mark.parametrize(
    ("stored", "dataset_period", "expected"),
    [
        ("0-5cm", "modelled, 2020 release", ("0-5cm", "modelled, 2020 release")),
        ("1981-2010", "1981-2010", (None, "1981-2010")),
        ("2021", "2021", (None, "2021")),
        ("", "2011-2015 acquisitions", (None, "2011-2015 acquisitions")),
    ],
)
def test_depth_or_period_splits_into_a_depth_and_a_period(
    stored: str, dataset_period: str, expected: tuple[str | None, str]
) -> None:
    assert split_depth_or_period(stored, dataset_period) == expected


def test_a_state_aggregate_sums_totals_and_area_weights_means() -> None:
    assert RegionValue.model_validate(state_value("TOTAL", "STATE_SUM")).aggregation == "STATE_SUM"
    assert RegionValue.model_validate(state_value("DISTRICT_MEAN", "STATE_AREA_MEAN")).district_count == 30
    with pytest.raises(ValidationError, match="not aggregated to a state"):
        RegionValue.model_validate(state_value("DISTRICT_P10", "STATE_AREA_MEAN"))
    with pytest.raises(ValidationError, match="at most the state's districts"):
        RegionValue.model_validate(state_value("TOTAL", "STATE_SUM", count=35, total=34))


def test_a_district_without_a_polygon_inherits_its_state_and_says_so() -> None:
    body = place()
    body["facets"] = [{"facet": "SOIL", "values": [state_value("DISTRICT_MEAN", "STATE_AREA_MEAN")]}]
    body["valuesFrom"] = "STATE"
    with pytest.raises(ValidationError, match="only when it has no polygon"):
        RegionPlace.model_validate(body)
    inherited = RegionPlace.model_validate({**body, "inheritedReason": "NO_DISTRICT_POLYGON"})
    assert inherited.values_from == "STATE"


def test_a_state_only_craft_shows_the_state_aggregate() -> None:
    body = place()
    body.update(
        key="state-24",
        scope="STATE",
        districtLgd=None,
        districtName=None,
        placeLabel="Gujarat",
        basis={
            "kind": "MASTER_LIST",
            "sourceId": None,
            "label": "IIT Crafts Master List, 2026-10-20",
            "level": "REVIEWED",
        },
        valuesFrom="STATE",
        facets=[{"facet": "SOIL", "values": [state_value("DISTRICT_MEAN", "STATE_AREA_MEAN")]}],
    )
    assert RegionPlace.model_validate(body).key == "state-24"
    with pytest.raises(ValidationError, match="district values or all state aggregates"):
        RegionPlace.model_validate({**body, "facets": place()["facets"]})


def test_a_place_basis_always_cites() -> None:
    with pytest.raises(ValidationError, match="only with the source"):
        PlaceBasis.model_validate(
            {"kind": "CRAFT_LOCATION", "sourceId": None, "label": "x", "level": "PROVISIONAL"}
        )
    with pytest.raises(ValidationError, match="Master List"):
        PlaceBasis.model_validate(
            {"kind": "MASTER_LIST", "sourceId": None, "label": "Wikipedia", "level": "REVIEWED"}
        )


def test_facets_appear_once_in_order_and_hold_only_their_datasets() -> None:
    body = place()
    body["facets"].reverse()
    with pytest.raises(ValidationError, match="REGION_FACETS order"):
        RegionPlace.model_validate(body)
    wrong = place()
    wrong["facets"][0]["facet"] = "CLIMATE"
    with pytest.raises(ValidationError, match="does not belong to"):
        RegionPlace.model_validate(wrong)


def test_region_datasets_are_exactly_the_cited_ones() -> None:
    body = golden_json("region.craft.golden.json")
    body["datasets"].pop()
    with pytest.raises(ValidationError, match="every cited dataset"):
        CraftRegion.model_validate(body)


def test_layer_classes_are_contiguous_and_hold_every_value() -> None:
    body = golden_json("region.layer.golden.json")
    gap = copy.deepcopy(body)
    gap["classes"][1]["min"] = 7.1
    with pytest.raises(ValidationError, match="contiguous"):
        MapLayer.model_validate(gap)
    outside = copy.deepcopy(body)
    outside["values"]["449"] = 9.0
    with pytest.raises(ValidationError, match="falls in a class"):
        MapLayer.model_validate(outside)
    named = copy.deepcopy(body)
    named["values"]["Kachchh"] = 8.1
    with pytest.raises(ValidationError, match="LGD"):
        MapLayer.model_validate(named)


def test_the_boundary_caption_is_the_plan_eight_text() -> None:
    caption = re.search(r'caption "([^"]+)"', plan_text())
    assert caption is not None and caption.group(1) == BOUNDARY_CAPTION
    layers = MapLayerList.model_validate(golden_json("region.layers.golden.json"))
    assert (layers.boundary.caption, layers.boundary.dataset.code) == (
        BOUNDARY_CAPTION,
        BOUNDARY_DATASET_CODE,
    )


def test_every_dataset_the_geo_etl_builds_has_a_region_facet() -> None:
    codes = set(geo_etl_datasets()) - {BOUNDARY_DATASET_CODE}
    assert codes and codes <= set(DATASET_FACETS)


def test_region_sources_are_every_place_source_once_in_place_order() -> None:
    body = golden_json("region.craft.golden.json")
    assert [source["id"] for source in body["sources"]] == [body["places"][0]["basis"]["sourceId"]]
    missing = {**body, "sources": []}
    with pytest.raises(ValidationError, match="every place's source once"):
        CraftRegion.model_validate(missing)
    twice = {**body, "sources": body["sources"] * 2}
    with pytest.raises(ValidationError, match="every place's source once"):
        CraftRegion.model_validate(twice)
