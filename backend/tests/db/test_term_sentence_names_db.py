import uuid
from collections.abc import AsyncIterator

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Claim, Concept, Term, TermConcept
from app.services.term_sentence_names import fill_sentence_names

from .testimony_seed import rolled_back_session

pytestmark = pytest.mark.db


def key(name: str) -> uuid.UUID:
    return uuid.uuid5(uuid.NAMESPACE_URL, f"test-term-sentence-names/{name}")


def claim(name: str, concept_id: uuid.UUID, text: str) -> Claim:
    return Claim(
        id=key(f"claim/{name}"),
        subjectType="CONCEPT",
        subjectId=concept_id,
        predicate="states",
        text=text,
        evidenceLevel="PROVISIONAL",
        origin="IMPORT",
    )


@pytest.fixture
async def session() -> AsyncIterator[AsyncSession]:
    async for opened in rolled_back_session():
        alum, kutch = key("concept/alum"), key("concept/kutch")
        opened.add_all(
            [
                Concept(id=alum, type="MATERIAL", name="Alum"),
                Concept(id=kutch, type="TRADITION", name="Kutch"),
                Term(id=key("term/alum"), key="test-sentence-alum", label="Alum"),
                Term(id=key("term/kutch"), key="test-sentence-kutch", label="Kutch"),
                Term(id=key("term/named"), key="test-sentence-named", label="Iron", sentenceName="Iron"),
            ]
        )
        await opened.flush()
        opened.add_all(
            [
                TermConcept(termId=key("term/alum"), conceptId=alum),
                TermConcept(termId=key("term/kutch"), conceptId=kutch),
                TermConcept(termId=key("term/named"), conceptId=alum),
                claim("alum", alum, "Printers boil the cloth with alum and madder."),
                claim("kutch", kutch, "Kutch is dry for most of the year."),
            ]
        )
        await opened.flush()
        yield opened


async def test_a_term_s_sentence_name_is_read_from_its_concept_s_claims(session: AsyncSession) -> None:
    await fill_sentence_names(session)
    rows = await session.execute(
        select(Term.key, Term.sentenceName).where(
            Term.id.in_([key("term/alum"), key("term/kutch"), key("term/named")])
        )
    )
    assert dict(rows.tuples().all()) == {
        "test-sentence-alum": "alum",
        "test-sentence-kutch": None,
        "test-sentence-named": "Iron",
    }
