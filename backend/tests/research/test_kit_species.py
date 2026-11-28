from typing import Any

import pytest
from pydantic import ValidationError

from app.research.component_specs import checked_spec
from app.research.component_specs_kit import SpeciesPart
from app.research.component_specs_kit_scene import KitScene

from . import science_spec_fixtures as science

IRON = {"part": "species", "role": "reactant", "material": "--dye-kut", "label": "u0601"}
OXYGEN = {"part": "species", "role": "reagent", "label": "u0602"}
BLACK = {"part": "species", "role": "product", "label": "u0603"}
CLOTH = {"part": "cloth", "form": "swatch", "material": "--dye-madder", "label": "u0604"}
REACTS = {"parts": [IRON, OXYGEN, BLACK], "motion": "react"}


def species(count: int, role: str = "reactant") -> list[dict[str, Any]]:
    return [{"part": "species", "role": role, "label": f"u06{10 + at}"} for at in range(count)]


def test_a_scene_holds_up_to_eight_species_of_one_reaction_and_still_three_other_parts() -> None:
    scene = KitScene.model_validate({"parts": [*species(5), *species(3, "product")], "motion": "react"})
    assert [part.role for part in scene.parts if isinstance(part, SpeciesPart)].count("product") == 3
    with pytest.raises(ValidationError, match="at most 8"):
        KitScene.model_validate({"parts": [*species(6), *species(3, "product")]})
    with pytest.raises(ValidationError, match="at most 3 parts, or at most 8 when every part is a species"):
        KitScene.model_validate({"parts": [*species(3), CLOTH]})
    assert len(KitScene.model_validate({"parts": [*species(2), CLOTH]}).parts) == 3


def test_the_react_motion_explains_a_product_made_from_a_species_and_nothing_else() -> None:
    assert KitScene.model_validate(REACTS).motion == "react"
    with pytest.raises(ValidationError, match="the react motion explains a product species part"):
        KitScene.model_validate({"parts": [IRON, OXYGEN], "motion": "react"})
    with pytest.raises(ValidationError, match="the react motion explains a product species part"):
        KitScene.model_validate({"parts": [BLACK], "motion": "react"})
    with pytest.raises(ValidationError, match="the take motion explains a cloth part"):
        KitScene.model_validate({"parts": [IRON, BLACK], "motion": "take"})


def test_only_a_reactant_breaks_and_a_species_takes_only_a_depicted_material() -> None:
    assert SpeciesPart.model_validate({**IRON, "breaks": True}).breaks
    with pytest.raises(ValidationError, match="only a reactant breaks"):
        SpeciesPart.model_validate({**BLACK, "breaks": True})
    with pytest.raises(ValidationError, match="only a reactant breaks"):
        SpeciesPart.model_validate({**OXYGEN, "breaks": True})
    with pytest.raises(ValidationError, match="depicted material"):
        SpeciesPart.model_validate({**IRON, "material": "--indigo"})
    with pytest.raises(ValidationError, match="role"):
        SpeciesPart.model_validate({**IRON, "role": "catalyst"})
    assert "material" not in SpeciesPart.model_validate(OXYGEN).model_dump(mode="json", by_alias=True)


def test_a_reaction_step_takes_a_species_scene_in_its_art_and_a_diagram_panel_takes_one_too() -> None:
    spec = science.reaction_player()
    spec["scenes"] = []
    spec["steps"][0]["scene"] = {"where": "u0611", "art": REACTS}
    spec["steps"][1]["scene"] = {"where": "u0612", "art": {"parts": [IRON, BLACK], "motion": "react"}}
    steps = checked_spec("reaction_player", spec).model_dump(mode="json", by_alias=True)["steps"]
    assert [part["role"] for part in steps[0]["scene"]["art"]["parts"]] == ["reactant", "reagent", "product"]
    assert steps[1]["scene"]["art"]["motion"] == "react"


def test_a_species_is_drawn_by_its_material_or_by_a_mark_of_a_colourless_substance_never_both() -> None:
    for mark in ("clear", "gas", "ion"):
        part = SpeciesPart.model_validate({**OXYGEN, "mark": mark})
        assert part.mark == mark and not part.uncoloured
    assert SpeciesPart.model_validate(OXYGEN).uncoloured and not SpeciesPart.model_validate(IRON).uncoloured
    with pytest.raises(ValidationError, match="its material's colour or by its mark"):
        SpeciesPart.model_validate({**IRON, "mark": "clear"})
    with pytest.raises(ValidationError, match="mark"):
        SpeciesPart.model_validate({**OXYGEN, "mark": "liquid"})
    assert "mark" not in SpeciesPart.model_validate(IRON).model_dump(mode="json", by_alias=True)
