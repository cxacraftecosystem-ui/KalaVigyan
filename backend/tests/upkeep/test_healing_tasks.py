import uuid
from dataclasses import replace

import pytest
from pydantic import ValidationError

from app.research.open_work import (
    CoverageTargets,
    FieldStanding,
    Items,
    OpenTask,
    SubjectStanding,
    TaskSubject,
    parse_task_key,
)
from app.research.open_work_tasks import subject_tasks
from app.research.source_proposals import SOURCE_TASK_KINDS, SourceProposal
from app.services.open_work_healing import HEALING_KINDS, Healing, healing_tasks, with_healing
from app.services.source_proposals import task_problem

FACT_A = "0e000000-0000-4000-8000-0000000000b1"
FACT_B = "0e000000-0000-4000-8000-0000000000b2"
SOURCE_A = "0e000000-0000-4000-8000-0000000000c1"
TARGETS = CoverageTargets(
    core_fields=("CHEMISTRY",),
    facts_min=3,
    section_sentences_min=3,
    quote_chars_min=25,
    quote_chars_max=300,
    components=False,
)
SUBJECT = TaskSubject(
    kind="craft", slug="Kutch-Ajrakh", name="Kutch Ajrakh", page_url="https://kv.example/crafts/Kutch-Ajrakh"
)
STANDING = SubjectStanding(
    subject=SUBJECT,
    targets=TARGETS,
    fields={"CHEMISTRY": FieldStanding(facts=3, section_sentences=3)},
    new_form=True,
    layout=True,
)
HEALING = Healing(
    held={"HISTORY": Items.of([FACT_B]), "CHEMISTRY": Items.of([FACT_A, FACT_B])},
    failing={None: Items.of([FACT_A])},
    rotten_facts=Items.of([FACT_B]),
    rotten_sources=Items.of([SOURCE_A]),
)


def test_held_failing_and_rotting_facts_become_three_kinds_of_work_in_field_order() -> None:
    tasks = healing_tasks(STANDING, HEALING)
    assert [task.key for task in tasks] == [
        "RESOURCE_FACT:craft:Kutch-Ajrakh:CHEMISTRY",
        "RESOURCE_FACT:craft:Kutch-Ajrakh:HISTORY",
        "CORROBORATE_FACT:craft:Kutch-Ajrakh",
        "FIND_ANOTHER_SOURCE:craft:Kutch-Ajrakh",
    ]
    chemistry, history, corroborate, rotten = tasks
    assert (chemistry.count, chemistry.fact_ids, chemistry.field) == (
        2,
        [uuid.UUID(FACT_A), uuid.UUID(FACT_B)],
        "CHEMISTRY",
    )
    assert chemistry.needed == (
        "2 facts of Kutch Ajrakh under CHEMISTRY (chemistry) are held from the page: no quote cited for them "
        "is found in its source any more."
    )
    assert history.needed == (
        "1 fact of Kutch Ajrakh under HISTORY (history) is held from the page: no quote cited for it is found "
        "in its source any more."
    )
    assert corroborate.field is None and corroborate.fact_ids == [uuid.UUID(FACT_A)]
    assert "propose_source" in corroborate.acceptance
    assert (rotten.fact_ids, rotten.source_ids, rotten.count) == ([uuid.UUID(FACT_B)], [SOURCE_A], 1)
    assert rotten.needed == (
        "1 fact of Kutch Ajrakh rests only on 1 source that failed to answer on 3 nightly checks in a row and has "
        "no archived copy."
    )
    assert {task.priority for task in tasks} == {"LOW"} and all(task.prompt is None for task in tasks)
    assert all(parse_task_key(task.key).kind in HEALING_KINDS for task in tasks)


def test_healing_work_leads_its_subject_s_tasks_and_no_healing_changes_nothing() -> None:
    healed = with_healing(STANDING, HEALING)
    assert [task.kind for task in subject_tasks(healed)][:4] == [
        "RESOURCE_FACT",
        "RESOURCE_FACT",
        "CORROBORATE_FACT",
        "FIND_ANOTHER_SOURCE",
    ]
    assert with_healing(STANDING, None) is STANDING
    assert healing_tasks(STANDING, Healing()) == []
    assert subject_tasks(replace(STANDING, healing=())) == []


def task(**changes: object) -> OpenTask:
    base = {
        "key": "RESOURCE_FACT:craft:Kutch-Ajrakh:CHEMISTRY",
        "kind": "RESOURCE_FACT",
        "priority": "LOW",
        "subject": SUBJECT,
        "needed": "n",
        "acceptance": "a",
        "count": 1,
        "factIds": [FACT_A],
    }
    return OpenTask.model_validate(base | changes)


def test_a_source_completes_only_a_task_that_names_its_fact_or_one_of_its_sources() -> None:
    key = "RESOURCE_FACT:craft:Kutch-Ajrakh:CHEMISTRY"
    fact_a, fact_b, source = uuid.UUID(FACT_A), uuid.UUID(FACT_B), uuid.UUID(SOURCE_A)
    assert task_problem(task(), key, fact_a, set()) is None
    assert (
        task_problem(task(), key, fact_b, set())
        == f"{key} lists other facts than {fact_b}; claim the task that names this fact."
    )
    assert task_problem(task(count=21), key, fact_b, set()) is None
    assert (
        task_problem(None, key, fact_a, set())
        == f"No open task has the key {key}; list_open_work gives the open tasks."
    )
    dead = task(kind="DEAD_SOURCE", key="DEAD_SOURCE:craft:Kutch-Ajrakh", factIds=[], sourceIds=[SOURCE_A])
    assert task_problem(dead, dead.key, fact_b, {source}) is None
    assert task_problem(dead, dead.key, fact_b, set()) is not None


def test_a_source_proposal_names_each_page_once_and_only_a_source_task() -> None:
    source = {"url": "https://example.org/a", "title": "A", "quotes": [{"text": "a quote of twenty letters"}]}
    body = {"claimId": FACT_A, "sources": [source]}
    assert SourceProposal.model_validate(body).task_key is None
    with pytest.raises(ValidationError, match="each source is named once"):
        SourceProposal.model_validate(body | {"sources": [source, source]})
    with pytest.raises(ValidationError, match="is not a task a source completes"):
        SourceProposal.model_validate(body | {"taskKey": "MISSING_FIELD:craft:Kutch-Ajrakh:CHEMISTRY"})
    for kind in SOURCE_TASK_KINDS:
        assert SourceProposal.model_validate(body | {"taskKey": f"{kind}:craft:Kutch-Ajrakh"}).task_key
