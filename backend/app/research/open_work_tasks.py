from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from datetime import datetime

from app.core.roles import can
from app.models.enums import DISCIPLINES

from . import open_work_texts as texts
from .open_work import (
    COMPONENT_NEEDS,
    OWNER_ORDER,
    PRIORITIES,
    REVIEW_QUEUES,
    SUBJECT_KINDS,
    TASK_PROMPTS,
    FieldStanding,
    Hold,
    OpenTask,
    QueueStanding,
    SubjectStanding,
    Viewer,
    WorkFilters,
    task_key,
)

__all__ = [
    "HIGH_DEMAND_ANSWERS",
    "MEDIUM_DEMAND_ANSWERS",
    "chosen_tasks",
    "open_tasks",
    "review_tasks",
    "reviewed_queues",
    "subject_priority",
    "subject_tasks",
]

HIGH_DEMAND_ANSWERS = 25
MEDIUM_DEMAND_ANSWERS = 5
EMPTY_FIELD = FieldStanding()
PRIORITY_RANK = {priority: rank for rank, priority in enumerate(PRIORITIES)}
OWNER_RANK = {slug: rank for rank, slug in enumerate(OWNER_ORDER)}
SUBJECT_RANK = {kind: rank for rank, kind in enumerate(SUBJECT_KINDS)}
FIELD_RANK = {discipline: rank for rank, discipline in enumerate(DISCIPLINES)}
CATEGORY = "category"


def subject_priority(standing: SubjectStanding) -> str:
    if standing.subject.kind == CATEGORY:
        return "LOW"
    if standing.subject.slug in OWNER_RANK or standing.demand >= HIGH_DEMAND_ANSWERS:
        return "HIGH"
    if standing.gi or standing.curated or standing.demand >= MEDIUM_DEMAND_ANSWERS:
        return "MEDIUM"
    return "LOW"


def subject_tasks(standing: SubjectStanding) -> list[OpenTask]:
    return [
        *_field_tasks(standing),
        *_component_tasks(standing),
        *_page_tasks(standing),
        *_corroboration_tasks(standing),
        *_link_tasks(standing),
    ]


def reviewed_queues(role: str | None) -> tuple[str, ...]:
    if role is None:
        return ()
    return tuple(queue for queue, capability in REVIEW_QUEUES.items() if can(role, capability))


def review_tasks(queues: Mapping[str, QueueStanding], viewer: Viewer) -> list[OpenTask]:
    found = []
    for queue in reviewed_queues(viewer.review_role):
        waiting = queues.get(queue)
        if waiting is None or waiting.count == 0:
            continue
        found.append(
            OpenTask(
                key=task_key("REVIEW", None, queue),
                kind="REVIEW",
                priority="HIGH",
                subject=None,
                need=queue,
                needed=texts.review_needed(queue, waiting),
                acceptance=texts.REVIEW_ACCEPTANCE,
                count=waiting.count,
            )
        )
    return found


def open_tasks(
    standings: Iterable[SubjectStanding], queues: Mapping[str, QueueStanding], viewer: Viewer
) -> list[OpenTask]:
    ordered = sorted(standings, key=_subject_order)
    return [
        *review_tasks(queues, viewer),
        *(task for standing in ordered for task in subject_tasks(standing)),
    ]


def chosen_tasks(
    tasks: Sequence[OpenTask],
    filters: WorkFilters,
    *,
    holds: Mapping[str, Hold],
    closed: frozenset[str],
    viewer: Viewer,
    now: datetime,
) -> list[OpenTask]:
    kept = []
    for task in tasks:
        if task.key in closed or not _matches(task, filters):
            continue
        hold = holds.get(task.key)
        if hold is None or hold.expires_at <= now:
            kept.append(task)
        elif viewer.user_id is not None and hold.user_id == viewer.user_id:
            kept.append(task.model_copy(update={"reserved_until": hold.expires_at}))
    return sorted(kept, key=lambda task: PRIORITY_RANK[task.priority])


def _matches(task: OpenTask, filters: WorkFilters) -> bool:
    if filters.kind is not None and task.kind != filters.kind:
        return False
    if filters.priority is not None and task.priority != filters.priority:
        return False
    return filters.field is None or task.field == filters.field


def _subject_order(standing: SubjectStanding) -> tuple[int, int, bool, bool, int, int, str, str]:
    subject = standing.subject
    return (
        PRIORITY_RANK[subject_priority(standing)],
        OWNER_RANK.get(subject.slug, len(OWNER_RANK)),
        not standing.gi,
        not standing.curated,
        -standing.demand,
        SUBJECT_RANK[subject.kind],
        subject.name.casefold(),
        subject.slug,
    )


def _task(standing: SubjectStanding, kind: str, detail: str | None, wording: texts.Wording) -> OpenTask:
    return OpenTask(
        key=task_key(kind, standing.subject, detail),
        kind=kind,
        priority=subject_priority(standing),
        subject=standing.subject,
        field=detail if detail in FIELD_RANK else None,
        need=detail if detail in COMPONENT_NEEDS else None,
        needed=wording.needed,
        acceptance=wording.acceptance,
        count=wording.items.count,
        fact_ids=list(wording.items.ids) if wording.facts else [],
        source_ids=[] if wording.facts else list(wording.items.ids),
        prompt=TASK_PROMPTS.get(kind),
    )


def _field_tasks(standing: SubjectStanding) -> list[OpenTask]:
    found = []
    for discipline in DISCIPLINES:
        kind = _field_kind(standing, discipline)
        if kind is not None:
            held = standing.fields.get(discipline, EMPTY_FIELD)
            wording = texts.field_wording(kind, standing, discipline, held)
            found.append(_task(standing, kind, discipline, wording))
    return found


def _field_kind(standing: SubjectStanding, discipline: str) -> str | None:
    targets = standing.targets
    held = standing.fields.get(discipline, EMPTY_FIELD)
    if held.facts == 0 and held.section_sentences == 0:
        return "MISSING_FIELD" if discipline in targets.core_fields else None
    if held.facts < targets.facts_min:
        return "THIN_FIELD"
    if held.section_sentences < targets.section_sentences_min:
        return "SECTION"
    return None


def _component_tasks(standing: SubjectStanding) -> list[OpenTask]:
    if not standing.targets.components:
        return []
    return [
        _task(standing, "MISSING_COMPONENT", need, texts.component_wording(standing, need, kinds))
        for need, kinds in COMPONENT_NEEDS.items()
        if standing.component_kinds.isdisjoint(kinds)
    ]


def _page_tasks(standing: SubjectStanding) -> list[OpenTask]:
    if not standing.new_form:
        return [_task(standing, "PAGE_FORM", None, texts.page_form_wording(standing))]
    if not standing.layout:
        return [_task(standing, "PAGE_LAYOUT", None, texts.page_layout_wording(standing))]
    return []


def _corroboration_tasks(standing: SubjectStanding) -> list[OpenTask]:
    found = []
    for discipline in sorted(standing.fields, key=_field_order):
        held = standing.fields[discipline]
        if held.one_source.count:
            wording = texts.second_source_wording(standing, discipline, held.one_source)
            found.append(_task(standing, "SECOND_SOURCE", discipline, wording))
        if held.differing.count:
            wording = texts.differ_wording(standing, discipline, held.differing)
            found.append(_task(standing, "SOURCES_DIFFER", discipline, wording))
    return found


def _link_tasks(standing: SubjectStanding) -> list[OpenTask]:
    found = []
    if standing.dead_sources.count:
        found.append(_task(standing, "DEAD_SOURCE", None, texts.dead_wording(standing)))
    if standing.unarchived_sources.count:
        found.append(_task(standing, "UNARCHIVED_SOURCE", None, texts.unarchived_wording(standing)))
    return found


def _field_order(discipline: str | None) -> int:
    return FIELD_RANK.get(discipline or "", len(FIELD_RANK))
