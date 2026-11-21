from collections.abc import AsyncIterator

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.contribution_queue_tasks import my_tasks
from app.services.task_reservations import claim_task

from .picture_seed import NOW, SLUG, people_in, seeded_session

pytestmark = pytest.mark.db

SITE = "https://kalavigyan.example"
MASTHEAD = f"MISSING_PICTURE:craft:{SLUG}:slot-masthead"
MISSING_PROCESS = f"MISSING_FIELD:craft:{SLUG}:PROCESS"


@pytest.fixture
async def session() -> AsyncIterator[AsyncSession]:
    async for opened in seeded_session():
        yield opened


async def test_a_claimed_picture_task_is_listed_open_with_what_it_asks(session: AsyncSession) -> None:
    people = await people_in(session)
    await claim_task(session, people.researcher.id, MASTHEAD, site=SITE, now=NOW)
    mine = await my_tasks(session, people.researcher, site=SITE, now=NOW)
    (held,) = mine.claimed
    assert held.task_key == MASTHEAD and held.task is not None
    assert (held.task.kind, held.task.needed) == (
        "MISSING_PICTURE",
        "A first picture for the page of Image Contribution Test Craft, shown at its top.",
    )


async def test_a_picture_task_and_a_field_task_of_one_page_are_both_listed_open(
    session: AsyncSession,
) -> None:
    people = await people_in(session)
    for key in (MASTHEAD, MISSING_PROCESS):
        await claim_task(session, people.researcher.id, key, site=SITE, now=NOW)
    mine = await my_tasks(session, people.researcher, site=SITE, now=NOW)
    assert {held.task_key: held.task is not None for held in mine.claimed} == {
        MASTHEAD: True,
        MISSING_PROCESS: True,
    }
