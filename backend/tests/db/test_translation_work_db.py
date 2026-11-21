import uuid
from collections.abc import AsyncIterator
from typing import Any

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import Refused
from app.models import TaskReservation
from app.research.open_work import SubjectStanding, TaskSubject, Viewer, WorkFilters
from app.services.open_work import SUBJECT_TARGETS, list_open_work
from app.services.open_work_subjects import subject_by_key
from app.services.open_work_translations import translation_tasks
from app.services.page_english import english_page
from app.services.page_text_index import refresh_page_texts
from app.services.page_translation_review import approve_translation, reject_translation, review_list
from app.services.page_translations import translation_reports
from app.services.task_reservations import claim_task
from app.services.translation_readers import set_reader_languages

from .translation_seed import (
    HINDI_LEDE,
    HINDI_PLANT,
    LEDE,
    NOW,
    PLANT,
    SITE,
    SLUG,
    bundle,
    hindi,
    opened_session,
    person,
)

pytestmark = pytest.mark.db

PAGE = ("craft", SLUG)
HINDI_TASK = f"TRANSLATE:craft:{SLUG}:hi"
GUJARATI_TASK = f"TRANSLATE:craft:{SLUG}:gu"


@pytest.fixture
async def session() -> AsyncIterator[AsyncSession]:
    async for opened in opened_session():
        english = await english_page(opened, PAGE)
        assert english is not None
        await refresh_page_texts(opened, PAGE, english.tag, english.document.content)
        yield opened


def standing(*, gi: bool) -> SubjectStanding:
    subject = TaskSubject(
        kind="craft", slug=SLUG, name="Translation Test Craft", page_url=f"{SITE}/crafts/{SLUG}"
    )
    return SubjectStanding(subject=subject, targets=SUBJECT_TARGETS["craft"], gi=gi)


async def proposed(
    session: AsyncSession, user: Any, *passages: dict[str, Any], task_key: str | None = None
) -> list[Any]:
    subject = await subject_by_key(session, "craft", SLUG)
    part = bundle(*passages, task_key=task_key).translation
    assert part is not None
    return await translation_reports(session, user, subject, part, origin="AGENT", now=NOW)


async def test_a_page_offers_its_region_s_language_first_and_hindi_with_its_passages(
    session: AsyncSession,
) -> None:
    tasks = await translation_tasks(session, [standing(gi=True)])
    assert [(task.key, task.priority, task.count) for task in tasks] == [
        (GUJARATI_TASK, "MEDIUM", 2),
        (HINDI_TASK, "LOW", 2),
    ]
    assert "into Gujarati (ગુજરાતી): 2 passages" in tasks[0].needed
    claimed = await translation_tasks(session, [standing(gi=True)], passages=20)
    hindi_task = next(task for task in claimed if task.key == HINDI_TASK)
    assert [passage.key for passage in hindi_task.passages] == [LEDE, PLANT]
    assert hindi_task.passages[1].fixed == [1] and hindi_task.passages[1].cited == [3]
    assert hindi_task.passages[0].texts == ["The cloth is dyed 3 times in an indigo ", "vat."]


async def test_a_claimed_task_lists_its_passages_and_closes_when_none_is_left(session: AsyncSession) -> None:
    translator = await person(session, "RESEARCHER")
    held = await claim_task(session, translator.id, HINDI_TASK, site=SITE, now=NOW)
    assert held.task is not None and [passage.key for passage in held.task.passages] == [LEDE, PLANT]
    first = await proposed(session, translator, hindi(LEDE, HINDI_LEDE), task_key=HINDI_TASK)
    assert first[0].status == "DRAFT"
    assert await _ending(session) is None
    listed = await list_open_work(
        session,
        WorkFilters(craft_slug=SLUG, kind="TRANSLATE"),
        Viewer(user_id=translator.id),
        site=SITE,
        now=NOW,
    )
    assert {task.key: task.count for task in listed.tasks}[HINDI_TASK] == 1
    await proposed(session, translator, hindi(PLANT, HINDI_PLANT), task_key=HINDI_TASK)
    assert await _ending(session) == "COMPLETED"
    wrong = await proposed(session, translator, hindi(LEDE, HINDI_LEDE), task_key=GUJARATI_TASK)
    assert "is not the TRANSLATE task of this part" in wrong[0].message


async def test_only_a_reviewer_who_reads_the_language_decides_and_never_their_own(
    session: AsyncSession,
) -> None:
    translator = await person(session, "RESEARCHER")
    reads_hindi = await person(session, "PROFESSOR", reads=("hi",))
    reads_tamil = await person(session, "PROFESSOR", reads=("ta",))
    reports = await proposed(session, translator, hindi(LEDE, HINDI_LEDE), hindi(PLANT, HINDI_PLANT))
    lede, plant = (uuid.UUID(str(report.id)) for report in reports)
    queue = await review_list(session, reads_hindi, limit=10, site=SITE)
    assert (queue.languages, queue.total) == (["hi"], 2)
    assert sorted(item.key for item in queue.items) == [LEDE, PLANT] and all(
        item.current for item in queue.items
    )
    assert (await review_list(session, reads_tamil, limit=10, site=SITE)).total == 0
    with pytest.raises(Refused, match="who reads Hindi"):
        await approve_translation(session, reads_tamil, lede, note=None, now=NOW)
    approved = await approve_translation(session, reads_hindi, lede, note=None, now=NOW)
    rejected = await reject_translation(
        session, reads_hindi, plant, note="The second clause is missing.", now=NOW
    )
    assert (approved.status, rejected.status) == ("APPROVED", "REJECTED")
    with pytest.raises(Refused, match="decided already"):
        await approve_translation(session, reads_hindi, plant, note=None, now=NOW)
    own = await proposed(session, reads_hindi, hindi(PLANT, HINDI_PLANT))
    assert own[0].status == "APPROVED"
    student = await person(session, "RESEARCHER")
    with pytest.raises(Refused, match="Only a Professor or Admin"):
        await set_reader_languages(session, student, ["hi"])
    assert await set_reader_languages(session, reads_tamil, ["ur", "hi", "en"]) == ("hi", "ur")


async def _ending(session: AsyncSession) -> str | None:
    return await session.scalar(
        select(TaskReservation.ending)
        .where(TaskReservation.taskKey == HINDI_TASK)
        .execution_options(populate_existing=True)
    )
