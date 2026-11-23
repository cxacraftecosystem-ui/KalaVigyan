import json
import uuid
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from app.data.design_palette import THEMES
from app.data.kind_fixture_files import KIND_FIXTURE_ORDER, KIND_FIXTURES_DIR, kind_fixtures
from app.research.component_specs import CONTRIBUTABLE_KINDS, checked_spec, not_contributable
from app.research.component_specs_general_delivery import DeliveredUnit, spec_problems, unit_problems
from app.services.drawing_themes import themed_markup
from app.services.kind_fixture_specs import served_kind_fixtures

REPO = Path(__file__).resolve().parents[3]
DOSSIERS = REPO / "backend" / "app" / "data" / "curation"
KUTCH = "Kutch-Ajrakh"
WITHHELD = ("language_switch", "citation_tool", "credits", "picture_plate", "model_explainer", "timeline_map")


def _fixtures() -> list[dict[str, Any]]:
    return [json.loads(path.read_text(encoding="utf-8")) for path in sorted(KIND_FIXTURES_DIR.glob("*.json"))]


def _dossier(craft: str) -> dict[str, Any]:
    return json.loads((DOSSIERS / f"{craft}.json").read_text(encoding="utf-8"))


def _claim_ids(fixture: dict[str, Any]) -> dict[str, uuid.UUID]:
    return {key: uuid.uuid5(uuid.NAMESPACE_URL, f"{fixture['craft']}/{key}") for key in fixture["facts"]}


def _units(fixture: dict[str, Any]) -> dict[str, DeliveredUnit]:
    ids = _claim_ids(fixture)
    return {
        ref: DeliveredUnit(text=unit["text"], claim_ids=[ids[claim] for claim in unit["claims"]])
        for ref, unit in fixture["units"].items()
    }


FIXTURE_LIST = _fixtures()


def test_every_contributable_kind_is_proven_on_a_craft_other_than_kutch_ajrakh() -> None:
    assert {fixture["kind"] for fixture in FIXTURE_LIST} == set(CONTRIBUTABLE_KINDS)
    assert len(CONTRIBUTABLE_KINDS) == 22
    assert all(fixture["craft"] != KUTCH for fixture in FIXTURE_LIST)
    assert {"Bidriware", "Blue-Pottery-Of-Jaipur", "Bastar-Dhokra"} <= {f["craft"] for f in FIXTURE_LIST}


def test_page_tools_and_the_authored_page_s_own_kinds_are_not_contributable() -> None:
    assert not set(WITHHELD) & set(CONTRIBUTABLE_KINDS)
    assert not_contributable("language_switch") == (
        "the site builds the language_switch of every page from its data, so it is never delivered"
    )
    assert "runs an authored page's own script" in (not_contributable("model_explainer") or "")
    assert not_contributable("chart") is None


@pytest.mark.parametrize("fixture", FIXTURE_LIST, ids=lambda fixture: fixture["label"])
def test_each_fixture_passes_its_spec_model_and_the_delivery_gates(fixture: dict[str, Any]) -> None:
    units = _units(fixture)
    ids = _claim_ids(fixture)
    cited = {
        ids[key]: [fact["text"], *(quote["quote"] for quote in fact["quotes"])]
        for key, fact in fixture["facts"].items()
    }
    assert spec_problems(fixture["kind"], fixture["spec"], units) == []
    assert unit_problems(units, cited) == []


@pytest.mark.parametrize("fixture", FIXTURE_LIST, ids=lambda fixture: fixture["label"])
def test_each_fixture_cites_its_craft_s_stored_facts_word_for_word(fixture: dict[str, Any]) -> None:
    dossier = _dossier(fixture["craft"])
    claims = {claim["id"]: claim for claim in dossier["claims"]}
    sources = {source["id"]: source for source in dossier["sources"]}
    for key, fact in fixture["facts"].items():
        stored = claims[key]
        assert fact["text"] == stored["text"]
        assert [(q["source"], q["locator"], q["quote"]) for q in fact["quotes"]] == [
            (q["sourceId"], q["locator"], q["quote"]) for q in stored["quotes"]
        ]
    for key, source in fixture["sources"].items():
        assert (source["title"], source["url"]) == (sources[key]["title"], sources[key].get("url"))
    cited = {claim for unit in fixture["units"].values() for claim in unit["claims"]}
    assert cited == set(fixture["facts"])


def test_a_material_no_record_holds_cannot_be_depicted() -> None:
    swatches = next(fixture for fixture in FIXTURE_LIST if fixture["kind"] == "swatch_cards")["spec"]
    colours = swatches["colours"]
    assert colours[0]["after"]["dye"] == "bidri-black"
    checked_spec("swatch_cards", swatches)
    unknown = {**colours[0], "after": {**colours[0]["after"], "dye": "ultramarine"}}
    with pytest.raises(ValidationError, match="dye"):
        checked_spec("swatch_cards", {**swatches, "colours": [unknown]})


def test_a_drawing_paints_only_recorded_materials() -> None:
    dip = next(fixture for fixture in FIXTURE_LIST if fixture["kind"] == "dip_player")["spec"]
    assert dip["dips"] == ["--dye-bidri-white", "--dye-bidri-black"]
    with pytest.raises(ValidationError, match="depicted material"):
        checked_spec("dip_player", {**dip, "dips": ["--dye-ultramarine"]})


def test_dip_phases_are_the_spec_s_own_words_each_named_once() -> None:
    dip = next(fixture for fixture in FIXTURE_LIST if fixture["kind"] == "dip_player")["spec"]
    assert [phase["pose"] for phase in dip["phases"]] == ["solution", "lifted", "oiled"]
    assert "equation" not in dip
    twice = [dip["phases"][0], dip["phases"][0]]
    with pytest.raises(ValidationError, match="each of its phases once"):
        checked_spec("dip_player", {**dip, "phases": twice})


def test_the_preview_is_served_its_fixtures_in_page_order_with_each_drawing_s_four_themes() -> None:
    served = served_kind_fixtures()
    assert [fixture["label"] for fixture in served] == [fixture["label"] for fixture in kind_fixtures()]
    assert len(served) == len(KIND_FIXTURE_ORDER) == 24
    (drawing,) = [fixture for fixture in served if fixture["kind"] == "drawing"]
    themes = drawing["spec"]["themes"]
    assert list(themes) == list(THEMES) == ["light", "dark", "hcLight", "hcDark"]
    assert themes == {theme: themed_markup(drawing["spec"]["svg"], theme) for theme in THEMES}
    assert themes["light"] != themes["dark"]
    others = [
        (served_one, filed)
        for served_one, filed in zip(served, kind_fixtures(), strict=True)
        if filed["kind"] != "drawing"
    ]
    assert all(served_one == filed for served_one, filed in others)
    assert all("themes" not in fixture["spec"] for fixture in kind_fixtures())
