import copy
import uuid
from functools import cache
from typing import Any

import pytest

from app.core.errors import InvalidInput
from app.services.claim_seed import load_seed_claims, seed_id
from app.services.science_seed import SciencePlan, load_science_seed, science_seed_plan
from app.services.science_seed_prune import compound_key, seeded_compounds

MYROBALAN = "ie:machilipatnam-kalamkari.material.myrobalan-karakkaya"
TREATMENT = "ie:machilipatnam-kalamkari.process_stage.myrobalan-treatment"
SECOND_PRINTING = "ie:machilipatnam-kalamkari.process_stage.second-printing"
COPPER_POT = "ie:ajrakh.tool.copper-dye-pot"
RED_DYEING = "ie:ajrakh.process_stage.red-dyeing"


@cache
def plan() -> SciencePlan:
    return science_seed_plan(load_science_seed(), load_seed_claims())


def plan_with(change) -> SciencePlan:
    science = copy.deepcopy(load_science_seed())
    change(science)
    return science_seed_plan(science, load_seed_claims())


def use_of(material_key: str, stage_key: str) -> dict[str, Any]:
    key = f"{stage_key}|USES|{material_key.removeprefix('ie:')}"
    return next(row for row in plan().rows["stageMaterials"] if row["id"] == seed_id("stage-material", key))


def test_a_stage_whose_quote_states_another_role_takes_it_and_the_others_keep_the_material_s() -> None:
    assert use_of(MYROBALAN, SECOND_PRINTING)["role"] == "DYE"
    assert use_of(MYROBALAN, TREATMENT)["role"] == "MORDANT"


def test_a_tool_a_seeded_stage_uses_is_a_tool_stage_material_of_kind_other() -> None:
    use = use_of(COPPER_POT, RED_DYEING)
    assert (use["role"], use["stageId"], use["materialId"]) == (
        "TOOL",
        seed_id("stage", RED_DYEING),
        seed_id("material", COPPER_POT),
    )
    assert use["claimId"] is not None
    tool = next(row for row in plan().rows["materials"] if row["id"] == use["materialId"])
    assert (tool["name"], tool["kind"], tool["compoundId"]) == (
        "Copper dye pot and stirring sticks",
        "OTHER",
        None,
    )
    assert tool["conceptId"] == seed_id("concept", COPPER_POT)


def test_a_stage_role_that_is_not_a_material_role_is_refused() -> None:
    def wrong(science: dict[str, Any]) -> None:
        science["materials"][MYROBALAN]["stageRoles"] = {SECOND_PRINTING: "COLOURANT"}

    with pytest.raises(InvalidInput, match="COLOURANT"):
        plan_with(wrong)


def test_a_stage_role_for_a_stage_that_does_not_use_the_material_is_refused() -> None:
    def wrong(science: dict[str, Any]) -> None:
        science["materials"][MYROBALAN]["stageRoles"] = {RED_DYEING: "DYE"}

    with pytest.raises(InvalidInput, match="no USES edge"):
        plan_with(wrong)


def test_a_tool_listed_among_the_materials_is_refused() -> None:
    def wrong(science: dict[str, Any]) -> None:
        science["materials"][COPPER_POT] = {"kind": "OTHER", "role": "INPUT", "compound": None}

    with pytest.raises(InvalidInput, match="is listed among the materials"):
        plan_with(wrong)


def test_a_compound_is_keyed_by_the_slug_of_its_name() -> None:
    assert compound_key("Iron(II) acetate") == "iron-ii-acetate"
    assert compound_key("Potassium alum") == "potassium-alum"

    def wrong(science: dict[str, Any]) -> None:
        science["compounds"][0]["key"] = "ferrous-acetate"

    with pytest.raises(InvalidInput, match="must be keyed iron-ii-acetate"):
        plan_with(wrong)


def test_only_an_unplanned_compound_with_the_seed_id_of_its_name_is_the_seed_s_to_delete() -> None:
    zinc = seed_id("compound", "zinc-oxide")
    alizarin = seed_id("compound", "alizarin")
    curated = uuid.uuid5(uuid.NAMESPACE_URL, "curated-compound:1092")
    stored = [(zinc, "Zinc oxide"), (alizarin, "Alizarin"), (curated, "Zinc oxide")]
    assert seeded_compounds(stored, planned={alizarin}) == [zinc]
