import uuid
from collections.abc import AsyncIterator
from datetime import timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import InvalidInput, Refused
from app.models import ComponentProposal, TaskReservation
from app.research.open_work import Viewer, WorkFilters
from app.services.open_work import list_open_work
from app.services.task_reservations import claim_task, release_task

from .open_work_seed import (
    CHEMISTRY_FACT,
    DEAD,
    HISTORY_ONE_SOURCE,
    NOW,
    OTHER,
    RESEARCHER,
    SITE,
    SLUG,
    UNARCHIVED,
    opened_session,
)

pytestmark = pytest.mark.db

PREFIX = f"craft:{SLUG}"
SECTION = f"SECTION:{PREFIX}:HISTORY"
EXPECTED = [
    f"MISSING_FIELD:{PREFIX}:OVERVIEW",
    f"MISSING_FIELD:{PREFIX}:PROCESS",
    f"THIN_FIELD:{PREFIX}:CHEMISTRY",
    f"MISSING_FIELD:{PREFIX}:PHYSICS",
    f"MISSING_FIELD:{PREFIX}:MATERIALS",
    f"MISSING_FIELD:{PREFIX}:GEOGRAPHY",
    f"MISSING_FIELD:{PREFIX}:GEOLOGY",
    f"MISSING_FIELD:{PREFIX}:CLIMATE",
    f"MISSING_FIELD:{PREFIX}:ECOLOGY",
    f"MISSING_FIELD:{PREFIX}:BOTANY",
    SECTION,
    f"MISSING_FIELD:{PREFIX}:ECONOMICS",
    f"MISSING_FIELD:{PREFIX}:DESIGN",
    f"MISSING_FIELD:{PREFIX}:HEALTH",
    f"MISSING_FIELD:{PREFIX}:SOCIETY",
    f"MISSING_FIELD:{PREFIX}:POLICY",
    f"MISSING_COMPONENT:{PREFIX}:molecules",
    f"MISSING_COMPONENT:{PREFIX}:map",
    f"MISSING_COMPONENT:{PREFIX}:reaction-player",
    f"MISSING_COMPONENT:{PREFIX}:pictures",
    f"PAGE_FORM:{PREFIX}",
    f"SECOND_SOURCE:{PREFIX}:CHEMISTRY",
    f"SOURCES_DIFFER:{PREFIX}:CHEMISTRY",
    f"SECOND_SOURCE:{PREFIX}:HISTORY",
    f"DEAD_SOURCE:{PREFIX}",
    f"UNARCHIVED_SOURCE:{PREFIX}",
]


@pytest.fixture
async def session() -> AsyncIterator[AsyncSession]:
    async for opened in opened_session():
        yield opened


async def listed(session: AsyncSession, viewer: Viewer = Viewer(), **filters: object) -> list[str]:
    work = await list_open_work(session, WorkFilters(craft_slug=SLUG, **filters), viewer, site=SITE, now=NOW)
    return [task.key for task in work.tasks]


async def test_a_craft_s_open_work_is_computed_from_its_facts_sections_components_and_sources(
    session: AsyncSession,
) -> None:
    work = await list_open_work(session, WorkFilters(craft_slug=SLUG), Viewer(), site=SITE, now=NOW)
    assert [task.key for task in work.tasks] == EXPECTED
    assert work.total == len(EXPECTED)
    tasks = {task.key: task for task in work.tasks}
    assert {task.priority for task in work.tasks} == {"MEDIUM"}
    assert tasks[SECTION].needed.endswith("but the published section has 2 sentences.")
    assert tasks[f"THIN_FIELD:{PREFIX}:CHEMISTRY"].count == 2
    assert tasks[f"SECOND_SOURCE:{PREFIX}:HISTORY"].fact_ids == [HISTORY_ONE_SOURCE]
    assert tasks[f"SOURCES_DIFFER:{PREFIX}:CHEMISTRY"].fact_ids == [CHEMISTRY_FACT]
    assert tasks[f"DEAD_SOURCE:{PREFIX}"].source_ids == [str(DEAD)]
    assert tasks[f"UNARCHIVED_SOURCE:{PREFIX}"].source_ids == [str(UNARCHIVED)]
    assert tasks[SECTION].subject is not None and tasks[SECTION].subject.page_url == f"{SITE}/crafts/{SLUG}"


async def test_filters_narrow_the_work_and_a_wrong_subject_is_refused(session: AsyncSession) -> None:
    assert await listed(session, field="HISTORY") == [SECTION, f"SECOND_SOURCE:{PREFIX}:HISTORY"]
    assert await listed(session, kind="PAGE_FORM") == [f"PAGE_FORM:{PREFIX}"]
    assert await listed(session, priority="HIGH") == []
    with pytest.raises(InvalidInput, match="is a craft, not a family"):
        await list_open_work(session, WorkFilters(family_slug=SLUG), Viewer(), site=SITE, now=NOW)
    with pytest.raises(InvalidInput, match="No craft has the slug"):
        await list_open_work(
            session, WorkFilters(craft_slug="No-Such-Craft-Anywhere"), Viewer(), site=SITE, now=NOW
        )


async def test_a_claimed_task_leaves_others_lists_until_it_is_released(session: AsyncSession) -> None:
    held = await claim_task(session, RESEARCHER, SECTION, site=SITE, now=NOW)
    assert (held.held, held.reserved_until) == (True, NOW + timedelta(hours=2))
    assert held.task is not None and held.task.key == SECTION
    mine = await list_open_work(
        session, WorkFilters(craft_slug=SLUG), Viewer(user_id=RESEARCHER), site=SITE, now=NOW
    )
    assert {task.key: task.reserved_until for task in mine.tasks}[SECTION] == NOW + timedelta(hours=2)
    assert SECTION not in await listed(session, Viewer(user_id=OTHER))
    with pytest.raises(Refused, match="reserved by another account"):
        await claim_task(session, OTHER, SECTION, site=SITE, now=NOW + timedelta(minutes=5))
    with pytest.raises(InvalidInput, match="no reservation"):
        await release_task(session, OTHER, SECTION, now=NOW)
    released = await release_task(session, RESEARCHER, SECTION, now=NOW + timedelta(minutes=10))
    assert (released.held, released.reserved_until) == (False, None)
    assert SECTION in await listed(session, Viewer(user_id=OTHER))


async def test_claiming_again_renews_and_an_expired_reservation_returns_to_the_list(
    session: AsyncSession,
) -> None:
    await claim_task(session, RESEARCHER, SECTION, site=SITE, now=NOW)
    renewed = await claim_task(session, RESEARCHER, SECTION, site=SITE, now=NOW + timedelta(hours=1))
    assert renewed.reserved_until == NOW + timedelta(hours=3)
    later = NOW + timedelta(hours=4)
    taken = await claim_task(session, OTHER, SECTION, site=SITE, now=later)
    assert taken.reserved_until == later + timedelta(hours=2)
    rows = (
        await session.scalars(
            select(TaskReservation)
            .where(TaskReservation.taskKey == SECTION)
            .execution_options(populate_existing=True)
        )
    ).all()
    endings = sorted((row.userId == RESEARCHER, row.ending) for row in rows)
    assert endings == [(False, None), (True, "EXPIRED")]


async def test_one_account_holds_at_most_five_tasks(session: AsyncSession) -> None:
    for key in EXPECTED[:5]:
        await claim_task(session, RESEARCHER, key, site=SITE, now=NOW)
    with pytest.raises(Refused, match="holds 5 tasks"):
        await claim_task(session, RESEARCHER, EXPECTED[5], site=SITE, now=NOW)


@pytest.mark.parametrize(
    ("key", "says"),
    [
        ("REVIEW:FACTS", "never reserved"),
        (f"MISSING_COMPONENT:{PREFIX}:what-if", "No open task"),
        (f"MISSING_FIELD:{PREFIX}:HISTORY", "No open task"),
        ("THIN_FIELD:craft:No-Such-Craft-Anywhere:HISTORY", "No craft has the slug"),
    ],
)
async def test_only_an_open_task_can_be_reserved(session: AsyncSession, key: str, says: str) -> None:
    with pytest.raises(InvalidInput, match=says):
        await claim_task(session, RESEARCHER, key, site=SITE, now=NOW)


async def test_review_queues_reach_reviewers_only(session: AsyncSession) -> None:
    session.add(
        ComponentProposal(
            proposerId=OTHER,
            label="shared/chemistry/zircovane-crystal",
            title="Zircovane crystal",
            description="A turnable model of the zircovane crystal lattice that binds the dye to cotton.",
            kind="molecule_3d",
            field="CHEMISTRY",
            subjects=[{"kind": "CRAFT", "key": SLUG}],
        )
    )
    await session.flush()
    admin = await list_open_work(
        session,
        WorkFilters(kind="REVIEW"),
        Viewer(user_id=uuid.uuid4(), review_role="ADMIN"),
        site=SITE,
        now=NOW,
    )
    assert "REVIEW:COMPONENTS" in [task.key for task in admin.tasks]
    assert all(task.key.startswith("REVIEW:") for task in admin.tasks)
    student = await list_open_work(
        session,
        WorkFilters(kind="REVIEW"),
        Viewer(user_id=uuid.uuid4(), review_role="STUDENT"),
        site=SITE,
        now=NOW,
    )
    assert student.tasks == []
