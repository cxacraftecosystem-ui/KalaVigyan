import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from app.research.knowledge_writes import ProposalReply
from app.research.page_revalidation import PageOwners
from app.research.review_queue import QueueDecision
from app.research.review_queue_parts import GateCheck
from app.research.write_back import WriteBackResult
from app.services import review_queue_refresh
from app.services.claim_holds import kept_verdict
from app.services.claim_holds_review import HOLD_MODEL, hold_reason, with_hold_evidence
from app.services.claim_pages import published_claims
from app.services.research_write_back import shown_results
from app.services.upkeep_healing import HealingReport, hold_changes
from app.services.upkeep_links import ROTTEN_AFTER_FAILURES, LinksReport

LATER = datetime(2026, 11, 20, 0, 30, tzinfo=UTC)
EARLIER = LATER - timedelta(days=45)
A, B, C = (uuid.UUID(int=n) for n in (1, 2, 3))


def check(gate: str, passed: bool, reason: str) -> GateCheck:
    return GateCheck(gate=gate, passed=passed, reasons=[reason], model=None, related=[])


def test_the_later_verdict_on_a_quote_wins_over_an_older_one() -> None:
    planned = {"id": A, "quoteCheck": "PASS", "checkedAt": EARLIER, "quote": "q"}
    assert kept_verdict(planned, {"quoteCheck": "FAIL", "checkedAt": LATER}) == {
        "id": A,
        "quoteCheck": "FAIL",
        "checkedAt": LATER,
        "quote": "q",
    }
    assert kept_verdict(planned, {"quoteCheck": "FAIL", "checkedAt": EARLIER - timedelta(days=1)}) == planned
    assert kept_verdict(planned, {"quoteCheck": "FAIL", "checkedAt": None}) == planned
    assert kept_verdict(planned, None) == planned
    unchecked = {"id": A, "quoteCheck": "PASS", "checkedAt": None}
    assert kept_verdict(unchecked, {"quoteCheck": "FAIL", "checkedAt": EARLIER})["quoteCheck"] == "FAIL"


def test_a_night_reports_what_it_held_and_what_it_lifted() -> None:
    held, lifted = hold_changes(frozenset({A, B}), frozenset({B, C}))
    assert (held, lifted) == ([C], [A])
    assert hold_changes(frozenset(), frozenset()) == ([], [])


def test_the_healing_report_names_each_count() -> None:
    report = HealingReport(
        held=[str(A)], lifted=[], held_now=4, corroborate=2, links=LinksReport(rotten=3, attached=["s"])
    )
    assert report.as_dict() == {
        "claimsHeld": 1,
        "claimsLifted": 0,
        "heldNow": 4,
        "corroborate": 2,
        "sourcesRotten": 3,
        "archivesAttached": 1,
        "pagesRefreshed": False,
    }
    assert ROTTEN_AFTER_FAILURES == 3


def test_a_hold_reason_names_the_day_the_quote_and_the_page() -> None:
    assert hold_reason("alum fixes the red", "https://example.org/a", LATER) == (
        'The nightly re-check of 2026-11-20 did not find the quote "alum fixes the red" in https://example.org/a.'
    )
    assert hold_reason("q", None, None) == (
        'The nightly re-check of an unrecorded day did not find the quote "q" in its source.'
    )


def test_the_hold_s_evidence_takes_the_place_of_the_stored_quotes_gate() -> None:
    stored = {A: [check("QUOTES", True, "found"), check("SOURCE", True, "graded C")]}
    held = check("QUOTES", False, "not found again")
    merged = with_hold_evidence(stored, {A: held, B: held})
    assert merged[A] == [held, check("SOURCE", True, "graded C")]
    assert merged[B] == [held]
    assert HOLD_MODEL == "nightly-upkeep"


def reply(outcome: str) -> ProposalReply:
    return ProposalReply(
        outcome=outcome,
        claim_id=A,
        status="APPROVED",
        level="PROVISIONAL",
        approved_at_once=False,
        in_review_queue=False,
        sources_differ=True,
        differs_from=[B],
        gates=[],
        message="m",
    )


def test_only_a_published_proposal_refreshes_its_pages_with_the_facts_it_differs_from() -> None:
    assert published_claims(reply("PUBLISHED")) == [A, B]
    assert published_claims(reply("WAITING")) == []
    assert published_claims(reply("REFUSED")) == []


def test_a_write_back_refreshes_its_live_claims_and_the_ones_it_re_found() -> None:
    key = "a" * 64
    created = WriteBackResult(dedupe_key=key, claim_id=A, created=True)
    found = WriteBackResult(dedupe_key=key, claim_id=B, created=False)
    assert shown_results([created, found], live=True) == [A, B]
    assert shown_results([created, found], live=False) == [B]


async def test_every_fact_decision_refreshes_the_fact_s_pages(monkeypatch: pytest.MonkeyPatch) -> None:
    asked: list[list[uuid.UUID]] = []
    sent: list[PageOwners] = []

    async def owners(session: Any, claim_ids: Any) -> PageOwners:
        asked.append(list(claim_ids))
        return PageOwners(crafts=("Kutch-Ajrakh",))

    async def refresh(found: PageOwners) -> bool:
        sent.append(found)
        return True

    monkeypatch.setattr(review_queue_refresh, "claim_owners", owners)
    monkeypatch.setattr(review_queue_refresh, "refresh_pages", refresh)
    for status in ("APPROVED", "REJECTED", "RETRACTED"):
        decided = QueueDecision(
            kind="FACTS", id=A, status=status, level="REVIEWED", sources_differ=False, message="m"
        )
        assert await review_queue_refresh.refresh_after_decision(None, decided) is True  # type: ignore[arg-type]
    assert asked == [[A], [A], [A]]
    assert sent == [PageOwners(crafts=("Kutch-Ajrakh",))] * 3
