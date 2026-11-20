import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Any

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ImageContribution, MediaAsset, User
from app.research.page_proposals import PageBundle
from app.services.page_preview import preview_page
from app.services.page_preview_links import preview_document
from app.services.page_preview_pictures import own_picture_file
from app.services.page_proposals import PageTools, propose_page

from .page_documents_seed import CRAFT, CRAFT_CLAIM, CRAFT_SLUG, seed
from .testimony_seed import rolled_back_session

pytestmark = pytest.mark.db

NOW = datetime(2026, 11, 20, 11, 0, tzinfo=UTC)
SITE = "https://kalavigyan.example"
GIVER = uuid.UUID("9e0e0000-0000-4000-8000-000000000001")
OTHER = uuid.UUID("9e0e0000-0000-4000-8000-000000000002")
GIVEN = uuid.UUID("9e0e0000-0000-4000-8000-0000000000a1")
ASSET = uuid.UUID("9e0e0000-0000-4000-8000-0000000000b1")
LABEL = f"{CRAFT_SLUG.lower()}/pictures/contributed-{GIVEN.hex[:12]}"


def bundle(contribution_id: uuid.UUID) -> PageBundle:
    return PageBundle.model_validate(
        {
            "subject": {"kind": "craft", "slug": CRAFT_SLUG},
            "pictures": [{"contributionId": str(contribution_id)}],
        }
    )


def unused(*_: Any, **__: Any) -> Any:
    raise AssertionError("a picture given already starts no upload")


def no_uploads() -> PageTools:
    nothing: Any = unused
    return PageTools(
        gates=nothing,
        fetcher=nothing,
        start_picture=nothing,
        spend=lambda kind: None,
        origin="AGENT",
        site=SITE,
    )


@pytest.fixture
async def session() -> AsyncIterator[AsyncSession]:
    async for opened in rolled_back_session():
        await seed(opened)
        for user_id in (GIVER, OTHER):
            opened.add(
                User(id=user_id, name="Picture giver", email=f"{user_id.hex}@example.org", role="RESEARCHER")
            )
        opened.add(
            MediaAsset(
                id=ASSET, s3Key=f"media/given/{GIVEN.hex}.webp", mime="image/webp", width=1200, height=800
            )
        )
        await opened.flush()
        opened.add(
            ImageContribution(
                id=GIVEN,
                contributorId=GIVER,
                craftId=CRAFT,
                claimIds=[CRAFT_CLAIM],
                origin="PHOTOGRAPH",
                caption="The printed cotton after its alum bath",
                altText="A length of printed cotton on a line",
                termsVersion="2026-11-19",
                rightsConfirmedAt=NOW,
                status="PENDING",
                sha256=GIVEN.hex * 2,
                assetId=ASSET,
            )
        )
        await opened.flush()
        yield opened


async def person(session: AsyncSession, user_id: uuid.UUID) -> User:
    found = await session.get(User, user_id)
    assert found is not None
    return found


async def test_a_picture_the_account_gave_is_drawn_in_its_preview_from_its_own_private_address(
    session: AsyncSession,
) -> None:
    giver = await person(session, GIVER)
    previewed = await preview_page(session, giver, bundle(GIVEN), site=SITE, now=NOW)
    assert [(part.part, part.outcome) for part in previewed.parts] == [("picture", "SHOWN")]
    document = await preview_document(session, giver, previewed.preview_url.rsplit("/", 1)[1], now=NOW)
    assert document["specs"][LABEL]["picture"]["src"] == f"/api/knowledge/pages/pictures/{GIVEN}"
    assert await own_picture_file(session, giver, GIVEN) is not None
    assert await own_picture_file(session, await person(session, OTHER), GIVEN) is None


async def test_another_account_cannot_show_or_propose_someone_else_s_picture(session: AsyncSession) -> None:
    other = await person(session, OTHER)
    previewed = await preview_page(session, other, bundle(GIVEN), site=SITE, now=NOW)
    (part,) = previewed.parts
    assert part.outcome == "REFUSED" and str(GIVEN) in part.message
    tools = no_uploads()
    result = await propose_page(session, other, bundle(GIVEN), tools=tools, now=NOW)
    assert [(each.part, each.outcome) for each in result.parts] == [("picture", "REFUSED")]


async def test_a_given_picture_in_a_proposed_bundle_waits_as_given_and_starts_no_upload(
    session: AsyncSession,
) -> None:
    tools = no_uploads()
    result = await propose_page(session, await person(session, GIVER), bundle(GIVEN), tools=tools, now=NOW)
    (part,) = result.parts
    assert (part.part, part.outcome, part.status, part.id) == ("picture", "ACCEPTED", "PENDING", str(GIVEN))
    assert part.upload is None
