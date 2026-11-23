import uuid
from datetime import UTC, datetime
from typing import Any

import pytest
from pydantic import ValidationError

from app.research.structure_proposals import CATEGORY_HOLDS, parsed_item
from app.services.curated_category_index import CuratedCategoryPage, IndexCategoryQuestion
from app.services.curated_index import IndexAlternative, IndexMaterial
from app.services.structure_proposals_dossier import dossier_problem
from app.services.structure_proposals_page import (
    PlacedEntry,
    current_value,
    placed_page,
    subject_concept,
    target_problem,
)

from .pages import HELD_A, HELD_B, MATERIAL_CONCEPT, curated_page, indigo, key, proposal

NEW_CLAIM = uuid.UUID(int=911)
ALUM_CONCEPT = key("alum-concept")
ALTERNATIVE = {"kind": "ALTERNATIVE", "materialKey": "M01", "alternativeKey": "M02"}
QUESTION = {"kind": "OPEN_QUESTION", "question": "Which mordant did the earliest printers of the family use?"}
TERM = {
    "kind": "GLOSSARY_TERM",
    "term": "Ajrak",
    "meaning": "A resist-printed cloth dyed in indigo and madder.",
}
CATEGORY_SLUG = "Textiles-Based-Craft-Category"


def bare(item: dict[str, Any]) -> Any:
    return parsed_item(item)


def alum() -> IndexMaterial:
    return indigo().model_copy(
        update={"key": "M02", "material_id": key("alum"), "concept_id": ALUM_CONCEPT, "name": "Alum"}
    )


def category_page(**changes: Any) -> CuratedCategoryPage:
    base: dict[str, Any] = {
        "category_slug": CATEGORY_SLUG,
        "version": 1,
        "curated_at": datetime(2026, 11, 1, tzinfo=UTC),
        "coverage": "THIN",
        "searched": [],
        "overview": {},
        "sentence_refs": [],
        "conflicts": [],
        "open_questions": [],
        "glossary": [],
        "pictures": [],
    }
    return CuratedCategoryPage(**(base | changes))


def category_proposal(item: dict[str, Any], **changes: Any) -> Any:
    return proposal(item, subject={"kind": "category", "slug": CATEGORY_SLUG}, **changes)


def test_an_alternative_is_another_material_of_the_page() -> None:
    with pytest.raises(ValidationError, match="another material of the page"):
        bare(ALTERNATIVE | {"alternativeKey": "M01"})
    page = curated_page(materials=[indigo(), alum()])
    assert target_problem(page, bare(ALTERNATIVE)) is None
    assert (
        target_problem(page, bare(ALTERNATIVE | {"alternativeKey": "M09"}))
        == "M09 is not a material of this page"
    )
    assert subject_concept(page, bare(ALTERNATIVE), "CHEMISTRY") == MATERIAL_CONCEPT


def test_an_approved_alternative_joins_its_material_and_is_not_given_twice() -> None:
    page = curated_page(materials=[indigo(), alum()])
    placed = placed_page(page, bare(ALTERNATIVE), PlacedEntry(NEW_CLAIM))
    assert placed.materials[0].alternatives == [IndexAlternative(key="M02", claim_id=NEW_CLAIM)]
    assert placed.materials[1].alternatives == []
    assert placed.claim_order[-1] == NEW_CLAIM
    assert current_value(placed, bare(ALTERNATIVE)) == "Alum"
    assert target_problem(placed, bare(ALTERNATIVE)) == "the page already gives M02 as an alternative to M01"


def test_an_alternative_fits_its_dossier_and_needs_a_stated_fact() -> None:
    assert dossier_problem(proposal(ALTERNATIVE, field="CHEMISTRY")) is None
    with pytest.raises(ValidationError, match="gives the fact that states it"):
        proposal(ALTERNATIVE, statement=None)


@pytest.mark.parametrize(
    "item",
    [
        {"kind": "STAGE_WHY", "stageKey": "P01"},
        {"kind": "NATIVE_NAME", "text": "Ajrak", "language": "sd"},
        {"kind": "BOTANICAL_NAME", "materialKey": "M01", "botanicalName": "Indigofera tinctoria"},
        ALTERNATIVE,
        {
            "kind": "REACTION",
            "reactionKind": "COMPLEXATION",
            "stageKey": "P01",
            "reactants": [{"name": "alum"}],
            "products": [{"name": "lake"}],
        },
    ],
)
def test_a_category_page_refuses_what_only_a_craft_page_keeps(item: dict[str, Any]) -> None:
    with pytest.raises(ValidationError) as refused:
        category_proposal(item)
    assert CATEGORY_HOLDS in str(refused.value)


def test_a_category_takes_terms_questions_unstaged_reactions_and_conflicts() -> None:
    reaction = {
        "kind": "REACTION",
        "reactionKind": "COMPLEXATION",
        "reactants": [{"name": "alum"}],
        "products": [{"name": "lake"}],
    }
    for item in (TERM, QUESTION, reaction):
        assert category_proposal(item).subject.kind == "category"
    conflict = {"kind": "CONFLICT", "about": "The first mordant", "claimIds": [str(HELD_A), str(HELD_B)]}
    listed = category_proposal(conflict, field=None, statement=None, sources=[])
    assert listed.item.kind == "CONFLICT"


def test_a_category_question_keeps_the_category_s_shape_and_a_conflict_its_own_facts() -> None:
    page = category_page()
    asked = placed_page(page, bare(QUESTION), PlacedEntry(NEW_CLAIM, key="O01"))
    (question,) = asked.open_questions
    assert isinstance(question, IndexCategoryQuestion)
    assert (question.key, question.claim_ids, question.sub_categories) == ("O01", [NEW_CLAIM], [])
    conflict = bare(
        {"kind": "CONFLICT", "about": "The first mordant", "claimIds": [str(HELD_A), str(HELD_B)]}
    )
    assert target_problem(page, conflict, held=frozenset({HELD_A, HELD_B})) is None
    unknown = target_problem(page, conflict, held=frozenset({HELD_A}))
    assert unknown == f"a conflict names facts of this page's dossier; these are not: {HELD_B}"
    assert subject_concept(page, bare(QUESTION), "HISTORY") is None
