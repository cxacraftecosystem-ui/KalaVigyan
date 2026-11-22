import copy
from functools import cache
from typing import Any

import pytest

from app.core.errors import InvalidInput
from app.research.licences import open_licence
from app.science.balance import CHECKER_VERSION
from app.services.claim_seed import claim_seed_plan, load_seed_claims, seed_id
from app.services.science_seed import SciencePlan, constants_data, load_science_seed, science_seed_plan

HAND_BALANCED = {
    ("ie:ajrakh.process_stage.kut", "iron-acetate"): [1, 2, 1, 1],
    ("ie:ajrakh.process_stage.indigo-dyeing", "indigo-reduction"): [1, 2, 2, 1],
    ("ie:ajrakh.process_stage.indigo-dyeing", "indigo-oxidation"): [2, 1, 2, 2],
    ("ie:machilipatnam-kalamkari.process_stage.mordant-printing-kasim", "iron-acetate"): [1, 2, 1, 1],
}
SPECIES_ONLY = {
    ("ie:ajrakh.process_stage.red-dyeing", "alizarin-lake"),
    ("ie:bagh.process_stage.bhatti", "alizarin-lake"),
    ("ie:machilipatnam-kalamkari.process_stage.alizarin-boiling", "alizarin-lake"),
}


@cache
def seed_claims_data() -> dict[str, Any]:
    return load_seed_claims()


@cache
def plan() -> SciencePlan:
    return science_seed_plan(load_science_seed(), seed_claims_data())


def plan_with(change) -> SciencePlan:
    science = copy.deepcopy(load_science_seed())
    change(science)
    return science_seed_plan(science, seed_claims_data())


def test_every_reaction_balances_to_its_hand_derived_coefficients() -> None:
    rows = {row["id"]: row for row in plan().rows["reactions"]}
    for (stage, key), coefficients in HAND_BALANCED.items():
        row = rows[seed_id("reaction", f"{stage}:{key}")]
        assert (row["balanced"], row["coefficients"], row["checkerVersion"]) == (
            True,
            coefficients,
            CHECKER_VERSION,
        )
    for stage, key in SPECIES_ONLY:
        row = rows[seed_id("reaction", f"{stage}:{key}")]
        assert (row["balanced"], row["coefficients"], row["equationInput"]) == (False, None, None)
    assert len(rows) == len(HAND_BALANCED) + len(SPECIES_ONLY)


def test_the_iron_acetate_equation_is_written_from_its_species() -> None:
    row = next(r for r in plan().rows["reactions"] if r["label"] == "Scrap iron dissolving into iron acetate")
    assert row["equationBalanced"] == "Fe + 2 CH3COOH -> Fe(CH3COO)2 + H2"
    assert [s["compoundId"] for s in row["species"]] == [
        None,
        None,
        str(seed_id("compound", "iron-ii-acetate")),
        None,
    ]


def test_each_seeded_stage_material_has_a_kind_and_a_role_and_no_entry_is_unused() -> None:
    materials = {row["id"] for row in plan().rows["materials"]}
    listed = {seed_id("material", key) for key in load_science_seed()["materials"]}
    assert materials == listed
    assert all(row["claimId"] is not None for row in plan().rows["stageMaterials"])


def test_a_material_without_a_kind_is_refused() -> None:
    with pytest.raises(InvalidInput, match="has no kind and role"):
        plan_with(lambda science: science["materials"].pop("ie:ajrakh.material.alum"))


def test_a_reading_its_claim_does_not_say_is_refused() -> None:
    def wrong(science: dict[str, Any]) -> None:
        science["conditions"][0]["readings"][0]["stated"] = "eleven days"

    with pytest.raises(InvalidInput, match="is not said by seed claim"):
        plan_with(wrong)


def test_a_reading_in_a_unit_of_another_quantity_is_refused() -> None:
    def wrong(science: dict[str, Any]) -> None:
        science["conditions"][0]["readings"][0]["unit"] = "metre"

    with pytest.raises(InvalidInput, match="cannot be expressed"):
        plan_with(wrong)


def test_a_citation_the_claim_does_not_have_is_refused() -> None:
    def wrong(science: dict[str, Any]) -> None:
        science["reactions"][0]["citations"][0][1] = 9

    with pytest.raises(InvalidInput, match="has no citation 9"):
        plan_with(wrong)


def test_a_reaction_on_a_stage_that_is_not_seeded_is_refused() -> None:
    def wrong(science: dict[str, Any]) -> None:
        science["reactions"][0]["stage"] = "ie:ajrakh.process_stage.unknown"

    with pytest.raises(InvalidInput, match="is not a seeded process stage"):
        plan_with(wrong)


def test_leucoindigo_is_seeded_with_its_pubchem_record_and_no_other_compound_claims_one() -> None:
    rows = {row["name"]: row for row in plan().rows["compounds"]}
    assert (rows["Leucoindigo"]["formula"], rows["Leucoindigo"]["pubchemCid"]) == ("C16H12N2O2", 23035)
    assert {name: row["pubchemCid"] for name, row in rows.items() if name != "Leucoindigo"} == {
        "Iron(II) acetate": None,
        "Alizarin": None,
        "Indigo": None,
        "Potassium alum": None,
    }


def test_the_constants_are_seeded_as_cited_claims_through_the_claim_seed() -> None:
    constants = claim_seed_plan(constants_data(load_science_seed()))
    assert len(constants["claims"]) == 5
    assert {row["quoteCheck"] for row in constants["claimSources"]} == {"PASS"}
    assert {row["evidenceLevel"] for row in constants["claims"]} == {"PROVISIONAL"}
    for source in constants["sources"]:
        assert open_licence(source["licence"])
        assert source["attribution"].startswith("Wikipedia contributors")
        assert "&oldid=" in source["url"]


def test_constant_claims_attach_to_concepts_that_exist() -> None:
    known = {concept["key"] for concept in seed_claims_data()["concepts"]}
    known |= {concept["key"] for concept in load_science_seed()["constants"]["concepts"]}
    for claim in load_science_seed()["constants"]["claims"]:
        assert claim["subjectKey"] in known


def test_readings_and_conditions_belong_to_one_seeded_stage() -> None:
    conditions = {row["id"]: row for row in plan().rows["conditions"]}
    for reading in plan().rows["readings"]:
        assert reading["conditionId"] in conditions
    assert all(row["reactionId"] is None for row in conditions.values())
    assert len(plan().rows["readings"]) == sum(len(c["readings"]) for c in load_science_seed()["conditions"])
