from __future__ import annotations

from collections.abc import Sequence

from .open_work import TASK_ITEMS_MAX, TASK_PROMPTS, OpenTask, SubjectStanding, TaskKey, task_key
from .open_work_flagship_backlog import FLAGSHIP_KINDS, FLAGSHIP_TASK, FLAGSHIPS, Flagship

__all__ = ["FLAGSHIP_KINDS", "FLAGSHIP_PRIORITY", "FLAGSHIP_TASK", "flagship_problem", "flagship_tasks"]

FLAGSHIP_PRIORITY = "HIGH"
CATEGORY = "category"
KINDS_TEXT = f"{', '.join(FLAGSHIP_KINDS[:-1])} or {FLAGSHIP_KINDS[-1]}"
NEEDED = (
    "The {family} family page draws no flagship interactive yet. The backlog's candidate: {mechanism}, "
    "anchored on {anchor} and resting on the {count} facts named here; still to find or make: {lacks}."
)
ACCEPTANCE = (
    "One finished {kinds}, its spec and units resting on the facts named here or held by the family page and "
    "{anchor}, keyed to {anchor} and sent in a bundle for the category page {slug} with this task as "
    "task_key. A waiting or approved proposal naming the task closes it, and so does any component of those "
    "kinds the family page draws."
)
NOT_A_FLAGSHIP = "{key} names no family's flagship; list_open_work gives the open ones"
WRONG_KIND = "a flagship task is completed by a component of kind {kinds}"
NOT_DELIVERED = "a flagship task is completed by a delivered component, with its spec and units"
NOT_KEYED = "the proposal completes {key} only when it is keyed to the family's anchor craft {anchor}"


def flagship_tasks(standing: SubjectStanding) -> list[OpenTask]:
    subject = standing.subject
    flagship = FLAGSHIPS.get(subject.slug) if subject.kind == CATEGORY else None
    if flagship is None or not standing.component_kinds.isdisjoint(FLAGSHIP_KINDS):
        return []
    return [
        OpenTask(
            key=task_key(FLAGSHIP_TASK, subject),
            kind=FLAGSHIP_TASK,
            priority=FLAGSHIP_PRIORITY,
            subject=subject,
            needed=_needed(flagship),
            acceptance=ACCEPTANCE.format(kinds=KINDS_TEXT, anchor=flagship.anchor, slug=subject.slug),
            count=len(flagship.facts),
            fact_ids=list(flagship.facts[:TASK_ITEMS_MAX]),
            prompt=TASK_PROMPTS.get(FLAGSHIP_TASK),
        )
    ]


def flagship_problem(key: TaskKey, kind: str, crafts: Sequence[str], *, delivered: bool) -> str | None:
    flagship = FLAGSHIPS.get(key.slug or "") if key.subject_kind == CATEGORY else None
    if flagship is None or key.detail is not None:
        return NOT_A_FLAGSHIP.format(key=key.text())
    if kind not in FLAGSHIP_KINDS:
        return WRONG_KIND.format(kinds=KINDS_TEXT)
    if not delivered:
        return NOT_DELIVERED
    if flagship.anchor not in crafts:
        return NOT_KEYED.format(key=key.text(), anchor=flagship.anchor)
    return None


def _needed(flagship: Flagship) -> str:
    return NEEDED.format(
        family=flagship.family,
        mechanism=flagship.mechanism,
        anchor=flagship.anchor,
        count=len(flagship.facts),
        lacks=flagship.lacks,
    )
