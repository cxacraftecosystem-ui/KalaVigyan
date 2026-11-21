import uuid
from dataclasses import replace
from datetime import UTC, datetime

from app.models.enums import DISCIPLINES
from app.research.open_work import CoverageTargets, SubjectStanding, TaskSubject
from app.research.open_work_gap_tasks import OpenGap, gap_task, listed
from app.research.open_work_tasks import subject_tasks

GAP = uuid.UUID("0f100000-0000-4000-8000-000000000001")
SUBJECT = TaskSubject(
    kind="craft", slug="Kutch-Ajrakh", name="Kutch Ajrakh", page_url="https://kv.example/crafts/Kutch-Ajrakh"
)
TARGETS = CoverageTargets(
    core_fields=DISCIPLINES,
    facts_min=3,
    section_sentences_min=3,
    quote_chars_min=25,
    quote_chars_max=300,
    components=True,
)
ASKED = OpenGap(
    id=GAP,
    question="Why is the cloth dyed twice in harde?",
    askers=3,
    last_asked=datetime(2026, 11, 18, 21, 5, tzinfo=UTC),
    fields=("CHEMISTRY", "HISTORY"),
    lacks=("NO_CITED_EVIDENCE", "FEW_SENTENCES"),
    priority="MEDIUM",
)


def test_a_gap_becomes_one_task_with_the_question_how_many_asked_and_what_would_answer_it() -> None:
    task = gap_task(SUBJECT, ASKED)
    assert task.key == "ANSWER_GAP:craft:Kutch-Ajrakh:gap-0f100000000040008000000000000001"
    assert (task.kind, task.priority, task.field, task.count, task.prompt) == (
        "ANSWER_GAP",
        "MEDIUM",
        "CHEMISTRY",
        3,
        "research_field",
    )
    assert task.needed == (
        'Readers asked "Why is the cloth dyed twice in harde?" (3 readers in the last 90 days, the latest on '
        "2026-11-18); the answer found no cited evidence and held fewer than 3 cited sentences in a field. "
        "Cited facts under CHEMISTRY and HISTORY would answer it."
    )
    assert task.acceptance.startswith(
        "At least 2 cited facts of Kutch Ajrakh under each of CHEMISTRY and HISTORY that a retrieval run for "
        "the question finds"
    )
    assert "naming this task's key as task_key: a fact filed under one of those fields" in task.acceptance
    assert task.fact_ids == [] and task.source_ids == [] and task.need is None


def test_one_reader_is_counted_in_the_singular() -> None:
    one = replace(ASKED, askers=1, lacks=("LOW_RETRIEVAL",), fields=("BOTANY",))
    assert gap_task(SUBJECT, one).needed == (
        'Readers asked "Why is the cloth dyed twice in harde?" (1 reader in the last 90 days, the latest on '
        "2026-11-18); the answer found no stored fact matching the question's words or names. "
        "Cited facts under BOTANY would answer it."
    )


def test_fields_are_listed_as_a_sentence_lists_them() -> None:
    assert listed(()) == ""
    assert listed(("HISTORY",)) == "HISTORY"
    assert listed(("PROCESS", "CHEMISTRY", "HISTORY")) == "PROCESS, CHEMISTRY and HISTORY"


def test_a_subject_lists_its_readers_questions_after_its_healing_and_before_its_fields() -> None:
    asked = gap_task(SUBJECT, ASKED)
    standing = SubjectStanding(subject=SUBJECT, targets=TARGETS, asked=(asked,))
    tasks = subject_tasks(standing)
    assert tasks[0] == asked
    assert [task.kind for task in tasks[1:17]] == ["MISSING_FIELD"] * 16


def test_the_task_never_names_who_asked() -> None:
    shown = gap_task(SUBJECT, ASKED).model_dump_json(by_alias=True)
    assert "user" not in shown.casefold() and "answerId" not in shown and "asker" not in shown.casefold()
