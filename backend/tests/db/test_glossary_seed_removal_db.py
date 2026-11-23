import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime

import pytest
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_engine
from app.models import Craft, CuratedCraft, Term, TermConcept, TermCraft, TermSummary
from app.services.claim_seed import seed_id
from app.services.term_glossary import seed_terms, term_id

pytestmark = pytest.mark.db

KUT_MATERIAL = seed_id("concept", "ie:ajrakh.material.kut-iron-paste")
CHECKED_AT = datetime(2026, 11, 23, 9, 0, tzinfo=UTC)


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


async def craft_id(session: AsyncSession, slug: str) -> uuid.UUID:
    found = await session.scalar(select(Craft.id).where(Craft.slug == slug))
    assert found is not None
    return found


async def uncurated_craft(session: AsyncSession) -> uuid.UUID:
    found = await session.scalar(
        select(Craft.id).where(Craft.id.not_in(select(CuratedCraft.craftId))).order_by(Craft.slug).limit(1)
    )
    assert found is not None
    return found


async def stale_term(session: AsyncSession, key: str, *, craft: uuid.UUID) -> uuid.UUID:
    term = term_id(key)
    session.add(Term(id=term, key=key, label=key.replace("-", " "), localNames=[], aliases=[]))
    await session.flush()
    session.add_all([TermCraft(termId=term, craftId=craft), TermConcept(termId=term, conceptId=KUT_MATERIAL)])
    await session.flush()
    return term


async def stored(session: AsyncSession, term: uuid.UUID) -> bool:
    return await session.scalar(select(Term.id).where(Term.id == term)) is not None


async def links_of(session: AsyncSession, term: uuid.UUID) -> tuple[list[uuid.UUID], list[uuid.UUID]]:
    crafts = list(await session.scalars(select(TermCraft.craftId).where(TermCraft.termId == term)))
    concepts = list(await session.scalars(select(TermConcept.conceptId).where(TermConcept.termId == term)))
    return crafts, concepts


async def test_a_seed_link_the_plan_no_longer_has_goes_and_its_unlinked_term_with_it(
    session: AsyncSession,
) -> None:
    uncurated = await uncurated_craft(session)
    gone = await stale_term(session, "retired-seed-word", craft=uncurated)
    summarised = await stale_term(session, "retired-but-read-word", craft=uncurated)
    session.add(
        TermSummary(
            termId=summarised, language="en", basis="STORED", payload={}, claimIds=[], checkedAt=CHECKED_AT
        )
    )
    await session.flush()
    counts = await seed_terms(session)
    assert counts["removedLinks"] >= 4
    assert counts["removedTerms"] >= 1
    assert not await stored(session, gone)
    assert await stored(session, summarised)
    assert await links_of(session, summarised) == ([], [])
    crafts, concepts = await links_of(session, term_id("kut"))
    assert await craft_id(session, "Kutch-Ajrakh") in crafts and KUT_MATERIAL in concepts


async def test_a_link_to_a_curated_craft_is_left_to_the_curated_import(session: AsyncSession) -> None:
    bagru = await craft_id(session, "Bagru-Hand-Block-Print")
    curated = {"craftId": bagru, "version": 1, "curatedAt": CHECKED_AT, "coverage": "THIN", "page": {}}
    await session.execute(insert(CuratedCraft).values(digest="a" * 64, **curated).on_conflict_do_nothing())
    kept = await stale_term(session, "curated-only-word", craft=bagru)
    await seed_terms(session)
    assert await links_of(session, kept) == ([bagru], [])
    assert await stored(session, kept)
