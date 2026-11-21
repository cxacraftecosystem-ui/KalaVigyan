from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy.ext.asyncio import AsyncSession

from app.research.open_work import TASK_ITEMS_MAX, OpenTask, SubjectStanding, task_key
from app.research.open_work_tasks import subject_priority
from app.research.open_work_translation_keys import TRANSLATE_TASK
from app.research.page_translation_texts import TRANSLATE_ACCEPTANCE, translate_needed
from app.research.translation_passages import TaskPassage
from app.research.translation_regions import translation_priority

from .page_text_index import covered_counts, indexed_passages, text_counts
from .page_translation_store import live_hashes
from .translation_offers import home_states, page_offers

__all__ = ["translation_tasks"]


async def translation_tasks(
    session: AsyncSession, standings: Sequence[SubjectStanding], *, passages: int = 0
) -> list[OpenTask]:
    slugs = [standing.subject.slug for standing in standings]
    if not slugs:
        return []
    totals = await text_counts(session, slugs)
    covered = await covered_counts(session, slugs)
    states = await home_states(session, slugs)
    tasks: list[OpenTask] = []
    for standing in standings:
        page = (standing.subject.kind, standing.subject.slug)
        total = totals.get(page, 0)
        if total == 0:
            continue
        for language in page_offers(*page, states):
            left = total - covered.get((*page, language), 0)
            if left > 0:
                tasks.append(_task(standing, language, left, states.get(page[1], ())))
    if passages:
        return [await _with_passages(session, task, passages) for task in tasks]
    return tasks


def _task(standing: SubjectStanding, language: str, left: int, states: Sequence[str]) -> OpenTask:
    subject = standing.subject
    return OpenTask(
        key=task_key(TRANSLATE_TASK, subject, language),
        kind=TRANSLATE_TASK,
        priority=translation_priority(subject_priority(standing), language, states),
        subject=subject,
        needed=translate_needed(subject.name, language, left),
        acceptance=TRANSLATE_ACCEPTANCE,
        count=left,
    )


async def _with_passages(session: AsyncSession, task: OpenTask, most: int) -> OpenTask:
    if task.subject is None:
        return task
    page = (task.subject.kind, task.subject.slug)
    language = task.key.rsplit(":", 1)[-1]
    live = await live_hashes(session, page, language)
    found: list[TaskPassage] = [
        passage for passage in await indexed_passages(session, page) if passage.source_hash not in live
    ]
    return task.model_copy(update={"passages": found[: min(most, TASK_ITEMS_MAX)]})
