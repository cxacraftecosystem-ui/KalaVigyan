from dataclasses import replace

from app.models.enums import DISCIPLINES
from app.research.open_work import CoverageTargets, FieldStanding, SubjectStanding, TaskSubject, Viewer
from app.research.open_work_tasks import open_tasks, subject_priority, subject_tasks
from app.services.open_work_refresh import closed_field_reservations

TARGETS = CoverageTargets(
    core_fields=DISCIPLINES,
    facts_min=3,
    section_sentences_min=3,
    quote_chars_min=25,
    quote_chars_max=300,
    components=False,
)


def standing(slug: str, **changes: object) -> SubjectStanding:
    subject = TaskSubject(
        kind="craft", slug=slug, name=slug.replace("-", " "), page_url=f"https://kv.example/crafts/{slug}"
    )
    return replace(SubjectStanding(subject=subject, targets=TARGETS, new_form=True, layout=True), **changes)


def test_a_curated_craft_is_medium_priority_like_a_gi_craft() -> None:
    assert subject_priority(standing("Curated-Craft", curated=True)) == "MEDIUM"
    assert subject_priority(standing("Gi-Craft", gi=True)) == "MEDIUM"
    assert subject_priority(standing("Plain-Craft")) == "LOW"


def test_within_a_priority_gi_crafts_come_first_then_curated_ones_then_reader_demand() -> None:
    standings = [
        standing("Popular-Craft", demand=10),
        standing("Curated-Craft", curated=True),
        standing("Gi-Craft", gi=True),
        standing("Gi-Curated-Craft", gi=True, curated=True),
    ]
    tasks = open_tasks(standings, {}, Viewer())
    firsts = list(dict.fromkeys(task.subject.slug for task in tasks if task.subject is not None))
    assert firsts == ["Gi-Curated-Craft", "Gi-Craft", "Curated-Craft", "Popular-Craft"]


def test_with_every_field_core_each_field_without_claims_is_missing_and_a_thin_one_is_thin() -> None:
    bare = standing("Bare-Craft", fields={"HISTORY": FieldStanding(facts=1)})
    kinds = {task.field: task.kind for task in subject_tasks(bare) if task.field is not None}
    assert len(kinds) == 16 and kinds["HISTORY"] == "THIN_FIELD"
    assert {kind for field, kind in kinds.items() if field != "HISTORY"} == {"MISSING_FIELD"}


def test_the_nightly_refresh_closes_reservations_of_field_tasks_no_longer_open() -> None:
    bare = standing("Bare-Craft", fields={"HISTORY": FieldStanding(facts=1)})
    held = ["MISSING_FIELD:craft:Bare-Craft:HISTORY", "THIN_FIELD:craft:Bare-Craft:HISTORY"]
    assert closed_field_reservations(held, subject_tasks(bare)) == ["MISSING_FIELD:craft:Bare-Craft:HISTORY"]
