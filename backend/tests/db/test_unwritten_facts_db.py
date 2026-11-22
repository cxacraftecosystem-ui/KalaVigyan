import uuid
from collections.abc import AsyncIterator

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Claim, ClaimSource
from app.services.monograph_generated import generated_document

from .page_documents_seed import ALUM, CRAFT_SLUG, CRAFT_TEXT, seed
from .testimony_seed import rolled_back_session

pytestmark = pytest.mark.db

PAPER = uuid.UUID("9d0c0000-0000-4000-8000-000000000007")
DYES = uuid.uuid5(uuid.NAMESPACE_URL, "test-unwritten-facts/dyes")
RESTRICTED = uuid.uuid5(uuid.NAMESPACE_URL, "test-unwritten-facts/restricted")
DYES_TEXT = "Most textile dyes used by the printers have not been evaluated for their health impact."
RESTRICTED_TEXT = "A guarded recipe keeps its mordant measure from readers."
FAMILY_TEXT = "Printers across India print with carved wooden blocks."


@pytest.fixture
async def session() -> AsyncIterator[AsyncSession]:
    async for opened in rolled_back_session():
        await seed(opened)
        for claim_id, text, sensitivity in (
            (DYES, DYES_TEXT, "OPEN"),
            (RESTRICTED, RESTRICTED_TEXT, "RESTRICTED"),
        ):
            opened.add(
                Claim(
                    id=claim_id,
                    subjectType="CONCEPT",
                    subjectId=ALUM,
                    predicate="states",
                    text=text,
                    evidenceLevel="PROVISIONAL",
                    origin="CONTRIBUTION",
                    field="HEALTH",
                    sensitivity=sensitivity,
                )
            )
            await opened.flush()
            opened.add(
                ClaimSource(claimId=claim_id, sourceId=PAPER, quote=None, locator="p. 4", quoteCheck="NA")
            )
        await opened.flush()
        yield opened


def units_with(document: object, text: str) -> list[object]:
    return [unit for unit in document.content.units.values() if text in str(unit.nodes)]


async def test_a_field_with_no_section_lists_its_facts_in_its_chapter_under_its_heading(
    session: AsyncSession,
) -> None:
    document = await generated_document(session, "craft", CRAFT_SLUG)
    assert document is not None
    (fact,) = units_with(document, DYES_TEXT[:40])
    assert (fact.tag, fact.chapter, fact.field, fact.claim_ids) == ("li", "made", "HEALTH", [str(DYES)])
    refs = [entry.ref for entry in document.content.layout if entry.chapter == "made"]
    heading = next(ref for ref in refs if document.content.units[ref].nodes == ["Health and safety"])
    fact_ref = next(ref for ref, unit in document.content.units.items() if unit is fact)
    assert refs.index(heading) < refs.index(fact_ref)
    assert units_with(document, RESTRICTED_TEXT) == []
    assert document.version == 3


async def test_a_fact_no_section_cites_follows_its_field_s_section_and_a_cited_one_is_not_listed_again(
    session: AsyncSession,
) -> None:
    document = await generated_document(session, "craft", CRAFT_SLUG)
    assert document is not None
    (listed,) = units_with(document, FAMILY_TEXT)
    assert (listed.tag, listed.chapter, listed.field) == ("li", "chem", "CHEMISTRY")
    assert all(unit.tag != "li" for unit in units_with(document, CRAFT_TEXT[:20]))
