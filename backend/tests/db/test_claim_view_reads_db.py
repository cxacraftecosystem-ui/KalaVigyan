from collections.abc import AsyncIterator

import pytest
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Claim, Source
from app.retrieval.citation_access import HELD_KEPT
from app.services.answer_events import cited_claims
from app.services.knowledge_api import craft_facts
from app.services.knowledge_view import claims_by_id
from app.services.section_blocks import KeptSentence, explainer_sentence

from .quote_visibility_seed import SLUG, Cite, fact, fact_text, key, seeded_session

pytestmark = pytest.mark.db

SITE = "https://kalavigyan.example"
BOOK, PAGE = key("reads-book"), key("reads-page")
DIFFERING, AGREEING, HELD = key("reads-differing"), key("reads-agreeing"), key("reads-held")
BOOK_QUOTE = "the madder bath is boiled for an hour"
LOST_QUOTE = "a sentence the page no longer holds anywhere"


@pytest.fixture
async def session() -> AsyncIterator[AsyncSession]:
    async for opened in seeded_session():
        opened.add_all(
            [
                Source(id=BOOK, kind="BOOK", title="A book on madder"),
                Source(id=PAGE, kind="WEB_PAGE", title="An open page on alum", licence="CC BY 4.0"),
            ]
        )
        await opened.flush()
        await fact(opened, DIFFERING, Cite(BOOK, BOOK_QUOTE))
        await fact(opened, AGREEING, Cite(BOOK, BOOK_QUOTE))
        await fact(opened, HELD, Cite(PAGE, LOST_QUOTE, check="FAIL"))
        await opened.execute(update(Claim).where(Claim.id == DIFFERING).values(sourcesDiffer=True))
        yield opened


async def test_a_stored_claim_whose_sources_differ_flags_the_sentence_that_cites_it(
    session: AsyncSession,
) -> None:
    views, sources = await claims_by_id(session, [DIFFERING, AGREEING])
    assert (views[DIFFERING].sources_differ, views[AGREEING].sources_differ) == (True, False)
    cited = cited_claims(list(views.values()), sources)
    differing = KeptSentence(fact_text(DIFFERING), (DIFFERING,), (), False)
    agreeing = KeptSentence(fact_text(AGREEING), (AGREEING,), (), False)
    flagged = explainer_sentence("s1.b1.1", differing, cited).model_dump(mode="json", by_alias=True)
    plain = explainer_sentence("s1.b1.2", agreeing, cited).model_dump(mode="json", by_alias=True)
    assert flagged["sourcesDiffer"] is True
    assert "sourcesDiffer" not in plain


async def test_a_reader_s_facts_leave_a_held_fact_out_and_a_contributor_s_keep_it_unquoted(
    session: AsyncSession,
) -> None:
    read = await craft_facts(session, SLUG, site=SITE)
    assert {found.id for found in read.facts} == {DIFFERING, AGREEING}
    kept = await craft_facts(session, SLUG, site=SITE, held=HELD_KEPT)
    assert {found.id for found in kept.facts} == {DIFFERING, AGREEING, HELD}
    (held,) = [found for found in kept.facts if found.id == HELD]
    assert [(cite.source_id, cite.quote) for cite in held.citations] == [(str(PAGE), None)]
