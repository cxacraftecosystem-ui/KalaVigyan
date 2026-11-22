import uuid
from collections.abc import AsyncIterator, Sequence
from datetime import UTC, datetime
from typing import Any

import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_engine, get_session
from app.core.deps import get_current_user, get_optional_user
from app.main import app
from app.models import Claim, ClaimSource, Craft, User
from app.research.retrieval import EVERY_CHUNK_ACLS, OPEN_CHUNK_ACLS
from app.services.claim_seed import seed_id
from app.services.craft_process import process_records
from app.services.shared_term_crafts import refresh_shared_terms
from app.services.term_store import SqlTermStore
from app.services.term_summaries import StoredTermLookup, TermLookup

from ..answering.fakes import translation
from ..readers import sign_in_as
from ..terms.fakes import CHECKED_AT, FakeResearch
from .closed_quotes import (
    CLOSED_QUOTE,
    OPEN_SOURCE,
    RESTRICTED_CHUNK_QUOTE,
    RESTRICTED_SOURCE_QUOTE,
    quote_closed,
    quote_restricted,
    store_closed_sources,
)

pytestmark = pytest.mark.db

AJRAKH = "Kutch-Ajrakh"
BAGRU = "Bagru-Hand-Block-Print"
ALUM_SENTENCE = "Alum is used as a mordant to fasten the colours."
ALUM_CONCEPT = seed_id("concept", "ie:ajrakh.material.alum")
KUT_CLAIM = uuid.UUID("c407fde1-3c40-5c81-8a5e-320317aacf9d")
CLOSED_ONLY = "Alum from the closed monograph brightens the madder red."
GUARDED = "Alum is a guarded family recipe of one printing house."
WITHDRAWN = "Alum was once thought to dull the indigo vat."
PAGE = f"/api/crafts/{AJRAKH}/page"
SHARED_ALUM = f"/api/shared-science/alum?craft={AJRAKH}"
CLAIM_READS = (
    PAGE,
    f"/api/crafts/{AJRAKH}/shared-science",
    SHARED_ALUM,
    f"/api/compare?crafts={AJRAKH}&crafts={BAGRU}&facets=MATERIALS",
)
NEVER_SHOWN = (RESTRICTED_CHUNK_QUOTE, RESTRICTED_SOURCE_QUOTE, GUARDED, WITHDRAWN)
NOT_FOR_STUDENTS = (CLOSED_QUOTE, CLOSED_ONLY, *NEVER_SHOWN)
STUDENT = User(id=uuid.uuid4(), name="Asha", email="asha@example.com", role="STUDENT")
RESEARCHER = User(id=uuid.uuid4(), name="Ravi", email="ravi@example.com", role="RESEARCHER")


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


async def hide_material(session: AsyncSession) -> None:
    await store_closed_sources(session)
    alum = (
        await session.execute(
            select(Claim.id).where(Claim.subjectId == ALUM_CONCEPT, Claim.text == ALUM_SENTENCE)
        )
    ).scalar_one()
    craft = (await session.execute(select(Craft).where(Craft.slug == AJRAKH))).scalar_one()
    processed = await process_records(session, craft, acls=EVERY_CHUNK_ACLS)
    closed_only = await alum_claim(session, CLOSED_ONLY)
    await quote_closed(session, [alum, KUT_CLAIM, closed_only, *processed.claims])
    await quote_restricted(session, alum)
    await quote_restricted(session, KUT_CLAIM)
    guarded = await alum_claim(session, GUARDED, sensitivity="RESTRICTED")
    withdrawn = await alum_claim(session, WITHDRAWN, status="WITHDRAWN")
    session.add_all(
        ClaimSource(claimId=claim_id, sourceId=OPEN_SOURCE, quote=text)
        for claim_id, text in ((guarded, GUARDED), (withdrawn, WITHDRAWN))
    )
    await session.flush()
    await refresh_shared_terms(session, now=datetime.now(UTC))


async def alum_claim(session: AsyncSession, text: str, **fields: Any) -> uuid.UUID:
    claim = Claim(
        id=uuid.uuid4(),
        subjectType="CONCEPT",
        subjectId=ALUM_CONCEPT,
        predicate="states",
        text=text,
        evidenceLevel="PROVISIONAL",
        origin="LIVE_RESEARCH",
        **fields,
    )
    session.add(claim)
    await session.flush()
    return claim.id


async def read(session: AsyncSession, path: str, reader: User | None) -> httpx.Response:
    async def this_session() -> AsyncIterator[Any]:
        yield session

    app.dependency_overrides[get_session] = this_session
    if reader is not None:
        sign_in_as(app, lambda: reader)
    try:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            return await client.get(path)
    finally:
        for dependency in (get_session, get_current_user, get_optional_user):
            app.dependency_overrides.pop(dependency, None)


def shown(text: str, among: Sequence[str]) -> list[str]:
    return [one for one in among if one in text]


def term_store(session: AsyncSession, acls: Sequence[str]) -> SqlTermStore:
    def sessions() -> AsyncSession:
        return AsyncSession(bind=session.bind, expire_on_commit=False, autoflush=False)

    return SqlTermStore(sessions, acls=acls)


def term_lookup(store: SqlTermStore) -> TermLookup:
    return TermLookup(
        store=store, research=FakeResearch(None), translation=translation(), clock=lambda: CHECKED_AT
    )


async def test_an_anonymous_reader_gets_a_student_s_reads_and_no_closed_restricted_or_hidden_text(
    session: AsyncSession,
) -> None:
    await hide_material(session)
    for path in CLAIM_READS:
        anonymous = await read(session, path, None)
        student = await read(session, path, STUDENT)
        assert (anonymous.status_code, student.status_code) == (200, 200), path
        assert anonymous.json() == student.json(), path
        assert shown(anonymous.text, NOT_FOR_STUDENTS) == [], path


async def test_a_researcher_still_reads_the_closed_quotes_and_never_the_restricted_text(
    session: AsyncSession,
) -> None:
    await hide_material(session)
    page = await read(session, PAGE, RESEARCHER)
    alum = await read(session, SHARED_ALUM, RESEARCHER)
    assert (page.status_code, alum.status_code) == (200, 200)
    assert shown(page.text, (CLOSED_QUOTE, CLOSED_ONLY)) == [CLOSED_QUOTE, CLOSED_ONLY]
    assert CLOSED_QUOTE in alum.text
    assert shown(page.text, NEVER_SHOWN) == shown(alum.text, NEVER_SHOWN) == []


async def test_a_term_summary_quotes_a_closed_chunk_only_to_a_reader_who_may_read_it(
    session: AsyncSession,
) -> None:
    await hide_material(session)
    researcher = await term_lookup(term_store(session, EVERY_CHUNK_ACLS)).summary("kut", "en")
    assert shown(researcher.model_dump_json(), (CLOSED_QUOTE, *NEVER_SHOWN)) == [CLOSED_QUOTE]
    anonymous = await StoredTermLookup(term_store(session, OPEN_CHUNK_ACLS)).summary("kut", "en")
    student = await term_lookup(term_store(session, OPEN_CHUNK_ACLS)).summary("kut", "en")
    assert anonymous == student
    assert shown(anonymous.model_dump_json(), NOT_FOR_STUDENTS) == []
    again = await StoredTermLookup(term_store(session, OPEN_CHUNK_ACLS)).summary("kut", "en")
    assert again.checked_at == anonymous.checked_at
