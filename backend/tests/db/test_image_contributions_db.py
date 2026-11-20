import uuid
from collections.abc import AsyncIterator
from typing import Any, cast

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import InvalidInput
from app.models import MediaAsset
from app.services import image_contributions as images

from ..pictures import AI_SOURCE, FakeObjects, picture, screen_tools
from .picture_seed import NOW, SLUG, People, declaration, people_in, seeded_session, sent

pytestmark = pytest.mark.db


@pytest.fixture
async def session() -> AsyncIterator[AsyncSession]:
    async for opened in seeded_session():
        yield opened


@pytest.fixture
async def people(session: AsyncSession) -> People:
    return await people_in(session)


async def test_a_researchers_ai_picture_waits_private_and_an_admin_shares_it(
    session: AsyncSession, people: People
) -> None:
    row = await sent(session, people.researcher, picture(note=AI_SOURCE))
    asset = await session.get(MediaAsset, row.assetId)
    assert (row.status, row.aiMarked, asset is not None and asset.visibility) == ("PENDING", True, "PRIVATE")
    assert asset is not None and (asset.model, asset.width, asset.height) == (
        "ChatGPT, gpt-image-1",
        800,
        600,
    )
    await images.approve(session, row.id, people.admin, "Matches the fact", now=NOW)
    assert (row.status, row.reviewedById, asset.visibility, asset.approvedById) == (
        "APPROVED",
        people.admin.id,
        "CRAFT_SHARED",
        people.admin.id,
    )


async def test_a_professors_clear_picture_is_approved_at_once(session: AsyncSession, people: People) -> None:
    row = await sent(session, people.professor, picture())
    asset = await session.get(MediaAsset, row.assetId)
    assert (row.status, row.reviewedById, asset is not None and asset.visibility) == (
        "APPROVED",
        people.professor.id,
        "CRAFT_SHARED",
    )


async def test_a_photograph_whose_own_metadata_says_ai_made_is_refused(
    session: AsyncSession, people: People
) -> None:
    with pytest.raises(InvalidInput):
        await sent(
            session,
            people.researcher,
            picture(note=AI_SOURCE),
            origin="PHOTOGRAPH",
            generator=None,
            prompt=None,
        )


async def test_the_same_picture_twice_is_refused(session: AsyncSession, people: People) -> None:
    await sent(session, people.researcher, picture(seed=3))
    with pytest.raises(images.ContributionRefused):
        await sent(session, people.other_researcher, picture(seed=3))


async def test_a_picture_is_decided_once_and_never_by_its_contributor(
    session: AsyncSession, people: People
) -> None:
    row = await sent(session, people.researcher, picture())
    with pytest.raises(images.ContributionRefused):
        await images.approve(session, row.id, people.researcher, None, now=NOW)
    await images.reject(session, row.id, people.admin, "The colour is wrong", now=NOW)
    with pytest.raises(images.ContributionRefused):
        await images.approve(session, row.id, people.admin, None, now=NOW)


async def test_only_the_contributor_sends_the_file_and_only_once(
    session: AsyncSession, people: People
) -> None:
    row = await images.declare(session, people.researcher, declaration(), now=NOW)
    objects, tools = cast(Any, FakeObjects()), screen_tools()
    stranger = images.Upload(contribution_id=row.id, user=people.other_researcher, data=picture())
    with pytest.raises(images.UnknownImage):
        await images.receive_file(session, stranger, objects=objects, tools=tools, now=NOW)
    own = images.Upload(contribution_id=row.id, user=people.researcher, data=picture())
    await images.receive_file(session, own, objects=objects, tools=tools, now=NOW)
    again = images.Upload(contribution_id=row.id, user=people.researcher, data=picture(seed=9))
    with pytest.raises(images.ContributionRefused):
        await images.receive_file(session, again, objects=objects, tools=tools, now=NOW)


async def test_a_declaration_names_a_real_craft_stage_material_and_shown_facts(
    session: AsyncSession, people: People
) -> None:
    with pytest.raises(InvalidInput):
        await images.declare(session, people.researcher, declaration(craftSlug="No-Such-Craft"), now=NOW)
    with pytest.raises(InvalidInput, match="stage"):
        await images.declare(session, people.researcher, declaration(stageId=str(uuid.uuid4())), now=NOW)
    with pytest.raises(InvalidInput, match="material"):
        await images.declare(session, people.researcher, declaration(materialId=str(uuid.uuid4())), now=NOW)
    with pytest.raises(InvalidInput):
        await images.declare(session, people.researcher, declaration(claimIds=[str(uuid.uuid4())]), now=NOW)


async def test_an_approved_picture_cannot_be_withdrawn_but_a_pending_one_can(
    session: AsyncSession, people: People
) -> None:
    approved = await sent(session, people.professor, picture(seed=4))
    with pytest.raises(images.ContributionRefused):
        await images.withdraw(session, approved.id, people.professor)
    asset = await session.get(MediaAsset, approved.assetId)
    assert (approved.status, asset is not None and asset.visibility) == ("APPROVED", "CRAFT_SHARED")
    pending = await sent(session, people.researcher, picture(640, 480, seed=5))
    await images.withdraw(session, pending.id, people.researcher)
    assert [found.id for found in await images.queue(session, "WITHDRAWN") if found.id == pending.id] == [
        pending.id
    ]


async def test_a_view_labels_an_ai_picture_as_an_illustration_with_its_tool_and_its_screen(
    session: AsyncSession, people: People
) -> None:
    row = await sent(session, people.researcher, picture())
    (view,) = await images.views(session, [row], objects=cast(Any, FakeObjects()), now=NOW)
    assert view.label == "Illustration, made with ChatGPT, gpt-image-1"
    assert (
        view.craft_slug == SLUG
        and view.file_url is not None
        and view.file_url.startswith("https://bucket.test/")
    )
    assert view.screen is not None and (view.screen.verdict, view.screen.reasons) == ("CLEAR", [])
