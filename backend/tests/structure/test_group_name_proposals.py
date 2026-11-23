import pytest
from pydantic import ValidationError

from app.research.structure_proposals import GroupNameItem, parsed_item
from app.research.structure_proposals_values import stated_check
from app.services.structure_proposals_dossier import dossier_problem
from app.services.structure_proposals_page import target_problem

from .pages import curated_page, proposal

NAME = {"kind": "GROUP_NAME", "name": "Khatri", "groupKind": "COMMUNITY"}
QUOTE = "about 40 families of Khatri printers now work on ajrakh cloth for local and urban buyers"
NO_FACT = {"statement": None, "field": None}


def test_a_name_is_proposed_with_its_sources_and_no_fact() -> None:
    named = proposal(NAME, QUOTE, **NO_FACT)
    assert isinstance(named.item, GroupNameItem)
    assert (named.item.name, named.item.group_kind, named.statement, named.field) == (
        "Khatri",
        "COMMUNITY",
        None,
        None,
    )
    assert dossier_problem(named) is None and target_problem(curated_page(), named.item) is None


@pytest.mark.parametrize(
    "changes",
    [
        {},
        {"statement": None},
        {"field": None},
        NO_FACT | {"sources": []},
        NO_FACT | {"taskKey": "HISTORY:Structure-Test-Craft"},
    ],
)
def test_a_name_carries_no_fact_field_or_task_and_needs_a_source(changes: dict[str, object]) -> None:
    with pytest.raises(ValidationError, match="never shown as a fact"):
        proposal(NAME, QUOTE, **changes)


def test_a_category_holds_no_names() -> None:
    with pytest.raises(ValidationError, match="category page keeps no stages"):
        proposal(
            NAME, QUOTE, **NO_FACT, subject={"kind": "category", "slug": "Textiles-Based-Craft-Category"}
        )


def test_a_name_is_stated_only_when_a_quote_holds_it() -> None:
    item = parsed_item(NAME)
    assert stated_check(item, [QUOTE]).passed
    missing = stated_check(item, ["about 40 families of printers now work on ajrakh cloth"])
    assert (missing.passed, missing.reasons) == (False, ["The name (Khatri) appears in none of the quotes."])


def test_only_a_community_or_a_person_is_listed() -> None:
    with pytest.raises(ValidationError):
        parsed_item(NAME | {"groupKind": "ORGANISATION"})
