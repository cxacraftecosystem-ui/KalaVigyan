import uuid
from typing import Any

import pytest
from pydantic import ValidationError

from app.research.page_drafts import (
    DraftAddition,
    DraftParts,
    PageLists,
    bundle_problem,
    draft_bundle,
    part_summaries,
    parts_counts,
    with_added,
    without,
)
from app.research.page_proposals import FACTS_MAX, PageSubject

from .test_page_proposals import COMPONENT, FACT, SUBJECT

STORED = uuid.UUID("6f1c2a4e-8d3b-4c5a-9e7f-0a1b2c3d4e5f")
SUPPLIED = uuid.UUID("0e000000-0000-4000-8000-0000000000a1")


def fact(n: int) -> dict[str, Any]:
    return {**FACT, "statement": f"Alum fixes the madder red on the cotton in bath {n}."}


def component(*refs: str) -> dict[str, Any]:
    return {"proposal": COMPONENT, "cites": {"u0006": list(refs)}}


def added(**parts: Any) -> DraftAddition:
    return DraftAddition.model_validate(parts)


def three_facts() -> DraftParts:
    return with_added(DraftParts(), added(facts=[fact(0), fact(1), fact(2)]))


def test_an_addition_adds_something() -> None:
    with pytest.raises(ValidationError, match="add at least one"):
        added()
    assert added(note="Started from the GI record.").note == "Started from the GI record."


def test_parts_are_appended_and_the_layout_lists_and_note_replace_the_draft_s() -> None:
    held = with_added(DraftParts(), added(facts=[fact(0)], supplied_sources=[SUPPLIED], note="first"))
    grown = with_added(held, added(facts=[fact(1)], supplied_sources=[SUPPLIED, STORED], note="second"))
    assert [f.statement for f in grown.facts] == [fact(0)["statement"], fact(1)["statement"]]
    assert grown.supplied_sources == [SUPPLIED, STORED]
    assert grown.note == "second"
    counts = parts_counts(grown)
    assert (counts.facts, counts.supplied_sources, counts.layout) == (2, 2, 0)


def test_a_draft_holds_no_more_than_a_bundle_does() -> None:
    full = with_added(DraftParts(), added(facts=[fact(n) for n in range(FACTS_MAX)]))
    with pytest.raises(ValidationError, match=f"at most {FACTS_MAX} items"):
        with_added(full, added(facts=[fact(FACTS_MAX)]))


def test_a_part_names_only_facts_the_draft_holds() -> None:
    with pytest.raises(ValueError, match="fact:3 names a fact this draft does not hold"):
        with_added(three_facts(), added(components=[component("fact:3")]))
    with pytest.raises(ValueError, match="fact:0 names a fact"):
        with_added(DraftParts(), added(lists={"signature": "fact:0"}))
    signed = with_added(three_facts(), added(lists={"signature": "fact:2", "mechanisms": ["alum mordant"]}))
    assert signed.lists == PageLists(signature="fact:2", mechanisms=["alum mordant"])


def test_removing_a_fact_renumbers_every_later_reference() -> None:
    held = with_added(
        three_facts(),
        added(
            components=[component("fact:2")],
            pictures=[{"claimIds": ["fact:1", str(STORED)]}],
            lists={"signature": "fact:2"},
        ),
    )
    left = without(held, "fact", 0)
    assert [f.statement for f in left.facts] == [fact(1)["statement"], fact(2)["statement"]]
    assert left.components[0].cites == {"u0006": ["fact:1"]}
    assert left.pictures[0].claim_ids == ["fact:0", STORED]
    assert left.lists is not None and left.lists.signature == "fact:1"


def test_a_fact_still_named_by_a_part_is_kept() -> None:
    held = with_added(three_facts(), added(components=[component("fact:1")]))
    with pytest.raises(ValueError, match="fact:1 is still named by component 0"):
        without(held, "fact", 1)
    assert len(without(held, "fact", 2).facts) == 2


@pytest.mark.parametrize(("part", "index"), [("fact", 3), ("structure", 0), ("picture", 1), ("layout", 0)])
def test_removing_a_part_the_draft_lacks_is_refused(part: str, index: int) -> None:
    with pytest.raises(ValueError, match="holds no"):
        without(three_facts(), part, index)


def test_a_supplied_source_and_a_component_are_removed_by_their_place() -> None:
    held = with_added(three_facts(), added(supplied_sources=[SUPPLIED, STORED], components=[component()]))
    assert without(held, "supplied_source", 0).supplied_sources == [STORED]
    assert without(held, "component", 0).components == []


def test_the_draft_becomes_the_bundle_it_previews_and_submits() -> None:
    held = with_added(three_facts(), added(components=[component("fact:0")], note="ready"))
    subject = PageSubject.model_validate(SUBJECT)
    bundle = draft_bundle(subject, held)
    assert (len(bundle.facts), len(bundle.components), bundle.note) == (3, 1, "ready")
    assert bundle_problem(subject, DraftParts()) is not None
    assert bundle_problem(subject, held) is None


def test_each_part_is_summarised_by_its_place() -> None:
    held = with_added(three_facts(), added(components=[component()], supplied_sources=[SUPPLIED]))
    summaries = [(part.part, part.index) for part in part_summaries(held)]
    assert summaries == [("fact", 0), ("fact", 1), ("fact", 2), ("component", 0), ("supplied_source", 0)]
    first = part_summaries(held)[0].summary
    assert first == f"CHEMISTRY: {fact(0)['statement']}"
