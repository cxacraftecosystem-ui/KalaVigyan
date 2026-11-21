import uuid
from dataclasses import replace
from datetime import UTC, datetime
from typing import Any

import pytest

from app.research.component_proposals import ComponentProposalDraft, task_problem
from app.research.open_work import (
    TASK_KINDS,
    TASK_PROMPTS,
    CoverageTargets,
    SubjectStanding,
    TaskKey,
    TaskSubject,
    Viewer,
    WorkFilters,
    parse_task_key,
)
from app.research.open_work_tasks import chosen_tasks, subject_tasks

NOW = datetime(2026, 11, 21, 12, 0, tzinfo=UTC)
METAL = "Metal-Craft-Category"
METAL_KEY = "FLAGSHIP:category:Metal-Craft-Category"
FIRST_DHOKRA_FACT = uuid.UUID("b6ecc15b-7df9-5345-910e-3567fcde20d1")
LAST_DHOKRA_FACT = uuid.UUID("cdcfbd45-cc3d-54c2-9c66-8f1a21a05655")
METAL_FACTS = 17
TARGETS = CoverageTargets(
    core_fields=(),
    facts_min=3,
    section_sentences_min=3,
    quote_chars_min=25,
    quote_chars_max=300,
    components=False,
)


def page(slug: str = METAL, kind: str = "category") -> TaskSubject:
    return TaskSubject(
        kind=kind, slug=slug, name=slug.replace("-", " "), page_url=f"https://kv.example/{slug}"
    )


def standing(**changes: Any) -> SubjectStanding:
    base = SubjectStanding(subject=page(), targets=TARGETS, new_form=True, layout=True)
    return replace(base, **changes)


def flagships(found: SubjectStanding) -> list[Any]:
    return [task for task in subject_tasks(found) if task.kind == "FLAGSHIP"]


def draft(**changes: Any) -> ComponentProposalDraft:
    values: dict[str, Any] = {
        "label": "shared/process/lost-wax-casting-player",
        "title": "Lost-wax casting, state by state",
        "description": "A player that steps a dhokra figure from its clay core through the wax, the fire and the pour.",
        "kind": "reaction_player",
        "field": "PROCESS",
        "subjects": [{"kind": "CRAFT", "key": "Bastar-Dhokra"}],
        "spec": {"steps": []},
        "task_key": METAL_KEY,
    }
    return ComponentProposalDraft.model_validate({**values, **changes})


def test_the_kind_sits_beside_the_component_task_and_its_key_names_the_family_page() -> None:
    assert TASK_KINDS.index("FLAGSHIP") == TASK_KINDS.index("MISSING_COMPONENT") + 1
    assert TASK_KINDS[-1] == "ANSWER_GAP"
    assert TASK_PROMPTS["FLAGSHIP"] == "deliver_page"
    assert parse_task_key(METAL_KEY) == TaskKey("FLAGSHIP", "category", METAL, None)


def test_a_family_page_drawing_no_player_holds_its_flagship_task_from_the_backlog() -> None:
    (task,) = flagships(standing(component_kinds=frozenset({"chart", "molecule_3d"})))
    assert (task.key, task.priority, task.subject, task.field, task.need) == (
        METAL_KEY,
        "HIGH",
        page(),
        None,
        None,
    )
    assert task.count == METAL_FACTS and len(task.fact_ids) == METAL_FACTS
    assert (task.fact_ids[0], task.fact_ids[-1]) == (FIRST_DHOKRA_FACT, LAST_DHOKRA_FACT)
    assert "The Metal family page draws no flagship interactive yet" in task.needed
    assert "lost-wax casting, anchored on Bastar-Dhokra" in task.needed
    assert "the melting range of dhokra's mixed metal" in task.needed
    assert "keyed to Bastar-Dhokra" in task.acceptance and "task_key" in task.acceptance
    assert task.prompt == "deliver_page"


@pytest.mark.parametrize("kind", ["reaction_player", "dip_player", "stage_player", "experiment_lab"])
def test_a_player_of_any_flagship_kind_on_the_family_page_closes_the_task(kind: str) -> None:
    assert flagships(standing(component_kinds=frozenset({kind}))) == []


def test_a_craft_or_a_category_outside_the_backlog_holds_no_flagship_task() -> None:
    assert flagships(standing(subject=page("Bastar-Dhokra", "craft"))) == []
    assert flagships(standing(subject=page("Test-Category"))) == []


def test_the_kind_filter_finds_the_flagship_tasks() -> None:
    tasks = subject_tasks(standing(subject=page("Paper-Craft-Category")))
    kept = chosen_tasks(
        tasks, WorkFilters(kind="FLAGSHIP"), holds={}, closed=frozenset(), viewer=Viewer(), now=NOW
    )
    assert [task.key for task in kept] == ["FLAGSHIP:category:Paper-Craft-Category"]
    closed = chosen_tasks(
        tasks,
        WorkFilters(kind="FLAGSHIP"),
        holds={},
        closed=frozenset({"FLAGSHIP:category:Paper-Craft-Category"}),
        viewer=Viewer(),
        now=NOW,
    )
    assert closed == []


def test_a_delivered_player_keyed_to_the_anchor_completes_the_flagship_task() -> None:
    assert task_problem(draft()) is None
    on_wax = [{"kind": "CONCEPT", "key": "0c000000-0000-4000-8000-000000000003"}]
    assert task_problem(draft(kind="experiment_lab", subjects=on_wax, craft_slug="Bastar-Dhokra")) is None


@pytest.mark.parametrize(
    ("changes", "problem"),
    [
        ({"kind": "chart"}, "reaction_player, dip_player, stage_player or experiment_lab"),
        ({"spec": None}, "delivered component"),
        ({"subjects": [{"kind": "CRAFT", "key": "Kutch-Ajrakh"}]}, "anchor craft Bastar-Dhokra"),
        ({"task_key": "FLAGSHIP:category:Test-Category"}, "names no family's flagship"),
        ({"task_key": "FLAGSHIP:craft:Bastar-Dhokra"}, "names no family's flagship"),
        ({"task_key": "FLAGSHIP:category:Metal-Craft-Category:PROCESS"}, "names no family's flagship"),
    ],
)
def test_a_flagship_task_refuses_any_other_proposal(changes: dict[str, Any], problem: str) -> None:
    found = task_problem(draft(**changes))
    assert found is not None and problem in found
