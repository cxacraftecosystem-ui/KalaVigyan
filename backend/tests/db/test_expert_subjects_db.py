import pytest

from app.models import Concept, Term, TermConcept
from app.services.expert_subjects import linked_subjects
from tests.db.field_voices_rows import ajrakh, rolled_back

pytestmark = pytest.mark.db


async def test_two_concepts_one_glossary_term_links_are_one_subject_and_an_unlinked_one_is_not() -> None:
    async with rolled_back() as session:
        craft = await ajrakh(session)
        alum, fitkari, lime = (
            Concept(craftId=craft.id, type="MATERIAL", name=f"Subject test {name}")
            for name in ("alum", "fitkari", "lime")
        )
        term = Term(key="subject-test-alum", label="Subject test alum")
        other = Term(key="subject-test-lime", label="Subject test lime")
        session.add_all([alum, fitkari, lime, term, other])
        await session.flush()
        session.add_all(
            [
                TermConcept(termId=term.id, conceptId=alum.id),
                TermConcept(termId=term.id, conceptId=fitkari.id),
                TermConcept(termId=other.id, conceptId=lime.id),
            ]
        )
        await session.flush()
        subjects = await linked_subjects(session, [alum.id, fitkari.id, lime.id])
        assert subjects.same(alum.id, fitkari.id)
        assert not subjects.same(alum.id, lime.id)
        assert dict(subjects.terms) == {
            alum.id: frozenset({term.id}),
            fitkari.id: frozenset({term.id}),
            lime.id: frozenset({other.id}),
        }
