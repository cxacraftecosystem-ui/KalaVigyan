from collections.abc import AsyncIterator

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.research.open_work import Viewer, WorkFilters
from app.services import image_contributions as images
from app.services.open_work import list_open_work

from ..pictures import picture
from .picture_seed import MATERIAL, NOW, SLUG, STAGE, People, people_in, seeded_session, sent

pytestmark = pytest.mark.db

SITE = "https://kalavigyan.example"
PREFIX = f"MISSING_PICTURE:craft:{SLUG}"
MASTHEAD = f"{PREFIX}:slot-masthead"
STAGE_TASK = f"{PREFIX}:stage-{STAGE}"
MATERIAL_TASK = f"{PREFIX}:material-{MATERIAL}"


@pytest.fixture
async def session() -> AsyncIterator[AsyncSession]:
    async for opened in seeded_session():
        yield opened


@pytest.fixture
async def people(session: AsyncSession) -> People:
    return await people_in(session)


async def picture_keys(session: AsyncSession) -> list[str]:
    filters = WorkFilters(craft_slug=SLUG, kind="MISSING_PICTURE")
    work = await list_open_work(session, filters, Viewer(), site=SITE, now=NOW)
    return [task.key for task in work.tasks]


async def test_a_craft_asks_for_its_first_picture_and_a_picture_of_each_stage_and_material(
    session: AsyncSession,
) -> None:
    filters = WorkFilters(craft_slug=SLUG, kind="MISSING_PICTURE")
    work = await list_open_work(session, filters, Viewer(), site=SITE, now=NOW)
    assert [task.key for task in work.tasks] == [MASTHEAD, STAGE_TASK, MATERIAL_TASK]
    tasks = {task.key: task for task in work.tasks}
    assert tasks[STAGE_TASK].needed == (
        "A picture of the stage Reducing the vat of Image Contribution Test Craft, as it is done."
    )
    assert (
        tasks[MATERIAL_TASK].needed
        == "A picture of Test indigo cake, a material of Image Contribution Test Craft."
    )
    assert "give_pictures" in tasks[MASTHEAD].acceptance and tasks[MASTHEAD].count == 1


async def test_a_picture_waiting_for_review_holds_its_task_and_a_refusal_reopens_it(
    session: AsyncSession, people: People
) -> None:
    row = await sent(session, people.researcher, picture(seed=61), stageId=str(STAGE))
    assert await picture_keys(session) == [MASTHEAD, MATERIAL_TASK]
    await images.reject(session, row.id, people.admin, "The stage is not shown", now=NOW)
    assert await picture_keys(session) == [MASTHEAD, STAGE_TASK, MATERIAL_TASK]


async def test_an_approved_picture_closes_its_task(session: AsyncSession, people: People) -> None:
    await sent(session, people.professor, picture(seed=62), slot="MASTHEAD")
    assert await picture_keys(session) == [STAGE_TASK, MATERIAL_TASK]
