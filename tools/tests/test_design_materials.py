from __future__ import annotations

import json
from typing import Any

import pytest

from design.build import build, render
from design.checks import validate
from design.material_lists import python_list, typescript_list
from design.materials import Material, load_materials, material_names, materials_from
from design.system import System, load_system
from design_tokens import REPO_ROOT

SYSTEM = load_system()
OUTPUTS, VIOLATIONS = render(SYSTEM)
DOSSIERS = REPO_ROOT / "backend" / "app" / "data" / "curation"
KUTCH = "Kutch-Ajrakh"
RECORD = {
    "token": "dye-test",
    "craft": "Bidriware",
    "material": "M01",
    "claims": ["C070"],
    "hex": "#D6D5CE",
    "shows": "A test swatch.",
}


def _dossier(slug: str) -> dict[str, Any]:
    return json.loads((DOSSIERS / f"{slug}.json").read_text(encoding="utf-8"))


def _with(material: Material) -> System:
    return System(SYSTEM.data, (material,))


def test_kutch_ajrakh_s_dyes_are_the_first_records_and_draw_as_the_approved_board() -> None:
    css = OUTPUTS["tokens.css"]
    for line in (
        "--dye-indigo: #253045;",
        "--dye-kut: #2A1C17;",
        "--dye-madder: #7E032C;",
        "--dip-4: #253045;",
    ):
        assert line in css
    kutch = [material.token for material in SYSTEM.materials if material.craft == KUTCH]
    assert len(kutch) == 21
    assert kutch[:3] == ["dye-cloth", "dye-harda", "dye-harda-dry"]
    assert build(SYSTEM)["specimen"]["dye-indigo"]["material"] == {
        "craft": KUTCH,
        "material": "M16",
        "claims": ["C087"],
        "colourStated": True,
    }


def test_materials_of_other_crafts_are_drawn_too() -> None:
    crafts = {material.craft for material in SYSTEM.materials}
    assert {"Bidriware", "Blue-Pottery-Of-Jaipur", "Bastar-Dhokra"} <= crafts
    assert "--dye-bidri-black: #232326;" in OUTPUTS["tokens.css"]
    assert VIOLATIONS == []


def test_each_record_names_a_material_and_facts_of_its_craft_s_dossier() -> None:
    for material in load_materials():
        dossier = _dossier(material.craft)
        assert dossier["craftSlug"] == material.craft
        assert material.material in {row["id"] for row in dossier["materials"]}, material.token
        assert set(material.claims) <= {row["id"] for row in dossier["claims"]}, material.token


def test_a_material_as_close_as_a_reserved_colour_is_refused() -> None:
    turmeric = SYSTEM.sem("turmeric", "light")
    near = Material("dye-test", "Bidriware", "M01", ("C070",), "A test swatch.", turmeric, True)
    tokens = build(_with(near))
    assert "specimen dye-test light 0.0 from turmeric" in validate(tokens, _with(near))


def test_a_blue_as_saturated_as_the_interactive_indigo_is_refused() -> None:
    indigo = SYSTEM.sem("indigo", "light")
    blue = Material("dye-test", "Bidriware", "M01", ("C070",), "A test swatch.", indigo, True)
    violations = validate(build(_with(blue)), _with(blue))
    assert any(violation.endswith("reads as the interactive indigo") for violation in violations)


@pytest.mark.parametrize(
    ("changes", "says"),
    [
        ({"oklch": [0.5, 0.05, 40]}, "once"),
        ({"claims": []}, "facts"),
        ({"material": "zinc"}, "dossier"),
        ({"token": "bidri-black"}, "depicted-material token"),
        ({"hex": "#d6d5ce"}, "capitals"),
        ({"colour": "black"}, "no field"),
    ],
)
def test_a_record_off_its_rules_is_refused(changes: dict[str, Any], says: str) -> None:
    with pytest.raises(ValueError, match=says):
        materials_from({"schemaVersion": 1, "materials": [{**RECORD, **changes}]})


def test_a_token_is_recorded_once_and_the_file_has_its_schema_version() -> None:
    with pytest.raises(ValueError, match="once"):
        materials_from({"schemaVersion": 1, "materials": [RECORD, RECORD]})
    with pytest.raises(ValueError, match="schema version"):
        materials_from({"schemaVersion": 2, "materials": [RECORD]})


def test_the_lists_name_each_dye_record_without_its_prefix_and_leave_the_dips_out() -> None:
    dip = Material("dip-1", KUTCH, "M16", ("C087",), "One dip.", "#5D7698", True)
    cloth = Material("dye-cloth", KUTCH, "M01", ("C064",), "Cloth.", "#F4F2EA", True)
    assert material_names([cloth, dip]) == ("cloth",)
    assert python_list(["cloth", "bidri-black"]) == (
        '__all__ = ["DEPICTED_MATERIALS"]\n\nDEPICTED_MATERIALS = (\n    "cloth",\n    "bidri-black",\n)\n'
    )
    assert typescript_list(["cloth"]) == 'export const DEPICTED_MATERIALS = ["cloth"] as const;\n'


def test_the_records_file_is_where_the_generator_reads_it() -> None:
    assert (REPO_ROOT / "tools" / "design" / "materials.json").is_file()
    assert OUTPUTS["depicted_materials.py"].startswith('__all__ = ["DEPICTED_MATERIALS"]')
    assert '"bidri-black"' in OUTPUTS["depictedMaterials.ts"]
