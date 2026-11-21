import dataclasses
import json
from pathlib import Path

from app.services.component_places import (
    PlaceBinding,
    PlacesHeld,
    component_binding,
    joined_places,
    practised_states,
)
from app.services.component_places_held import piece_texts
from app.services.monograph_generated_assembly import assembled_document
from app.services.monograph_generated_drawings import Drawings

from .generated_parts import component, fragment_monograph, generated

GUJARAT, UTTAR_PRADESH = 24, 9
KACHCHH, JAIPUR, AZAMGARH = 449, 102, 123
RAINFALL = "shared/climate/kachchh-annual-rainfall-chart"
DRYING = "shared/process/cloth-drying-photo"
OWN_DRYING = "bagh-print/process/cloth-drying-photo"
AZAMGARH_PAGE = PlacesHeld(frozenset({AZAMGARH}), frozenset({UTTAR_PRADESH}))
KACHCHH_PAGE = PlacesHeld(frozenset({KACHCHH}), frozenset({GUJARAT}))
SALT_FLAT = "Printed cloth dries on the salt flat of Kachchh."


def binding(
    *, kind: str = "diagram", field: str = "CHEMISTRY", places: tuple[str, ...] = (), text: str = ""
) -> PlaceBinding:
    return component_binding(kind=kind, field=field, places=places, texts=[text])


def test_a_place_subject_binds_a_component_to_its_district() -> None:
    found = binding(kind="picture_plate", field="GEOGRAPHY", places=(f"lgd:{KACHCHH}",))
    assert found == PlaceBinding(bound=True, districts=frozenset({KACHCHH}))
    assert found.held_by(KACHCHH_PAGE)
    assert not found.held_by(AZAMGARH_PAGE)


def test_a_place_its_units_name_binds_it_to_the_narrowest_place_named() -> None:
    assert binding(text="A carver in Jaipur cuts the block.") == PlaceBinding(True, frozenset({JAIPUR}))
    assert binding(text="Printers in Gujarat wash the cloth.") == PlaceBinding(
        True, states=frozenset({GUJARAT})
    )
    assert binding(text="Kachchh, in Gujarat, is dry.") == PlaceBinding(True, frozenset({KACHCHH}))
    assert binding(text="Printers in Gujarat wash the cloth.").held_by(KACHCHH_PAGE)
    assert not binding(text="A carver in Jaipur cuts the block.").held_by(KACHCHH_PAGE)


def test_a_region_or_climate_figure_is_bound_even_when_it_names_no_place() -> None:
    for found in (binding(kind="map_layer", field="GEOGRAPHY"), binding(kind="chart", field="CLIMATE")):
        assert found == PlaceBinding(bound=True)
        assert not found.held_by(KACHCHH_PAGE)


def test_a_component_that_names_no_place_may_go_on_any_page() -> None:
    found = binding(text="Alum fixes the madder red.")
    assert found == PlaceBinding()
    assert found.held_by(PlacesHeld())


def test_a_family_or_category_holds_every_place_of_its_crafts() -> None:
    held = joined_places([KACHCHH_PAGE, AZAMGARH_PAGE])
    assert held == PlacesHeld(frozenset({KACHCHH, AZAMGARH}), frozenset({GUJARAT, UTTAR_PRADESH}))
    assert binding(places=(f"lgd:{KACHCHH}",)).held_by(held)


def test_a_piece_s_units_are_read_from_its_delivery_and_never_from_a_monograph_it_cannot_name() -> None:
    units = {
        "u5001": {"text": SALT_FLAT, "claimIds": []},
        "u5002": {"text": "Alum fixes red.", "claimIds": []},
    }
    assert piece_texts(DRYING, {"delivered": {"spec": {}, "units": units}}) == (SALT_FLAT, "Alum fixes red.")
    assert piece_texts(DRYING, {"monograph": "../Kutch-Ajrakh"}) == ()
    assert piece_texts(DRYING, {"monograph": "No-Such-Monograph"}) == ()
    assert piece_texts(None, {"monograph": "Kutch-Ajrakh"}) == ()


def test_a_craft_s_states_of_practice_are_the_register_states_it_names() -> None:
    assert practised_states(["Gujarat", " Uttar Pradesh "]) == frozenset({GUJARAT, UTTAR_PRADESH})
    assert practised_states(["All India"]) == frozenset()


def _monograph(root: Path) -> Path:
    fragment_monograph(root)
    folder = root / "Kutch-Ajrakh"
    content = json.loads((folder / "content.json").read_text(encoding="utf-8"))
    unit = {"chapter": "process", "tag": "p", "field": None, "nodes": [SALT_FLAT], "claimIds": []}
    content["units"]["u10"] = unit
    (folder / "content.json").write_text(json.dumps(content), encoding="utf-8")
    for label in (RAINFALL, DRYING, OWN_DRYING):
        spec = {"caption": "u10"} if label != RAINFALL else {"setting": "figure"}
        (folder / "specs" / (label.replace("/", "__") + ".json")).write_text(
            json.dumps(spec), encoding="utf-8"
        )
    return root


def _drawn(root: Path, places: PlacesHeld, *found: object) -> set[str]:
    built = assembled_document(generated(components=found, places=places), Drawings(root=root))
    assert built is not None
    return {entry.label for entry in built.content.components}


def test_a_page_borrows_a_district_figure_only_when_it_is_about_that_district(tmp_path: Path) -> None:
    root = _monograph(tmp_path)
    rainfall = dataclasses.replace(
        component(RAINFALL), kind="chart", field="CLIMATE", subjects=(f"place:lgd:{KACHCHH}",), borrowed=True
    )
    assert RAINFALL not in _drawn(root, AZAMGARH_PAGE, rainfall)
    assert RAINFALL in _drawn(root, KACHCHH_PAGE, rainfall)


def test_a_borrowed_picture_whose_caption_names_another_place_is_left_out_but_an_own_one_stays(
    tmp_path: Path,
) -> None:
    root = _monograph(tmp_path)
    borrowed = dataclasses.replace(
        component(DRYING), kind="picture_plate", field="PROCESS", subjects=(), borrowed=True
    )
    own = dataclasses.replace(component(OWN_DRYING), kind="picture_plate", field="PROCESS", subjects=())
    shown = _drawn(root, AZAMGARH_PAGE, borrowed, own)
    assert DRYING not in shown
    assert OWN_DRYING in shown
    assert DRYING in _drawn(root, KACHCHH_PAGE, borrowed)
