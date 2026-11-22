from collections.abc import AsyncIterator, Iterable
from datetime import UTC, datetime
from typing import Any

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ArticleSection
from app.research.review_switch import Placement
from app.services import knowledge_view, reader_facts
from app.services.candidate_store import FactSubject
from app.services.coverage import craft_coverage
from app.services.fact_proposals_readers import reader_place
from app.services.knowledge_api import craft_facts
from app.services.upkeep_hidden import count_hidden_facts, last_hidden_facts

from .reader_facts_seed import (
    CLOSED,
    CRAFT,
    FAILING,
    FIELD,
    HELD,
    HIDDEN,
    RESTRICTED,
    SECRET,
    SLUG,
    key,
    seeded_facts,
)

pytestmark = pytest.mark.db

SITE = "https://kalavigyan.example"
NOW = datetime(2026, 11, 22, 23, 45, tzinfo=UTC)
EVERY = (CLOSED, HELD, FAILING, HIDDEN, SECRET, RESTRICTED)
SEEN = {CLOSED, FAILING}
APPROVED_AT_ONCE = Placement("PUBLISHED", "APPROVED", approved_at_once=True, queued=False)
WAITING = Placement("WAITING", "DRAFT", approved_at_once=False, queued=True)
SUBJECT = FactSubject(kind="craft", name="Reader Facts Test Craft", slug=SLUG, craft_id=CRAFT)


@pytest.fixture
async def session() -> AsyncIterator[AsyncSession]:
    async for opened in seeded_facts():
        yield opened


async def test_coverage_get_facts_the_page_views_and_the_rule_count_the_same_facts_for_a_reader(
    session: AsyncSession,
) -> None:
    assert await reader_facts.shown_to_readers(session, EVERY) == SEEN
    views, _ = await knowledge_view.claims_by_id(session, EVERY)
    assert set(views) == SEEN
    read = await craft_facts(session, SLUG, site=SITE)
    assert {fact.id for fact in read.facts} == SEEN
    coverage = await craft_coverage(session, SLUG)
    assert coverage.count(FIELD).claims == len(SEEN) == 2


async def test_a_fact_from_a_closed_source_keeps_its_citation_without_its_words_and_a_failed_quote_is_dropped(
    session: AsyncSession,
) -> None:
    views, sources = await knowledge_view.claims_by_id(session, [CLOSED, FAILING])
    assert [(c["quote"], c["evidence"]) for c in views[CLOSED].citations] == [(None, "INFERRED")]
    assert views[CLOSED].readable_citation_ids() == frozenset()
    assert [c["quote"] is None for c in views[FAILING].citations] == [False, True]
    assert key("study") in sources


async def test_each_hidden_fact_is_named_by_the_rule_that_hides_it(session: AsyncSession) -> None:
    assert await reader_facts.hidden_reasons(session, EVERY) == {
        HELD: reader_facts.HELD,
        HIDDEN: reader_facts.HIDDEN_CONCEPT,
        SECRET: reader_facts.NO_SHOWN_SOURCE,
        RESTRICTED: reader_facts.RESTRICTED_FACT,
    }


async def test_the_nightly_count_names_each_reason_and_stores_the_report(session: AsyncSession) -> None:
    report = await count_hidden_facts(session, now=NOW)
    (craft,) = [found for found in report.crafts if found.slug == SLUG]
    assert craft.approved == 6 and craft.unexplained == ()
    assert dict(craft.hidden) == {
        "HELD": 1,
        "HIDDEN_CONCEPT": 1,
        "NO_SHOWN_SOURCE": 1,
        "RESTRICTED_FACT": 1,
    }
    stored = await last_hidden_facts(session)
    assert stored is not None and stored["countedAt"] == NOW.isoformat()
    assert {k: v for k, v in _row(stored, SLUG).items() if k in ("craft", "approved")} == {
        "craft": SLUG,
        "approved": 6,
    }


async def test_a_fact_the_rule_shows_but_a_view_leaves_out_fails_the_night(
    session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    real = knowledge_view.claims_by_id

    async def over_hiding(given: AsyncSession, claim_ids: Iterable[Any], **kwargs: Any) -> Any:
        views, sources = await real(given, claim_ids, **kwargs)
        return {claim_id: view for claim_id, view in views.items() if claim_id != CLOSED}, sources

    monkeypatch.setattr(reader_facts.knowledge_view, "claims_by_id", over_hiding)
    report = await count_hidden_facts(session, now=NOW)
    (craft,) = [found for found in report.crafts if found.slug == SLUG]
    assert craft.unexplained == (CLOSED,)
    assert report.unexplained >= 1 and SLUG in report.as_dict()["craftsUnexplained"]


async def test_the_reply_says_where_readers_see_a_fact_and_why_they_cannot_see_one(
    session: AsyncSession,
) -> None:
    shown = await reader_place(session, CLOSED, SUBJECT, FIELD, APPROVED_AT_ONCE)
    assert (shown.shown, shown.reason, shown.in_prose, shown.chapter) == (True, None, False, "made")
    assert shown.page_url is not None and shown.page_url.endswith(f"/crafts/{SLUG}")
    held = await reader_place(session, HELD, SUBJECT, FIELD, APPROVED_AT_ONCE)
    assert (held.shown, held.reason) == (False, "HELD")
    waiting = await reader_place(session, CLOSED, SUBJECT, FIELD, WAITING)
    assert (waiting.shown, waiting.reason) == (False, "WAITING")
    session.add(
        ArticleSection(
            craftId=CRAFT,
            field=FIELD,
            version=1,
            status="PUBLISHED",
            sentences=[{"text": "Most dyes were never tested.", "claimIds": [str(CLOSED)]}],
        )
    )
    await session.flush()
    written = await reader_place(session, CLOSED, SUBJECT, FIELD, APPROVED_AT_ONCE)
    assert (written.shown, written.in_prose, written.write_task) == (True, True, None)


def _row(stored: dict[str, Any], slug: str) -> dict[str, Any]:
    (row,) = [row for row in stored["perCraft"] if row["craft"] == slug]
    return dict(row)
