import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Answer, CandidateCheck, Claim, ClaimSource, Concept, Craft, Source
from app.services.write_back_report import report_window, write_back_report

from .testimony_seed import rolled_back_session

pytestmark = pytest.mark.db

NOW = datetime(2031, 1, 1, tzinfo=UTC)
LATELY = NOW - timedelta(days=2)
LONG_AGO = NOW - timedelta(days=40)
SLUG = "Write-Back-Report-Craft"


def key(name: str) -> uuid.UUID:
    return uuid.uuid5(uuid.NAMESPACE_URL, f"test-write-back-report/{name}")


CRAFT, CONCEPT, SOURCE, ANSWER = key("craft"), key("concept"), key("source"), key("answer")


def live_claim(name: str, *, status: str, at: datetime) -> Claim:
    return Claim(
        id=key(name),
        subjectType="CONCEPT",
        subjectId=CONCEPT,
        predicate="states",
        text=f"Researched fact {name} about the alum bath of the craft.",
        evidenceLevel="PROVISIONAL",
        origin="LIVE_RESEARCH",
        status=status,
        createdAt=at,
    )


@pytest.fixture
async def session() -> AsyncIterator[AsyncSession]:
    async for opened in rolled_back_session():
        opened.add(Craft(id=CRAFT, slug=SLUG, name="Write Back Report Craft"))
        await opened.flush()
        opened.add(Concept(id=CONCEPT, craftId=CRAFT, type="MATERIAL", name="Alum"))
        opened.add(
            Source(id=SOURCE, kind="WEB_PAGE", title="Alum notes", url="https://report.example.org/alum")
        )
        opened.add(
            Answer(id=ANSWER, question="Why alum?", mode="DEEP", tiersUsed=["T1", "T3"], createdAt=LATELY)
        )
        opened.add(Answer(question="Why red?", mode="HYBRID", tiersUsed=["T1"], createdAt=LATELY))
        opened.add_all(
            [
                live_claim("live", status="IN_REVIEW", at=LATELY),
                live_claim("approved", status="APPROVED", at=LATELY),
                live_claim("old", status="IN_REVIEW", at=LONG_AGO),
            ]
        )
        await opened.flush()
        opened.add(
            ClaimSource(
                claimId=key("live"),
                sourceId=SOURCE,
                quote="alum fixes the red to the cotton",
                quoteCheck="PASS",
                foundBy="ANSWER",
                answerId=ANSWER,
                createdAt=LATELY,
            )
        )
        for gate, passed in (("QUOTES", True), ("SOURCE", True), ("DUPLICATE", True), ("NOVELTY", False)):
            opened.add(
                CandidateCheck(claimId=key("live"), gate=gate, passed=passed, reasons=["r"], checkedAt=LATELY)
            )
        await opened.flush()
        yield opened


async def test_the_report_reads_the_window_s_answers_claims_citations_and_gates(
    session: AsyncSession,
) -> None:
    report = await write_back_report(session, now=NOW, days=14)
    assert report["window"]["days"] == 14 and report["ok"] is True
    assert report["answers"] == {"total": 2, "withLiveResearch": 1, "byMode": {"DEEP": 1, "HYBRID": 1}}
    assert report["claims"] == {
        "written": 2,
        "byStatus": {"IN_REVIEW": 1, "APPROVED": 1},
        "byLevel": {"PROVISIONAL": 2},
        "gated": 1,
    }
    assert report["citations"] == {
        "added": 1,
        "byFoundBy": {"ANSWER": 1},
        "byQuoteCheck": {"PASS": 1},
        "answers": 1,
    }
    assert report["gates"]["NOVELTY"] == {"passed": 0, "refused": 1}
    assert report["gates"]["QUOTES"] == {"passed": 1, "refused": 0}
    assert report["crafts"] == [{"craft": SLUG, "written": 2}]
    assert {row["claimId"] for row in report["latest"]} == {str(key("live")), str(key("approved"))}


def test_a_report_window_covers_at_least_one_day() -> None:
    window = report_window(NOW, 1)
    assert (window.start, window.end) == (NOW - timedelta(days=1), NOW)
    with pytest.raises(ValueError, match="at least one day"):
        report_window(NOW, 0)
