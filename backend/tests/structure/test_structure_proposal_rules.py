import uuid
from typing import Any

import pytest
from pydantic import ValidationError

from app.research.structure_proposals import parsed_item
from app.research.structure_proposals_values import stated_check
from app.services.structure_proposals_dossier import dossier_problem
from app.services.structure_proposals_page import (
    PlacedEntry,
    current_value,
    next_key,
    placed_page,
    subject_concept,
    target_problem,
)

from .pages import (
    AFTER_QUOTE,
    BOTANY_QUOTE,
    FORMULA_QUOTE,
    GI_QUOTE,
    HELD_A,
    HELD_B,
    HELD_C,
    HISTORY_CONCEPT,
    MATERIAL_CONCEPT,
    NAME_QUOTE,
    OLD_AFTER,
    STAGE_CONCEPT,
    curated_page,
    proposal,
    source,
)

NEW_CLAIM = uuid.UUID(int=901)
TERM_CONCEPT = uuid.UUID(int=902)
NAME = {"kind": "NATIVE_NAME", "text": "Ajrak", "language": "sd", "script": "Arab"}
AFTER = {
    "kind": "STAGE_AFTER",
    "stageKey": "P01",
    "text": "Deep red where alum was printed",
    "colours": ["RED"],
}
WHY = {"kind": "STAGE_WHY", "stageKey": "P01"}
REACTION = {
    "kind": "REACTION",
    "reactionKind": "COMPLEXATION",
    "stageKey": "P01",
    "reactants": [{"name": "alum", "formula": "KAl(SO4)2"}, {"name": "alizarin"}],
    "products": [{"name": "Lake pigment", "formula": "KAl(SO4)2"}],
}
BOTANY = {"kind": "BOTANICAL_NAME", "materialKey": "M01", "botanicalName": "Indigofera tinctoria"}
TERM = {"kind": "GLOSSARY_TERM", "term": "Ajrak", "meaning": "The printed cloth, named for its blue."}
CONFLICT = {
    "kind": "CONFLICT",
    "about": "Which wash turns the cloth red",
    "claimIds": [str(HELD_A), str(HELD_B)],
}
QUESTION = {"kind": "OPEN_QUESTION", "question": "Which river first fed the dye houses?"}
GI = {"kind": "GI_RECORD", "applicationNumber": "182", "registeredOn": "2009-03-10"}


def bare(item: dict[str, Any]) -> Any:
    return parsed_item(item)


def test_a_conflict_names_held_facts_and_carries_no_new_fact() -> None:
    held = proposal(CONFLICT, statement=None, sources=[], field=None)
    assert held.item.kind == "CONFLICT" and held.sources == []
    with pytest.raises(ValidationError, match="gives no new fact"):
        proposal(CONFLICT)
    with pytest.raises(ValidationError, match="each fact once"):
        proposal(CONFLICT | {"claimIds": [str(HELD_A), str(HELD_A)]}, statement=None, sources=[], field=None)


@pytest.mark.parametrize(
    ("changes", "words"),
    [
        ({"statement": None}, "gives the fact that states it"),
        ({"sources": []}, "gives the fact that states it"),
        ({"sources": [source(NAME_QUOTE), source(NAME_QUOTE, title="Again")]}, "each source is named once"),
        ({"sources": [source(NAME_QUOTE, quotes=[{"text": NAME_QUOTE}])]}, "its locator"),
        ({"statement": "Write to ajrak.dyer@example.org for the cloth's name."}, "personal data"),
    ],
)
def test_every_other_kind_gives_its_fact_with_located_quotes(changes: dict[str, Any], words: str) -> None:
    with pytest.raises(ValidationError, match=words):
        proposal(NAME, **changes)


def test_a_gi_record_states_something_and_colours_are_named_once() -> None:
    with pytest.raises(ValidationError, match="at least one part"):
        proposal({"kind": "GI_RECORD"})
    with pytest.raises(ValidationError, match="each colour is named once"):
        proposal(AFTER | {"colours": ["RED", "RED"]})


def test_a_structure_task_must_be_a_field_task_of_the_same_page_and_field() -> None:
    assert proposal(NAME, task_key="MISSING_FIELD:craft:Structure-Test-Craft:HISTORY").task_key is not None
    with pytest.raises(ValidationError, match="asks for CHEMISTRY"):
        proposal(NAME, task_key="THIN_FIELD:craft:Structure-Test-Craft:CHEMISTRY")
    with pytest.raises(ValidationError, match="another page"):
        proposal(NAME, task_key="MISSING_FIELD:craft:Another-Craft:HISTORY")


@pytest.mark.parametrize(
    ("item", "quote"),
    [
        (NAME, NAME_QUOTE),
        (AFTER, AFTER_QUOTE),
        (REACTION, FORMULA_QUOTE),
        (BOTANY, BOTANY_QUOTE),
        (TERM, NAME_QUOTE),
        (GI, GI_QUOTE),
    ],
)
def test_every_name_colour_and_number_an_item_gives_is_in_a_quote(item: dict[str, Any], quote: str) -> None:
    check = stated_check(bare(item), [quote])
    assert (check.check, check.passed) == ("STATED", True)


def test_a_name_the_quotes_never_give_refuses_the_item_and_says_which() -> None:
    check = stated_check(bare(NAME | {"text": "Ajarak"}), [NAME_QUOTE])
    assert (check.passed, check.reasons) == (
        False,
        ["The native name (Ajarak) appears in none of the quotes."],
    )
    colour = stated_check(bare(AFTER | {"colours": ["BLUE", "RED"]}), ["The mordant is reduced in the vat"])
    assert colour.reasons == [
        "The colour blue (BLUE) appears in none of the quotes.",
        "The colour red (RED) appears in none of the quotes.",
    ]
    gi = stated_check(bare(GI | {"certificateNumber": "C-77"}), [GI_QUOTE])
    assert gi.reasons == ["The certificate number (C-77) appears in none of the quotes."]


def test_a_stage_s_why_and_an_open_question_name_nothing_beyond_their_statement() -> None:
    assert stated_check(bare(WHY), []).passed is True
    assert stated_check(bare(QUESTION), []).passed is True


def test_the_dossier_s_own_rules_hold_for_every_proposal() -> None:
    assert dossier_problem(proposal(WHY, field="HISTORY")) is not None
    assert dossier_problem(proposal(WHY, field="CHEMISTRY")) is None
    assert dossier_problem(proposal(NAME, statement="x" * 601)) is not None
    assert dossier_problem(proposal(NAME, sources=[source(NAME_QUOTE, language="English")])) is not None
    assert dossier_problem(proposal(NAME | {"script": "deva"})) is not None
    assert dossier_problem(proposal(NAME)) is None


@pytest.mark.parametrize(
    ("item", "problem"),
    [
        (AFTER | {"stageKey": "P09"}, "P09 is not a stage of this page"),
        (BOTANY | {"materialKey": "M07"}, "M07 is not a material of this page"),
        (NAME | {"text": "AJRAKH", "language": "hi"}, "already gives the native name AJRAKH in hi"),
        (CONFLICT | {"claimIds": [str(HELD_C), str(HELD_B)]}, "already shows these facts as a conflict"),
        (CONFLICT | {"claimIds": [str(HELD_A), str(NEW_CLAIM)]}, str(NEW_CLAIM)),
    ],
)
def test_an_item_must_fit_the_page_it_is_written_into(item: dict[str, Any], problem: str) -> None:
    found = target_problem(curated_page(), bare(item))
    assert found is not None and problem in found


def test_a_new_name_in_another_language_and_a_reaction_without_a_stage_fit() -> None:
    assert target_problem(curated_page(), bare(NAME)) is None
    assert target_problem(curated_page(), bare(REACTION | {"stageKey": None})) is None


def test_each_fact_is_about_the_stage_material_or_craft_field_it_explains() -> None:
    page = curated_page()
    assert subject_concept(page, bare(AFTER), "CHEMISTRY") == STAGE_CONCEPT
    assert subject_concept(page, bare(BOTANY), "BOTANY") == MATERIAL_CONCEPT
    assert subject_concept(page, bare(NAME), "HISTORY") == HISTORY_CONCEPT
    assert subject_concept(page, bare(NAME), "SOCIETY") is None
    assert subject_concept(page, bare(TERM), "HISTORY") is None


def test_keys_follow_the_highest_of_their_letter() -> None:
    assert next_key("C", ["C001", "C009", "S01", "C1x"], width=3) == "C010"
    assert next_key("W", []) == "W01"
    assert next_key("S", ["S09", "S11"]) == "S12"


def test_a_stage_s_after_and_why_land_on_that_stage_only() -> None:
    page = curated_page()
    after = placed_page(page, bare(AFTER), PlacedEntry(NEW_CLAIM))
    first, second = after.stages
    assert (first.after.text, first.after.colours, first.after.claim_id) == (
        AFTER["text"],
        ["RED"],
        NEW_CLAIM,
    )
    assert second.after.claim_id == OLD_AFTER
    assert after.claim_order == [HELD_A, HELD_B, HELD_C, NEW_CLAIM]
    why = placed_page(page, bare(WHY), PlacedEntry(NEW_CLAIM))
    assert [stage.why_claim_id for stage in why.stages] == [NEW_CLAIM, None]
    assert current_value(page, bare(AFTER | {"stageKey": "P02"})) == "Pale"


def test_names_reactions_terms_and_questions_join_the_page_under_their_keys() -> None:
    page = curated_page()
    named = placed_page(page, bare(NAME), PlacedEntry(NEW_CLAIM))
    assert [(name.text, name.language, name.claim_id) for name in named.native_names][-1] == (
        "Ajrak",
        "sd",
        NEW_CLAIM,
    )
    reacted = placed_page(page, bare(REACTION), PlacedEntry(NEW_CLAIM, key="R01"))
    (reaction,) = reacted.reactions
    assert (reaction.key, reaction.stage_key, reaction.reaction_id, reaction.claim_ids) == (
        "R01",
        "P01",
        None,
        [NEW_CLAIM],
    )
    assert [species.formula for species in reaction.reactants] == ["KAl(SO4)2", None]
    termed = placed_page(page, bare(TERM), PlacedEntry(NEW_CLAIM, key="W01", concept_id=TERM_CONCEPT))
    (term,) = termed.glossary
    assert (term.key, term.term_key, term.names, term.concept_id) == ("W01", None, ["Ajrak"], TERM_CONCEPT)
    asked = placed_page(page, bare(QUESTION), PlacedEntry(NEW_CLAIM, key="O01"))
    assert [(q.key, q.question, q.claim_ids) for q in asked.open_questions] == [
        ("O01", QUESTION["question"], [NEW_CLAIM])
    ]


def test_a_botanical_name_and_a_conflict_change_what_the_page_already_holds() -> None:
    page = curated_page()
    named = placed_page(page, bare(BOTANY), PlacedEntry(NEW_CLAIM))
    (material,) = named.materials
    assert (material.botanical_name, material.claim_ids) == ("Indigofera tinctoria", [HELD_A, NEW_CLAIM])
    disputed = placed_page(page, bare(CONFLICT), PlacedEntry(None))
    assert [conflict.claim_ids for conflict in disputed.conflicts] == [[HELD_B, HELD_C], [HELD_A, HELD_B]]
    assert disputed.claim_order == page.claim_order
