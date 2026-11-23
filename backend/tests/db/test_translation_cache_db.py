import uuid
from collections.abc import AsyncIterator

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Claim, ClaimTranslation
from app.services.translation_cache import SqlTranslationCache, checked_source_sha256, source_sha256

from .write_back_seed import ALUM_CONCEPT, key, seeded_session

pytestmark = pytest.mark.db

ENGLISH = "Alum is the mordant that binds alizarin to cotton."
CHANGED = "Alum is the mordant that binds alizarin to cotton in Zelvar."
HINDI = "फिटकरी वह मॉर्डेंट है जो एलिज़रिन को कपास से बाँधती है।"
HINDI_CHANGED = "फिटकरी वह मॉर्डेंट है जो ज़ेलवार में एलिज़रिन को कपास से बाँधती है।"


@pytest.fixture
async def session() -> AsyncIterator[AsyncSession]:
    async for opened in seeded_session():
        yield opened


def cache_for(session: AsyncSession) -> SqlTranslationCache:
    def sessions() -> AsyncSession:
        return AsyncSession(bind=session.bind, expire_on_commit=False, autoflush=False)

    return SqlTranslationCache(sessions)


async def translated_claim(session: AsyncSession) -> uuid.UUID:
    claim_id = key("translated-claim")
    session.add(
        Claim(
            id=claim_id,
            subjectType="CONCEPT",
            subjectId=ALUM_CONCEPT,
            predicate="states",
            text=ENGLISH,
            evidenceLevel="VERIFIED",
            origin="IMPORT",
        )
    )
    await session.flush()
    return claim_id


async def test_a_claim_translation_is_found_again_for_the_same_text_and_language(
    session: AsyncSession,
) -> None:
    claim_id = await translated_claim(session)
    cache = cache_for(session)
    await cache.remember("hi", {claim_id: (ENGLISH, HINDI)})
    assert await cache.known("hi", {claim_id: ENGLISH}) == {claim_id: HINDI}
    assert await cache.known("ta", {claim_id: ENGLISH}) == {}
    stored = (
        await session.execute(select(ClaimTranslation).where(ClaimTranslation.claimId == claim_id))
    ).scalar_one()
    assert (stored.language, stored.sourceSha256) == ("hi", checked_source_sha256(ENGLISH))


async def test_a_translation_cached_before_the_read_back_check_is_made_again(session: AsyncSession) -> None:
    claim_id = await translated_claim(session)
    session.add(
        ClaimTranslation(claimId=claim_id, language="hi", sourceSha256=source_sha256(ENGLISH), text=HINDI)
    )
    await session.flush()
    cache = cache_for(session)
    assert await cache.known("hi", {claim_id: ENGLISH}) == {}
    await cache.remember("hi", {claim_id: (ENGLISH, HINDI_CHANGED)})
    assert await cache.known("hi", {claim_id: ENGLISH}) == {claim_id: HINDI_CHANGED}


async def test_a_changed_claim_text_misses_the_cache_and_is_replaced(session: AsyncSession) -> None:
    claim_id = await translated_claim(session)
    cache = cache_for(session)
    await cache.remember("hi", {claim_id: (ENGLISH, HINDI)})
    assert await cache.known("hi", {claim_id: CHANGED}) == {}
    await cache.remember("hi", {claim_id: (CHANGED, HINDI_CHANGED)})
    assert await cache.known("hi", {claim_id: CHANGED}) == {claim_id: HINDI_CHANGED}
    count = select(func.count()).select_from(ClaimTranslation).where(ClaimTranslation.claimId == claim_id)
    assert (await session.execute(count)).scalar_one() == 1


def test_the_source_hash_is_the_sha256_of_the_utf8_text() -> None:
    assert source_sha256("abc") == "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"


def test_the_cache_key_is_the_hash_of_the_checks_edition_and_the_text() -> None:
    assert checked_source_sha256("abc") == source_sha256("read-back-1\nabc")
    assert checked_source_sha256("abc") != source_sha256("abc")
