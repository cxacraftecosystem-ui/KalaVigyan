import uuid
from collections.abc import AsyncIterator

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_engine
from app.media.claim_set import claim_set
from app.media.rows import stage_claims
from app.models import Claim, ClaimSource, Concept, Craft, Process, ProcessStage, Source
from app.research.retrieval import EVERY_CHUNK_ACLS, OPEN_CHUNK_ACLS, RESEARCHER_CHUNK_ACL
from app.retrieval.indexing import replace_source_chunks

pytestmark = pytest.mark.db


def key(name: str) -> uuid.UUID:
    return uuid.uuid5(uuid.NAMESPACE_URL, f"test-media-citation-access/{name}")


CRAFT, CONCEPT, PROCESS, STAGE = key("craft"), key("concept"), key("process"), key("stage")
CLOSED_PAGE, BOOK = key("closed-page"), key("book")
CLOSED, OPEN = key("closed-quote"), key("open-quote")
CLOSED_TEXT = "The dye house keeps its own measures of alum and madder for every bath."
CLOSED_QUOTE = "Alum is weighed by the master dyer on the morning of the bath"
BOOK_QUOTE = "the madder bath is boiled for an hour"


@pytest.fixture
async def session() -> AsyncIterator[AsyncSession]:
    async with get_engine().connect() as connection:
        transaction = await connection.begin()
        try:
            opened = AsyncSession(bind=connection, expire_on_commit=False, autoflush=False)
            await _stage(opened)
            await _sources(opened)
            await _cited(opened, CLOSED, CLOSED_PAGE, CLOSED_QUOTE)
            await _cited(opened, OPEN, BOOK, BOOK_QUOTE)
            yield opened
            await opened.close()
        finally:
            await transaction.rollback()


async def _stage(session: AsyncSession) -> None:
    session.add(Craft(id=CRAFT, slug="Media-Citation-Access-Craft", name="Media Citation Access Craft"))
    await session.flush()
    session.add_all(
        [
            Concept(id=CONCEPT, craftId=CRAFT, type="PROCESS_STAGE", name="Alum printing"),
            Process(id=PROCESS, craftId=CRAFT, name="Printing"),
        ]
    )
    await session.flush()
    session.add(ProcessStage(id=STAGE, processId=PROCESS, ordinal=6, conceptId=CONCEPT, name="Alum printing"))
    await session.flush()


async def _sources(session: AsyncSession) -> None:
    session.add_all(
        [
            Source(
                id=CLOSED_PAGE, kind="WEB_PAGE", title="A dye house's page", licence="All rights reserved"
            ),
            Source(id=BOOK, kind="BOOK", title="A book on madder"),
        ]
    )
    await session.flush()
    await replace_source_chunks(session, CLOSED_PAGE, CLOSED_TEXT, acl=RESEARCHER_CHUNK_ACL)


async def _cited(session: AsyncSession, claim_id: uuid.UUID, source_id: uuid.UUID, quote: str) -> None:
    session.add(
        Claim(
            id=claim_id,
            subjectType="CONCEPT",
            subjectId=CONCEPT,
            predicate="PROCESS_STAGE",
            text=f"Alum printing, as fact {claim_id.hex[:8]} says.",
            evidenceLevel="PROVISIONAL",
            origin="IMPORT",
            status="APPROVED",
        )
    )
    await session.flush()
    session.add(
        ClaimSource(claimId=claim_id, sourceId=source_id, chunkId=None, quote=quote, quoteCheck="PASS")
    )
    await session.flush()


async def test_a_closed_licence_quote_with_no_passage_is_left_out_of_a_readers_media_bundle(
    session: AsyncSession,
) -> None:
    found = (await stage_claims(session, [STAGE]))[STAGE]
    assert {claim.id: [cite.chunk_acl for cite in claim.citations] for claim in found} == {
        CLOSED: [RESEARCHER_CHUNK_ACL],
        OPEN: ["PUBLIC"],
    }
    assert [claim.id for claim in claim_set(found, acls=OPEN_CHUNK_ACLS)] == [OPEN]
    assert {claim.id for claim in claim_set(found, acls=EVERY_CHUNK_ACLS)} == {CLOSED, OPEN}
