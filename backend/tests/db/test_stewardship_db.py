import uuid
from collections.abc import AsyncIterator
from datetime import timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import InvalidInput, Refused
from app.data.craft_master_loader import ACTIVE
from app.models import Craft, CraftSteward, User
from app.research.stewardship import STEWARD_CRAFTS_MAX
from app.services.stewardship import adopt_craft, drop_craft, my_crafts

from .open_work_seed import NOW, OTHER, RESEARCHER, SITE, SLUG, opened_session

pytestmark = pytest.mark.db

PREFIX = f"craft:{SLUG}"


@pytest.fixture
async def session() -> AsyncIterator[AsyncSession]:
    async for opened in opened_session():
        yield opened


async def account(session: AsyncSession, user_id: uuid.UUID) -> User:
    found = await session.get(User, user_id)
    assert found is not None
    return found


async def test_an_adopted_craft_comes_back_as_one_package_with_every_gap_new(session: AsyncSession) -> None:
    steward = await account(session, RESEARCHER)
    package = await adopt_craft(session, steward, SLUG, site=SITE, now=NOW)
    assert (package.craft.slug, package.craft.page_url, package.stewards, package.seen_at) == (
        SLUG,
        f"{SITE}/crafts/{SLUG}",
        1,
        None,
    )
    assert package.tasks == [] and len(package.new_tasks) == package.total == 26
    assert package.new_tasks[0].key == f"MISSING_FIELD:{PREFIX}:OVERVIEW"


async def test_the_next_look_shows_only_the_gaps_opened_since_the_last_one_first(
    session: AsyncSession,
) -> None:
    steward = await account(session, RESEARCHER)
    await adopt_craft(session, steward, SLUG, site=SITE, now=NOW)
    row = await session.scalar(select(CraftSteward).where(CraftSteward.userId == RESEARCHER))
    assert row is not None
    gap = f"MISSING_FIELD:{PREFIX}:POLICY"
    row.seenTaskKeys = [key for key in row.seenTaskKeys if key != gap]
    await session.flush()
    later = NOW + timedelta(hours=1)
    (package,) = (await my_crafts(session, steward, site=SITE, now=later)).crafts
    assert [task.key for task in package.new_tasks] == [gap]
    assert len(package.tasks) == 25 and package.seen_at == NOW
    (again,) = (await my_crafts(session, steward, site=SITE, now=later)).crafts
    assert (again.new_tasks, again.seen_at) == ([], later)


async def test_stewardship_never_blocks_another_account(session: AsyncSession) -> None:
    first = await adopt_craft(session, await account(session, RESEARCHER), SLUG, site=SITE, now=NOW)
    second = await adopt_craft(session, await account(session, OTHER), SLUG, site=SITE, now=NOW)
    assert (first.stewards, second.stewards) == (1, 2)
    assert len(second.new_tasks) == 26
    again = await adopt_craft(session, await account(session, OTHER), SLUG, site=SITE, now=NOW)
    assert again.stewards == 2


async def test_a_dropped_craft_leaves_the_list_and_cannot_be_dropped_twice(session: AsyncSession) -> None:
    steward = await account(session, RESEARCHER)
    await adopt_craft(session, steward, SLUG, site=SITE, now=NOW)
    dropped = await drop_craft(session, steward, SLUG, now=NOW + timedelta(minutes=5))
    assert (dropped.craft_slug, dropped.adopted) == (SLUG, False)
    assert (await my_crafts(session, steward, site=SITE, now=NOW)).crafts == []
    with pytest.raises(InvalidInput, match="does not steward"):
        await drop_craft(session, steward, SLUG, now=NOW)


async def test_one_account_stewards_at_most_ten_crafts(session: AsyncSession) -> None:
    steward = await account(session, OTHER)
    slugs = list(
        await session.scalars(
            select(Craft.slug)
            .where(Craft.status == ACTIVE, Craft.isCatchAll.is_(False), Craft.slug != SLUG)
            .order_by(Craft.slug)
            .limit(STEWARD_CRAFTS_MAX)
        )
    )
    ids = list(await session.scalars(select(Craft.id).where(Craft.slug.in_(slugs))))
    session.add_all([CraftSteward(userId=OTHER, craftId=craft_id, adoptedAt=NOW) for craft_id in ids])
    await session.flush()
    assert len(ids) == STEWARD_CRAFTS_MAX
    with pytest.raises(Refused, match="stewards 10 crafts"):
        await adopt_craft(session, steward, SLUG, site=SITE, now=NOW)
