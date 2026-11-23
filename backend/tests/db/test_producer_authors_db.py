import uuid
from collections.abc import AsyncIterator

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_engine
from app.models import Source
from app.services.source_titles import ProducerAuthored, producer_authored

pytestmark = pytest.mark.db

STUDY_URL = "https://www.jeb.co.in/journal_issues/200701_jan07/paper_22.pdf"
TITLE = "Mutagenicity assessment of textile dyes from Sanganer (Rajasthan)"


def key(name: str) -> uuid.UUID:
    return uuid.uuid5(uuid.NAMESPACE_URL, f"test-producer-authors/{name}")


@pytest.fixture
async def session() -> AsyncIterator[AsyncSession]:
    async with get_engine().connect() as connection:
        transaction = await connection.begin()
        try:
            opened = AsyncSession(bind=connection, expire_on_commit=False, autoflush=False)
            yield opened
            await opened.close()
        finally:
            await transaction.rollback()


async def test_the_report_lists_a_source_whose_authors_are_its_file_s_producer(session: AsyncSession) -> None:
    session.add_all(
        [
            Source(id=key("sys"), kind="OTHER", title=TITLE, url=STUDY_URL, authors=["sys"]),
            Source(id=key("word"), kind="OTHER", title="A dye report", authors=["Microsoft Office User"]),
            Source(id=key("named"), kind="PAPER", title=TITLE, authors=["Nupur Mathur", "Pradeep Bhatnagar"]),
            Source(id=key("none"), kind="WEB_PAGE", title="A page on Sanganer printing"),
        ]
    )
    await session.flush()
    listed = {row.id: row for row in await producer_authored(session)}
    assert listed[key("sys")] == ProducerAuthored(key("sys"), TITLE, STUDY_URL, ("sys",), 0)
    assert listed[key("word")].as_dict() == {
        "id": str(key("word")),
        "title": "A dye report",
        "url": None,
        "authors": ["Microsoft Office User"],
        "citations": 0,
    }
    assert key("named") not in listed and key("none") not in listed
