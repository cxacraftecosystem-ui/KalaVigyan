from collections.abc import AsyncIterator

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Claim, Craft, Source
from app.research.retrieval import EVERY_CHUNK_ACLS, OPEN_CHUNK_ACLS, RESEARCHER_CHUNK_ACL
from app.retrieval.citation_access import HELD_KEPT
from app.retrieval.indexing import replace_source_chunks
from app.retrieval.statements import CraftScope, claim_conditions
from app.services.knowledge_view import claims_by_id, claims_for, contributor_claims_for

from .quote_visibility_seed import CRAFT, Cite, fact, key, seeded_session

pytestmark = pytest.mark.db

CLOSED_PAGE, OPEN_PAGE, BOOK = key("closed-page"), key("open-page"), key("book")
UNLINKED, UNQUOTED, BOOK_QUOTED = key("unlinked"), key("unquoted"), key("book-quoted")
HELD, FAILING = key("held"), key("failing")
CLOSED_TEXT = "The dye house keeps its own measures of alum and madder for every bath."
CLOSED_QUOTE = (
    "Alum is weighed by the master dyer on the morning of the bath, and the madder is ground the night "
    "before, so that the colour that rises in the vat is the colour the printer asked for when the cloth "
    "was first stamped with the resist and laid out to dry in the courtyard sun."
)
OPEN_TEXT = "Alum fixes the madder red on cotton in the second bath of the day."
OPEN_QUOTE = "Alum fixes the madder red on cotton"
BOOK_QUOTE = "the madder bath is boiled for an hour"
LOST_QUOTE = "a sentence the page no longer holds anywhere"
SCOPE = CraftScope(craft_id=CRAFT, sub_category_id=None)


@pytest.fixture
async def session() -> AsyncIterator[AsyncSession]:
    async for opened in seeded_session():
        await _sources(opened)
        await fact(opened, UNLINKED, Cite(CLOSED_PAGE, CLOSED_QUOTE))
        await fact(opened, UNQUOTED, Cite(CLOSED_PAGE, None))
        await fact(opened, BOOK_QUOTED, Cite(BOOK, BOOK_QUOTE))
        await fact(opened, HELD, Cite(OPEN_PAGE, LOST_QUOTE, check="FAIL"))
        await fact(opened, FAILING, Cite(OPEN_PAGE, OPEN_QUOTE), Cite(BOOK, LOST_QUOTE, check="FAIL"))
        yield opened


async def _sources(session: AsyncSession) -> None:
    session.add_all(
        [
            Source(
                id=CLOSED_PAGE,
                kind="WEB_PAGE",
                title="A dye house's page",
                licence="All rights reserved",
                origin="LIVE_RESEARCH",
            ),
            Source(id=OPEN_PAGE, kind="WEB_PAGE", title="An open page on alum", licence="CC BY 4.0"),
            Source(id=BOOK, kind="BOOK", title="A book on madder"),
        ]
    )
    await session.flush()
    await replace_source_chunks(session, CLOSED_PAGE, CLOSED_TEXT, acl=RESEARCHER_CHUNK_ACL)
    await replace_source_chunks(session, OPEN_PAGE, OPEN_TEXT)


async def test_a_quote_no_passage_holds_takes_the_access_of_its_pages_passages_and_its_fact_stays(
    session: AsyncSession,
) -> None:
    public, sources = await claims_by_id(session, [UNLINKED, UNQUOTED, BOOK_QUOTED], acls=OPEN_CHUNK_ACLS)
    assert set(public) == {UNLINKED, UNQUOTED, BOOK_QUOTED}
    assert [(c["sourceId"], c["quote"], c["evidence"]) for c in public[UNLINKED].citations] == [
        (str(CLOSED_PAGE), None, "INFERRED")
    ]
    assert CLOSED_PAGE in sources
    assert [(c["quote"], c["evidence"]) for c in public[UNQUOTED].citations] == [(None, "INFERRED")]
    assert [(c["quote"], c["evidence"]) for c in public[BOOK_QUOTED].citations] == [(BOOK_QUOTE, "QUOTED")]
    researcher, _ = await claims_by_id(session, [UNLINKED], acls=EVERY_CHUNK_ACLS)
    assert [c["quote"] for c in researcher[UNLINKED].citations] == [CLOSED_QUOTE]


async def test_a_held_fact_leaves_search_and_views_but_a_contributor_still_reads_it_unquoted(
    session: AsyncSession,
) -> None:
    searched = set(await session.scalars(select(Claim.id).where(*claim_conditions(SCOPE, mode="HYBRID"))))
    assert HELD not in searched and FAILING in searched
    kept = set(
        await session.scalars(select(Claim.id).where(*claim_conditions(SCOPE, mode="HYBRID", held=HELD_KEPT)))
    )
    assert HELD in kept
    craft = await session.get(Craft, CRAFT)
    assert craft is not None
    shown, _ = await claims_for(session, craft, mode="HYBRID", acls=EVERY_CHUNK_ACLS)
    assert {view.id for view in shown} == {UNLINKED, UNQUOTED, BOOK_QUOTED, FAILING}
    by_id, _ = await claims_by_id(session, [HELD, FAILING], acls=EVERY_CHUNK_ACLS)
    assert set(by_id) == {FAILING}
    read, _ = await contributor_claims_for(session, craft, mode="HYBRID", acls=EVERY_CHUNK_ACLS)
    (held,) = [view for view in read if view.id == HELD]
    assert [(c["sourceId"], c["quote"], c["evidence"]) for c in held.citations] == [
        (str(OPEN_PAGE), None, "INFERRED")
    ]


async def test_a_failed_quote_is_never_shown_as_verbatim(session: AsyncSession) -> None:
    views, _ = await claims_by_id(session, [FAILING], acls=OPEN_CHUNK_ACLS)
    assert [(c["sourceId"], c["quote"], c["evidence"]) for c in views[FAILING].citations] == [
        (str(OPEN_PAGE), OPEN_QUOTE, "QUOTED"),
        (str(BOOK), None, "INFERRED"),
    ]
