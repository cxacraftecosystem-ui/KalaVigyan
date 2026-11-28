import json
from pathlib import Path
from typing import Any

from app.research.page_report import ReportInput
from app.research.page_report_design import DESIGN_RULE
from app.research.page_report_rules import checked_rules
from app.research.page_report_species import species_colour_problems

from .page_report_rules_fixtures import FIGURE, page_document

AJRAKH_SPECS = Path(__file__).resolve().parents[2] / "app" / "data" / "monographs" / "Kutch-Ajrakh" / "specs"
PLAYER = "sanganeri-hand-block-printing/chemistry/alizarin-alum-iron-player"
NAMES = {
    "u5009": "alizarin",
    "u5010": "alum, aluminium sulphate",
    "u5011": "red",
    "u5018": "oxygen in the air",
}


def species(role: str, label: str, **colour: str) -> dict[str, Any]:
    return {"part": "species", "role": role, "label": label, "breaks": False, **colour}


def lane(*items: tuple[str, str]) -> dict[str, Any]:
    names = [
        {"item": "species", "swatch": swatch, "name": [name], "state": [], "cid": None}
        for name, swatch in items
    ]
    return {"parts": [{"part": "lane", "label": "Species in this step", "items": names}]}


def player(parts: list[dict[str, Any]], swatches: tuple[tuple[str, str], ...]) -> dict[str, Any]:
    step = {
        "name": "Alum takes alizarin",
        "scene": {"where": "u5008", "art": {"parts": parts, "motion": "react"}},
        "chemistry": lane(*swatches),
    }
    return {"id": "rp-red", "steps": [step], "scenes": []}


def text(unit: str) -> str:
    return NAMES.get(unit, "")


SANGANER = player(
    [
        species("reactant", "u5009"),
        species("reagent", "u5010"),
        species("product", "u5011", material="--dye-madder"),
    ],
    (("alizarin", "clear"), ("alum, aluminium sulphate", "clear"), ("red", "--dye-madder")),
)


def test_a_reaction_step_drawing_species_with_no_colour_names_them_the_fields_that_colour_them_and_the_tool() -> (
    None
):
    (found,) = species_colour_problems(PLAYER, SANGANER, text)
    assert found.startswith(
        f"{PLAYER}, step 1 (Alum takes alizarin): its scene draws 'alizarin', 'alum, aluminium sulphate' with no "
        "colour, each an empty outline; give each species part material"
    )
    assert "or mark clear, gas or ion for a colourless substance" in found and found.endswith(
        "with edit_draft"
    )


def test_a_step_whose_species_each_have_a_colour_or_a_mark_and_a_matching_lane_passes() -> None:
    filled = player(
        [
            species("reactant", "u5009", material="--dye-madder"),
            species("reagent", "u5010", mark="clear"),
            species("reagent", "u5018", mark="gas"),
            species("product", "u5011", material="--dye-madder"),
        ],
        (("alizarin", "--dye-madder"), ("alum, aluminium sulphate", "clear"), ("oxygen in the air", "gas")),
    )
    assert species_colour_problems(PLAYER, filled, text) == []


def test_a_lane_marking_clear_a_species_its_scene_colours_names_the_swatch_to_give() -> None:
    coloured = player(
        [
            species("reactant", "u5009", material="--dye-madder"),
            species("product", "u5011", material="--dye-madder"),
        ],
        (("Alizarin", "clear"), ("red", "--dye-madder")),
    )
    assert species_colour_problems(PLAYER, coloured, text) == [
        f"{PLAYER}, step 1 (Alum takes alizarin): its lane marks 'Alizarin' clear, an empty dashed square, while "
        "its scene draws it in --dye-madder; give the lane's swatch --dye-madder, in the draft with edit_draft"
    ]


def test_kutch_ajrakh_s_players_draw_their_own_scenes_and_none_is_named() -> None:
    files = sorted(AJRAKH_SPECS.glob("*player.json"))
    assert len(files) == 4
    for path in files:
        spec = json.loads(path.read_text(encoding="utf-8"))
        assert species_colour_problems(path.stem, spec, lambda unit: unit) == []


def test_the_design_rule_fails_a_page_whose_player_draws_an_uncoloured_species_and_passes_it_filled() -> None:
    document = page_document()
    specs = {**document.specs, FIGURE: SANGANER}
    verdict, found = checked_rules(ReportInput(document=document.model_copy(update={"specs": specs})))[
        DESIGN_RULE
    ]
    assert verdict == "FAIL" and any(
        line.startswith(f"{FIGURE}, step 1 (Alum takes alizarin)") for line in found
    )
    assert checked_rules(ReportInput(document=document))[DESIGN_RULE][0] == "PASS"
