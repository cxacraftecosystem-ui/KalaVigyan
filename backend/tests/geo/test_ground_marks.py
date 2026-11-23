import uuid
from dataclasses import replace
from typing import Any

import pytest
from pydantic import ValidationError

from app.data.river_names import NamedRiver
from app.geo.place_ground import ABROAD_REACH_KM, craft_ground, direct_measures, pins_in_reach
from app.research.datasets import DatasetRef
from app.research.rivers import HYDRORIVERS_DATASET_CODE
from app.research.why_here import CraftGround, GroundPin, GroundRiver
from app.services import place_ground as service
from app.services.chapter_context import PlacePoint
from app.services.curated_index import IndexPlace

from ..contracts.golden import golden_json
from .ground_fixtures import GOLDEN_GROUND, ORIGIN, fixture_inputs, fixture_layers, fixture_place

OSM_NAMES = "OSM_RIVER_NAMES"
WIKIDATA_NAMES = "WIKIDATA_RIVER_NAMES"
ABROAD = "Q9900001"


def pin(**changes: Any) -> GroundPin:
    fields: dict[str, Any] = {
        "key": f"abroad-{ABROAD}",
        "name": "Abroad region",
        "roles": ["ORIGIN"],
        "country": "Pakistan",
        "wikidata_id": ABROAD,
        "longitude": ORIGIN[0],
        "latitude": ORIGIN[1] + 4.0,
    }
    return GroundPin(**{**fields, **changes})


def dataset(code: str, attribution: str | None = None) -> DatasetRef:
    return DatasetRef(
        code=code,
        title=f"{code} title",
        publisher=None,
        edition="1",
        period="static",
        native_resolution="vector",
        licence="Open",
        licence_url=None,
        attribution=attribution,
        citation=None,
        url=None,
    )


def river(**changes: Any) -> GroundRiver:
    fields: dict[str, Any] = {
        "key": "river-9-7-9",
        "name": "Test River",
        "main_riv": 9,
        "reach_ids": [7, 8, 9],
        "hydrorivers": dataset(HYDRORIVERS_DATASET_CODE),
        "names": dataset(OSM_NAMES, "© OpenStreetMap contributors"),
    }
    return GroundRiver(**{**fields, **changes})


def named(name: str, code: str, reach_ids: tuple[int, ...]) -> NamedRiver:
    return NamedRiver(
        name=name,
        dataset_code=code,
        refs=("ref-1",),
        main_riv=reach_ids[-1],
        reach_ids=reach_ids,
        district_lgds=(449,),
    )


def index_place(key: str, name: str, **changes: Any) -> IndexPlace:
    fields: dict[str, Any] = {
        "key": key,
        "name": name,
        "kind": "REGION",
        "role": "ORIGIN",
        "district": None,
        "district_lgd": None,
        "state": None,
        "state_lgd": None,
        "country": "Pakistan",
        "wikidata_id": ABROAD,
        "location_id": None,
        "concept_id": uuid.UUID("9e0d0000-0000-4000-8000-0000000000c1"),
        "claim_ids": [uuid.UUID("9e0d0000-0000-4000-8000-0000000000c2")],
    }
    return IndexPlace(**{**fields, **changes})


def test_a_place_abroad_is_in_reach_within_500_km_of_a_located_place() -> None:
    near, far = pin(latitude=ORIGIN[1] + 4.0), pin(key="abroad-Q9900002", latitude=ORIGIN[1] + 4.6)
    assert ABROAD_REACH_KM == 500
    assert pins_in_reach([fixture_place()], [near, far]) == [near]
    assert pins_in_reach(
        [fixture_place(), fixture_place(key="place-2", latitude=ORIGIN[1] + 1.0)], [far]
    ) == [far]


def test_the_frame_reaches_a_place_abroad_and_a_ground_without_marks_reads_as_before() -> None:
    measures = direct_measures(fixture_layers())
    ground = craft_ground(replace(fixture_inputs(), abroad=(pin(),), rivers=(river(),)), measures)
    assert ground is not None
    assert ground.frame.holds(ORIGIN[0], ORIGIN[1] + 4.0)
    assert ([p.key for p in ground.abroad], [r.key for r in ground.rivers]) == (
        [f"abroad-{ABROAD}"],
        ["river-9-7-9"],
    )
    beyond = craft_ground(replace(fixture_inputs(), abroad=(pin(latitude=ORIGIN[1] + 4.6),)), measures)
    assert beyond is not None
    assert beyond.model_dump(mode="json", by_alias=True) == golden_json(GOLDEN_GROUND)


def test_a_river_cites_hydrorivers_for_its_lines_and_another_dataset_for_its_name() -> None:
    assert river().names.attribution == "© OpenStreetMap contributors"
    with pytest.raises(ValidationError, match="is drawn from HYDRORIVERS_1_0"):
        river(hydrorivers=dataset(OSM_NAMES))
    with pytest.raises(ValidationError, match="is named by WIKIDATA_RIVER_NAMES or OSM_RIVER_NAMES"):
        river(names=dataset(HYDRORIVERS_DATASET_CODE))
    assert river(names=dataset(WIKIDATA_NAMES)).names.code == WIKIDATA_NAMES
    with pytest.raises(ValidationError, match="each of its reaches once"):
        river(reach_ids=[7, 7, 9])


def test_every_mark_sits_once_inside_the_frame() -> None:
    ground = golden_json(GOLDEN_GROUND)
    outside = pin(latitude=ground["frame"]["north"] + 1.0).model_dump(mode="json", by_alias=True)
    with pytest.raises(ValidationError, match="the frame holds every place abroad"):
        CraftGround.model_validate({**ground, "abroad": [outside]})
    twice = pin(key=ground["places"][0]["key"], latitude=ORIGIN[1]).model_dump(mode="json", by_alias=True)
    with pytest.raises(ValidationError, match="listed once"):
        CraftGround.model_validate({**ground, "abroad": [twice]})


def test_a_place_abroad_named_twice_is_one_pin_with_both_roles_at_its_stored_point() -> None:
    places = [
        index_place("L01", "Sindh"),
        index_place("L02", "Sindh", role="PRACTISED"),
        index_place("L03", "Unplaced", wikidata_id="Q9900009"),
    ]
    points = {ABROAD: PlacePoint(ABROAD, latitude=25.89442, longitude=68.52478)}
    assert service.abroad_pins(places, points) == (
        GroundPin(
            key=f"abroad-{ABROAD}",
            name="Sindh",
            roles=["PRACTISED", "ORIGIN"],
            country="Pakistan",
            wikidata_id=ABROAD,
            longitude=68.525,
            latitude=25.894,
        ),
    )


def test_a_dossier_river_is_the_one_river_the_names_dataset_matches(monkeypatch: pytest.MonkeyPatch) -> None:
    suran = named("Suran", OSM_NAMES, (7, 8, 9))
    matches = {("Dhamadka River (Suran)", 449): suran, ("Suran", 449): suran}
    monkeypatch.setattr(service, "place_river", lambda name, lgd: matches.get((name, lgd)))
    places = [
        index_place(
            "L01", "Dhamadka River (Suran)", kind="RIVER", country="India", district_lgd=449, wikidata_id=None
        ),
        index_place("L02", "Suran", kind="RIVER", country="India", district_lgd=449, wikidata_id=None),
        index_place(
            "L03", "Unnamed stream", kind="RIVER", country="India", district_lgd=449, wikidata_id=None
        ),
        index_place("L04", "Suran", kind="VILLAGE", country="India", district_lgd=449, wikidata_id=None),
    ]
    assert service.named_rivers(places) == (suran,)


def test_a_river_is_drawn_only_with_both_its_dataset_rows() -> None:
    lines, names = dataset(HYDRORIVERS_DATASET_CODE), dataset(OSM_NAMES, "© OpenStreetMap contributors")
    suran, other = named("Suran", OSM_NAMES, (7, 8, 9)), named("Other", WIKIDATA_NAMES, (4, 5))
    [drawn] = service.ground_rivers([suran, other], {HYDRORIVERS_DATASET_CODE: lines, OSM_NAMES: names})
    assert drawn == GroundRiver(
        key="river-9-7-9", name="Suran", main_riv=9, reach_ids=[7, 8, 9], hydrorivers=lines, names=names
    )
    assert service.ground_rivers([suran], {OSM_NAMES: names}) == ()
