import uuid
from collections.abc import AsyncIterator
from datetime import timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AuditLog, Claim, ClaimSource, Craft, Source, SourceUpkeep
from app.research.open_work import task_key
from app.research.review_queue import FACTS
from app.services.claim_holds import (
    corroborated_claim,
    held_claim_ids,
    shown_held_ids,
    unheld_by_id,
    with_kept_verdicts,
)
from app.services.claim_holds_review import hold_evidence
from app.services.craft_page_records import craft_page_records
from app.services.open_work import subject_standings
from app.services.open_work_counts import Owners
from app.services.open_work_healing import subject_healing
from app.services.open_work_subjects import subject_by_key
from app.services.review_queue_select import QueueScope, pending_conditions
from app.services.upkeep_healing import CLAIMS_HELD, heal
from app.services.upkeep_links import rotten_source_ids
from app.services.upkeep_quotes import FAILING_RECHECK_AFTER, sources_due

from .claim_holds_seed import (
    ARCHIVED_ONLY,
    CHECKED,
    CRAFT,
    FAILING,
    HELD,
    HOST,
    ROTTEN_ONLY,
    SLUG,
    SOUND,
    SOURCES,
    held_session,
    quote_row,
)

pytestmark = pytest.mark.db

SITE = "https://kalavigyan.example"
MINE = (HELD, FAILING, SOUND, ROTTEN_ONLY, ARCHIVED_ONLY)


@pytest.fixture
async def session() -> AsyncIterator[AsyncSession]:
    async for opened in held_session():
        yield opened


async def test_a_fact_is_held_only_when_every_quote_fails(session: AsyncSession) -> None:
    assert await held_claim_ids(session, MINE) == frozenset({HELD})
    assert HELD in await shown_held_ids(session)
    corroborated = await session.scalars(select(Claim.id).where(Claim.id.in_(MINE), corroborated_claim()))
    assert set(corroborated.all()) == {FAILING}
    assert await unheld_by_id(session, {claim_id: str(claim_id) for claim_id in MINE}) == {
        claim_id: str(claim_id) for claim_id in MINE if claim_id != HELD
    }


async def test_a_held_fact_waits_in_the_facts_queue_with_the_failed_quotes(session: AsyncSession) -> None:
    conditions = pending_conditions(FACTS, QueueScope(viewer_id=uuid.uuid4()))
    queued = await session.scalars(select(Claim.id).where(Claim.id.in_(MINE), *conditions))
    assert set(queued.all()) == {HELD}
    evidence = await hold_evidence(session, MINE)
    assert set(evidence) == {HELD}
    check = evidence[HELD]
    assert (check.gate, check.passed, len(check.reasons)) == ("QUOTES", False, 2)
    assert {
        place for place in ("one", "two") for reason in check.reasons if f"{HOST}/{place}." in reason
    } == {
        "one",
        "two",
    }
    assert all(
        reason.startswith(f"The nightly re-check of {CHECKED.date().isoformat()}") for reason in check.reasons
    )


async def test_a_re_import_keeps_the_upkeep_s_later_verdict(session: AsyncSession) -> None:
    row = quote_row(HELD, "one", 0)
    planned = [
        {"id": row, "quoteCheck": "PASS", "checkedAt": CHECKED - timedelta(days=30), "locator": "p. 2"}
    ]
    kept = await with_kept_verdicts(session, planned)
    assert kept == [{"id": row, "quoteCheck": "FAIL", "checkedAt": CHECKED, "locator": "p. 2"}]
    newer = [{"id": row, "quoteCheck": "PASS", "checkedAt": CHECKED + timedelta(days=1)}]
    assert await with_kept_verdicts(session, newer) == newer


async def test_healing_work_lists_held_failing_and_rotting_facts(session: AsyncSession) -> None:
    rotten = set((await session.scalars(rotten_source_ids())).all())
    assert SOURCES["rotten"] in rotten and SOURCES["archived"] not in rotten
    healing = (await subject_healing(session, Owners(crafts=(CRAFT,), categories=())))[CRAFT]
    assert healing.held["CHEMISTRY"].ids == (str(HELD),)
    assert healing.failing["CHEMISTRY"].ids == (str(FAILING),)
    assert healing.rotten_facts.ids == (str(ROTTEN_ONLY),)
    assert healing.rotten_sources.ids == (str(SOURCES["rotten"]),)
    subject = await subject_by_key(session, "craft", SLUG)
    (standing,) = await subject_standings(session, [subject], site=SITE)
    tasks = {task.key: task for task in standing.healing}
    resource = task_key("RESOURCE_FACT", standing.subject, "CHEMISTRY")
    assert list(tasks) == [
        resource,
        task_key("CORROBORATE_FACT", standing.subject, "CHEMISTRY"),
        task_key("FIND_ANOTHER_SOURCE", standing.subject),
    ]
    assert tasks[resource].fact_ids == [HELD] and tasks[resource].count == 1
    assert standing.fields.get("CHEMISTRY") is not None and standing.fields["CHEMISTRY"].facts == 4


async def test_the_nightly_healing_records_holds_and_attaches_archives(session: AsyncSession) -> None:
    report = await heal(session, before=frozenset({SOUND}))
    assert str(HELD) in report.held and str(SOUND) in report.lifted
    assert report.links.rotten >= 1 and str(SOURCES["archived"]) in report.links.attached
    archived = await session.get(Source, SOURCES["archived"], populate_existing=True)
    assert archived is not None
    assert (
        archived.externalIds["archivedUrl"] == f"https://web.archive.org/web/20260920000000/{HOST}/archived"
    )
    logged = await session.scalars(select(AuditLog.detail).where(AuditLog.action == CLAIMS_HELD))
    assert any(str(HELD) in (detail or {}).get("claimIds", []) for detail in logged.all())
    rotten = set((await session.scalars(rotten_source_ids())).all())
    assert SOURCES["archived"] not in rotten


async def test_a_quote_found_again_lifts_the_hold(session: AsyncSession) -> None:
    row = await session.get(ClaimSource, quote_row(HELD, "two", 0))
    assert row is not None
    row.quoteCheck = "PASS"
    await session.flush()
    assert await held_claim_ids(session, [HELD]) == frozenset()


async def test_a_failing_source_is_checked_again_after_a_week(session: AsyncSession) -> None:
    session.add(SourceUpkeep(sourceId=SOURCES["two"], checkedAt=CHECKED, outcome="FETCHED"))
    await session.flush()
    soon = {
        due.source_id for due in await sources_due(session, now=CHECKED + timedelta(days=3), limit=100_000)
    }
    later = {
        due.source_id for due in await sources_due(session, now=CHECKED + timedelta(days=8), limit=100_000)
    }
    assert SOURCES["two"] not in soon and SOURCES["rotten"] not in soon
    assert SOURCES["two"] in later and SOURCES["rotten"] in later
    assert timedelta(days=7) == FAILING_RECHECK_AFTER


async def test_a_held_fact_leaves_the_craft_page(session: AsyncSession) -> None:
    craft = await session.get(Craft, CRAFT)
    assert craft is not None
    records = await craft_page_records(session, craft)
    shown = {view.id for view in records.views}
    assert HELD not in shown and {FAILING, SOUND} <= shown
