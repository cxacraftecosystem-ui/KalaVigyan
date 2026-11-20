from typing import Any

import pytest
from pydantic import ValidationError

from app.research.page_proposals import PageBundle, fact_index

from .general_spec_fixtures import TABLE

SUBJECT = {"kind": "craft", "slug": "Kutch-Ajrakh"}
FACT = {
    "subject": SUBJECT,
    "field": "CHEMISTRY",
    "statement": "Alum fixes the madder red on the cotton.",
    "sources": [
        {"url": "https://example.org/alum", "title": "Alum", "quotes": [{"text": "alum fixes the red"}]}
    ],
}
UNITS = {
    "u0001": {"text": "Alum fixes the madder red."},
    "u0002": {"text": "Alum fixes the madder red."},
    "u0003": {"text": "Mordant"},
    "u0004": {"text": "What it does"},
    "u0005": {"text": "Alum"},
    "u0006": {"text": "Fixes the madder red"},
}
COMPONENT = {
    "label": "kutch-ajrakh/chemistry/alum-table",
    "title": "Alum on cotton",
    "description": "A table of what alum does to the madder red on cotton, cited fact by fact.",
    "kind": "general_table",
    "field": "CHEMISTRY",
    "craftSlug": "Kutch-Ajrakh",
    "subjects": [{"kind": "CRAFT", "key": "Kutch-Ajrakh"}],
    "spec": TABLE,
    "units": UNITS,
}


def bundle(**parts: Any) -> PageBundle:
    return PageBundle.model_validate({"subject": SUBJECT, **parts})


def test_a_bundle_holds_work_of_at_least_one_kind() -> None:
    with pytest.raises(ValidationError, match="at least one fact"):
        bundle()
    assert len(bundle(facts=[FACT]).facts) == 1


def test_a_component_cites_the_bundle_s_facts_by_their_place() -> None:
    cited = bundle(facts=[FACT], components=[{"proposal": COMPONENT, "cites": {"u0006": ["fact:0"]}}])
    assert cited.components[0].cites == {"u0006": ["fact:0"]}
    assert fact_index("fact:0") == 0 and fact_index("fact") is None


@pytest.mark.parametrize(
    ("cites", "says"),
    [
        ({"u0006": ["fact:1"]}, "names a fact this bundle does not hold"),
        ({"u0099": ["fact:0"]}, "units the component does not hold"),
        ({"u0006": ["claim:0"]}, "should match pattern"),
    ],
)
def test_a_cite_names_a_fact_of_the_bundle_and_a_unit_of_the_component(
    cites: dict[str, Any], says: str
) -> None:
    with pytest.raises(ValidationError, match=says):
        bundle(facts=[FACT], components=[{"proposal": COMPONENT, "cites": cites}])


def test_a_picture_may_rest_on_a_fact_of_the_bundle() -> None:
    picture = {"claimIds": ["fact:0"]}
    assert bundle(facts=[FACT], pictures=[picture]).pictures[0].claim_ids == ["fact:0"]
    with pytest.raises(ValidationError, match="does not hold"):
        bundle(pictures=[picture])


def test_a_layout_part_follows_the_layout_rules() -> None:
    hero = {"ref": "kutch-ajrakh/pictures/i01", "chapter": "glance", "order": 1, "role": "HERO"}
    twice = {**hero, "order": 2}
    with pytest.raises(ValidationError):
        bundle(layout={"baseVersion": 0, "entries": [hero, twice]})
    assert bundle(layout={"baseVersion": 0, "entries": [hero]}).layout is not None
