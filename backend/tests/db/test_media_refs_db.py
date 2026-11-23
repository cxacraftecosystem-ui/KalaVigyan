import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime

import pytest
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_engine
from app.models import Claim, MediaRef, MediaRefClaim
from app.research.image_relevance import ChosenImage, Illustration
from app.research.images import ImageCandidate
from app.services.claim_seed import seed_id
from app.services.media_ref_store import SqlMediaStore, media_ref_id, media_url_key, stored_pictures

pytestmark = pytest.mark.db

KUT_CLAIM = uuid.UUID("c407fde1-3c40-5c81-8a5e-320317aacf9d")
VAM_SOURCE = seed_id("source", "ie:ajrakh:S3")
RETRIEVED = datetime(2026, 11, 17, 10, 20, tzinfo=UTC)
VAM_PAGE = "https://collections.vam.ac.uk/item/O132500/"
VAM_IMAGE = "https://framemark.vam.ac.uk/collections/2015HK4003/full/!100,100/0/default.jpg"


@pytest.fixture
async def session() -> AsyncIterator[AsyncSession]:
    async with get_engine().connect() as connection:
        transaction = await connection.begin()
        try:
            session = AsyncSession(bind=connection, expire_on_commit=False, autoflush=False)
            yield session
            await session.close()
        finally:
            await transaction.rollback()


def store_for(session: AsyncSession) -> SqlMediaStore:
    def sessions() -> AsyncSession:
        return AsyncSession(bind=session.bind, expire_on_commit=False, autoflush=False)

    return SqlMediaStore(sessions)


def vam_card() -> ChosenImage:
    candidate = ImageCandidate(
        provider="searxng",
        page_url=VAM_PAGE,
        image_url=VAM_IMAGE,
        original_url=VAM_IMAGE,
        title="Ajrakh process sample",
        description="Strips of cotton cloth block-printed in progressive stages of the ajrakh process.",
        site="collections.vam.ac.uk",
        retrieved_at=RETRIEVED,
    )
    return ChosenImage(candidate, Illustration(claim_ids=(KUT_CLAIM,), shared=2))


async def test_a_chosen_picture_is_stored_once_with_its_claims_and_page_source(session: AsyncSession) -> None:
    store = store_for(session)
    first = (await store.keep([vam_card()]))[0]
    again = (await store.keep([vam_card()]))[0]
    key = media_url_key("searxng", VAM_PAGE, VAM_IMAGE)
    assert first == again
    assert first.id == media_ref_id(key)
    assert (first.display, first.source_id, first.width, first.licence) == (
        "LINK_CARD",
        str(VAM_SOURCE),
        None,
        None,
    )
    rows = await session.scalar(select(func.count()).select_from(MediaRef).where(MediaRef.urlKey == key))
    links = list(
        await session.scalars(select(MediaRefClaim.claimId).where(MediaRefClaim.mediaRefId == first.id))
    )
    assert (rows, links) == (1, [KUT_CLAIM])


async def test_only_visible_claims_are_illustrated(session: AsyncSession) -> None:
    store = store_for(session)
    hidden = uuid.uuid4()
    found = await store.claim_texts([KUT_CLAIM, hidden])
    assert [claim.claim_id for claim in found] == [KUT_CLAIM]
    assert found[0].text.startswith("Kut is made from jaggery or molasses")
    await session.execute(update(Claim).where(Claim.id == KUT_CLAIM).values(status="RETRACTED"))
    assert await store.claim_texts([KUT_CLAIM]) == []


async def test_a_stored_link_card_is_read_back_for_its_claim_but_not_as_an_inline_picture(
    session: AsyncSession,
) -> None:
    store = store_for(session)
    kept = (await store.keep([vam_card()]))[0]
    read = await store.stored([KUT_CLAIM, uuid.uuid4()])
    assert (kept.id, KUT_CLAIM, "TEXT") in [(p.media.id, p.claim_id, p.relevance) for p in read]
    assert {picture.claim_id for picture in read} == {KUT_CLAIM}
    assert kept.id not in {picture.media.id for picture in await stored_pictures(session, [KUT_CLAIM])}
