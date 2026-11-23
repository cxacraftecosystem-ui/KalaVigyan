import uuid
from collections.abc import AsyncIterator

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Source
from app.services.source_journals import JournalRead, StoredDoi, store_journals, unjournaled

from .testimony_seed import rolled_back_session

pytestmark = pytest.mark.db

BARE = uuid.uuid5(uuid.NAMESPACE_URL, "test-source-journals/bare")
NAMED = uuid.uuid5(uuid.NAMESPACE_URL, "test-source-journals/named")
BARE_DOI = "10.1000/kv.journal.bare"
NAMED_DOI = "10.1000/kv.journal.named"
JOURNAL = "Coloration Technology"


@pytest.fixture
async def session() -> AsyncIterator[AsyncSession]:
    async for opened in rolled_back_session():
        opened.add_all(
            [
                Source(id=BARE, kind="PAPER", title="Alizarin lakes on cotton", doi=BARE_DOI),
                Source(
                    id=NAMED,
                    kind="PAPER",
                    title="Indigo vats and lime",
                    doi=NAMED_DOI,
                    containerTitle="Dyes and Pigments",
                ),
            ]
        )
        await opened.flush()
        yield opened


async def test_a_stored_doi_without_a_journal_is_read_and_its_journal_stored(session: AsyncSession) -> None:
    listed = await unjournaled(session)
    assert StoredDoi(BARE, BARE_DOI) in listed
    assert NAMED not in {stored.id for stored in listed}
    reads = [JournalRead(BARE, BARE_DOI, JOURNAL), JournalRead(NAMED, NAMED_DOI, "Another Journal")]
    assert await store_journals(session, reads) == 1
    query = select(Source.id, Source.containerTitle).where(Source.id.in_([BARE, NAMED]))
    rows = dict((await session.execute(query)).tuples().all())
    assert rows == {BARE: JOURNAL, NAMED: "Dyes and Pigments"}
