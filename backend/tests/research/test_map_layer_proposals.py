import ast
import json
import re
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from app.data.skill_library import reference_text
from app.research.dataset_proposals import DatasetProposal, record_problems, upload_types
from app.research.map_layer_geojson import (
    FEATURES_MAX,
    LAYER_BYTES_MAX,
    LayerRefused,
    parsed_layer,
    ring_area,
)
from app.research.map_layer_proposals import (
    INDIA_FRAME,
    LAYER_CLASSES,
    LINE_DECIMALS,
    POINT_DECIMALS,
    Frame,
    MapLayerPlan,
    layer_problems,
)
from app.research.review_queue_layers import layer_checks

REPOSITORY = Path(__file__).resolve().parents[3]
INDIA_BOUNDS = REPOSITORY / "frontend" / "components" / "map" / "indiaBounds.ts"
BOUND = re.compile(r"(?P<name>m(?:in|ax)L(?:ong|at)itude): (?P<value>-?[0-9.]+)")
NUMBER_WORDS = {3: "three", 4: "four"}
TABLE_ROW = re.compile(r"^\| (?P<layer>[^|]+) \| (?P<tolerance>[^|]+) \|$", re.MULTILINE)
SITES = MapLayerPlan(
    layer_class="POINT_SITES",
    value_property="deposits",
    variable="deposits recorded at the site",
    unit="count",
    method="counted from the dataset's site records",
)
RIVERS = MapLayerPlan(
    layer_class="RIVERS", simplified_to=0.008, method="centre lines as the dataset draws them"
)
LAKES = MapLayerPlan(layer_class="LAKES", simplified_to=0.006, method="shore lines as the dataset draws them")
TRAILING_ZEROS = (
    b'{"type": "FeatureCollection", "features": [{"type": "Feature", "geometry": {"type": "Point", '
    b'"coordinates": [72.1000, 23.0]}, "properties": {"deposits": 1}}]}'
)
RECORD: dict[str, Any] = {
    "code": "KV_TEST_SITES",
    "title": "Mineral sites of Gujarat",
    "publisher": "A geological survey",
    "edition": "2024",
    "version": "1",
    "period": "2024",
    "native_resolution": "point sites",
    "crs": "EPSG:4326",
    "licence": "CC BY 4.0",
    "licence_url": "https://creativecommons.org/licenses/by/4.0/",
    "attribution": "A geological survey",
    "redistributable": True,
    "citation": "A geological survey (2024). Mineral sites of Gujarat.",
    "landing_url": "https://example.org/sites",
    "url": "https://example.org/sites.geojson",
    "sha256": "a" * 64,
}


def feature(geometry: dict[str, Any], **properties: Any) -> dict[str, Any]:
    return {"type": "Feature", "geometry": geometry, "properties": properties}


def point(longitude: float, latitude: float, **properties: Any) -> dict[str, Any]:
    return feature({"type": "Point", "coordinates": [longitude, latitude]}, **properties)


def collection(*features: dict[str, Any], crs: str | None = None) -> bytes:
    body: dict[str, Any] = {"type": "FeatureCollection", "features": list(features)}
    if crs is not None:
        body["crs"] = {"type": "name", "properties": {"name": crs}}
    return json.dumps(body).encode("utf-8")


def square(west: float, south: float, side: float) -> dict[str, Any]:
    east, north = round(west + side, 3), round(south + side, 3)
    ring = [[west, south], [east, south], [east, north], [west, north], [west, south]]
    return {"type": "Polygon", "coordinates": [ring]}


def refused(data: bytes, plan: MapLayerPlan) -> str:
    with pytest.raises(LayerRefused) as raised:
        parsed_layer(data, plan)
    return str(raised.value)


def constant(relative: str, name: str) -> float:
    tree = ast.parse((REPOSITORY / relative).read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
            isinstance(t, ast.Name) and t.id == name for t in node.targets
        ):
            return float(ast.literal_eval(node.value))
    raise AssertionError(f"{relative} has no constant {name}")


def test_a_point_inside_india_s_frame_with_its_value_passes() -> None:
    layer = parsed_layer(collection(point(72.5, 23.0, deposits=3), point(70.25, 22.5, deposits=None)), SITES)
    assert (layer.features, layer.bounds) == (2, Frame(west=70.25, south=22.5, east=72.5, north=23.0))
    assert layer.layer["features"][1]["properties"] == {"deposits": None}


def test_a_coordinate_finer_than_the_map_keeps_is_refused() -> None:
    assert refused(collection(point(72.12345, 23.0, deposits=1)), SITES) == (
        "feature 1 gives [72.12345, 23.0]; coordinates carry at most 4 decimals"
    )
    rivers = collection(feature({"type": "LineString", "coordinates": [[72.1234, 23.0], [72.5, 23.1]]}))
    assert refused(rivers, RIVERS) == "feature 1 gives [72.1234, 23.0]; coordinates carry at most 3 decimals"
    assert parsed_layer(TRAILING_ZEROS, SITES).features == 1


def test_a_coordinate_outside_india_s_frame_is_refused() -> None:
    assert refused(collection(point(72.5, 23.0, deposits=1), point(99.0, 23.0, deposits=1)), SITES) == (
        "feature 2 reaches [99.0, 23.0], outside India's frame; clip the layer to the Survey of India outline "
        "or the map's frame"
    )


def test_a_crs_other_than_wgs_84_is_refused_and_crs84_passes() -> None:
    assert refused(collection(point(72.5, 23.0, deposits=1), crs="urn:ogc:def:crs:EPSG::3857"), SITES) == (
        "a layer is in WGS 84 longitude and latitude, and its crs names urn:ogc:def:crs:EPSG::3857"
    )
    passing = collection(point(72.5, 23.0, deposits=1), crs="urn:ogc:def:crs:OGC:1.3:CRS84")
    assert parsed_layer(passing, SITES).features == 1


def test_a_geometry_its_layer_class_does_not_hold_is_refused() -> None:
    assert refused(collection(feature(square(72.5, 23.0, 0.1))), RIVERS) == (
        "feature 1 is a Polygon; RIVERS holds LineString or MultiLineString"
    )


def test_every_feature_gives_its_value_as_a_number_or_null() -> None:
    assert refused(collection(point(72.5, 23.0)), SITES) == (
        "feature 1 has no deposits: give its value, or null where it has no reading"
    )
    assert refused(collection(point(72.5, 23.0, deposits="three")), SITES) == (
        "feature 1 gives deposits as 'three'; a value is a number, or null"
    )
    assert parsed_layer(collection(point(72.5, 23.0, deposits=None)), SITES).features == 1


def test_a_lake_under_the_least_area_is_left_out_and_rings_close() -> None:
    assert ring_area(square(72.5, 23.0, 0.05)["coordinates"][0]) == pytest.approx(0.0025)
    assert refused(collection(feature(square(72.5, 23.0, 0.05))), LAKES) == (
        "feature 1 is under 0.004 square degree, which a LAKES layer leaves out"
    )
    assert parsed_layer(collection(feature(square(72.5, 23.0, 0.1))), LAKES).features == 1
    opened = {"type": "Polygon", "coordinates": [[[72.5, 23.0], [72.6, 23.0], [72.6, 23.1], [72.5, 23.1]]]}
    assert refused(collection(feature(opened)), LAKES) == (
        "feature 1 has a ring that is not closed or has under 4 positions"
    )


def test_a_file_that_is_no_feature_collection_is_refused() -> None:
    message = "a layer is a GeoJSON FeatureCollection in UTF-8 JSON"
    assert refused(b"district,value\nKachchh,1\n", SITES) == message
    assert refused(json.dumps({"type": "Feature"}).encode(), SITES) == message
    assert refused(collection(), SITES) == "a layer holds 1 to 5000 features"


def test_a_plan_is_refused_for_each_rule_it_breaks() -> None:
    assert layer_problems("EPSG:4326", RIVERS) == []
    assert layer_problems("WGS 84", SITES) == []
    coarse = RIVERS.model_copy(update={"simplified_to": 0.02})
    assert layer_problems("WGS 84 / UTM zone 43N (EPSG:32643)", coarse) == [
        "a map layer is in WGS 84 longitude and latitude (EPSG:4326), not 'WGS 84 / UTM zone 43N (EPSG:32643)'",
        "rivers are simplified no further than 0.01 degree, not 0.02",
    ]
    unstated = RIVERS.model_copy(
        update={"simplified_to": None, "method": "inverse distance weighted, smoothed"}
    )
    assert layer_problems("EPSG:4326", unstated) == [
        "give the tolerance the rivers were simplified to, at most 0.01 degree",
        "a layer's values are what its dataset states for each place, never interpolated, kriged or smoothed",
    ]
    simplified = SITES.model_copy(update={"simplified_to": 0.001, "unit": None})
    assert layer_problems("EPSG:4326", simplified) == [
        "point sites are points, and a point is never simplified",
        "the value in deposits names its variable and the unit its dataset states",
    ]


def test_a_plan_names_a_known_class_and_a_plain_property() -> None:
    with pytest.raises(ValidationError):
        MapLayerPlan.model_validate({"layerClass": "OCEANS", "method": "as published"})
    with pytest.raises(ValidationError):
        MapLayerPlan.model_validate(
            {"layerClass": "RIVERS", "valueProperty": "rain (mm)", "method": "as published"}
        )


def test_a_layer_record_takes_its_plan_s_problems_and_a_geojson_upload() -> None:
    proposal = DatasetProposal.model_validate(RECORD | {"crs": "EPSG:3857", "layer": SITES.model_dump()})
    assert record_problems(proposal) == [
        "a map layer is in WGS 84 longitude and latitude (EPSG:4326), not 'EPSG:3857'"
    ]
    assert upload_types(proposal) == ["application/geo+json"]
    assert upload_types(DatasetProposal.model_validate(RECORD)) == ["text/csv"]


def test_the_review_names_every_check_a_stored_layer_passed() -> None:
    assert layer_checks(RIVERS) == [
        "Its licence is open and lets anyone redistribute the data",
        "It is in WGS 84 longitude and latitude (EPSG:4326)",
        "Simplified to 0.008 degree, within the 0.01 its layer class allows",
        "Every coordinate lies inside India's frame, at the precision the map keeps",
        "Its method names no interpolation or smoothing",
    ]
    assert "Every feature gives its deposits as a number, or null where it has no reading" in layer_checks(
        SITES
    )
    assert "Points, never simplified" in layer_checks(SITES)


def test_the_tolerances_are_the_site_s_own_layers_and_the_frame_is_the_map_s() -> None:
    assert LAYER_CLASSES["RIVERS"].tolerance == constant("tools/maplayers/rivers.py", "TOLERANCE")
    assert LAYER_CLASSES["LAKES"].tolerance == constant("tools/maplayers/rivers.py", "LAKE_TOLERANCE")
    assert LAYER_CLASSES["LAKES"].min_area == constant("tools/maplayers/rivers.py", "LAKE_MIN_AREA")
    assert LAYER_CLASSES["COUNTRY_OUTLINES"].tolerance == constant("tools/basemap/build.py", "TOLERANCE")
    assert LAYER_CLASSES["RELIEF_BANDS"].tolerance == constant("tools/maplayers/relief.py", "BAND_TOLERANCE")
    assert LAYER_CLASSES["BASIN_REACHES"].tolerance == constant(
        "etl/geo/geo_etl/topology.py", "SIMPLIFY_DEGREES"
    )
    rows = {row["layer"]: row["tolerance"] for row in TABLE_ROW.finditer(reference_text("datasets"))}
    assert rows["district shapes, on a 0.001-degree grid"].startswith(
        f"{LAYER_CLASSES['DISTRICT_SHAPES'].tolerance:g} "
    )
    bounds = {
        match["name"]: float(match["value"]) for match in BOUND.finditer(INDIA_BOUNDS.read_text("utf-8"))
    }
    assert (INDIA_FRAME.west, INDIA_FRAME.south, INDIA_FRAME.east, INDIA_FRAME.north) == (
        bounds["minLongitude"],
        bounds["minLatitude"],
        bounds["maxLongitude"],
        bounds["maxLatitude"],
    )


def test_the_dataset_guide_states_the_layer_limits_the_checks_apply() -> None:
    guide = " ".join(reference_text("datasets").split())
    assert f"at most {LAYER_BYTES_MAX // (1024 * 1024)} MB and {FEATURES_MAX} features" in guide
    decimals = (
        f"more than {NUMBER_WORDS[LINE_DECIMALS]} decimals ({NUMBER_WORDS[POINT_DECIMALS]} for a point)"
    )
    assert decimals in guide
    assert [name for name in LAYER_CLASSES if f"`{name}`" not in guide] == []
