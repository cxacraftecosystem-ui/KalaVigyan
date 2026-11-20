import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import CandidateCheck, Chunk, Claim, ClaimSource, Concept, Craft, Source
from app.services.write_back_audit import gate_less_write_backs

from .testimony_seed import rolled_back_session

pytestmark = pytest.mark.db

NOW = datetime(2031, 2, 1, tzinfo=UTC)
LATELY = NOW - timedelta(days=3)
FOUND_QUOTE = "the alum bath fixes the madder red to the cotton cloth"
LOST_QUOTE = "the iron bath turns the madder red to a deep brown"
WEAK_QUOTE = "a shop page says the cloth is washed in the river"
TWIN_TEXT = "Alum fixes the madder red to the cotton cloth of the craft."


def key(name: str) -> uuid.UUID:
    return uuid.uuid5(uuid.NAMESPACE_URL, f"test-write-back-audit/{name}")


CRAFT, CONCEPT = key("craft"), key("concept")
GOOD, LOST, WEAK = key("good-source"), key("lost-source"), key("weak-source")
PASSES, UNFOUND, D_ONLY, TWIN, GATED, HELD = (
    key("passes"),
    key("unfound"),
    key("d-only"),
    key("twin"),
    key("gated"),
    key("held"),
)


def claim(claim_id: uuid.UUID, text: str, *, origin: str = "LIVE_RESEARCH") -> Claim:
    return Claim(
        id=claim_id,
        subjectType="CONCEPT",
        subjectId=CONCEPT,
        predicate="states",
        text=text,
        evidenceLevel="PROVISIONAL",
        origin=origin,
        status="APPROVED",
        field="MATERIALS",
        createdAt=LATELY,
    )


def cited(claim_id: uuid.UUID, source_id: uuid.UUID, quote: str) -> ClaimSource:
    return ClaimSource(claimId=claim_id, sourceId=source_id, quote=quote, quoteCheck="PASS", foundBy="ANSWER")


def source(source_id: uuid.UUID, kind: str, url: str, reliability: str) -> Source:
    return Source(id=source_id, kind=kind, title="Mordant notes", url=url, reliability=reliability)


@pytest.fixture
async def session() -> AsyncIterator[AsyncSession]:
    async for opened in rolled_back_session():
        await _sources(opened)
        opened.add_all(
            [
                claim(PASSES, "The alum bath fixes the madder red to the cotton cloth."),
                claim(UNFOUND, "The iron bath turns the madder red of the cloth to a deep brown."),
                claim(D_ONLY, "The printed cloth is washed in the river after dyeing."),
                claim(TWIN, TWIN_TEXT),
                claim(HELD, TWIN_TEXT, origin="IMPORT"),
                claim(GATED, "The cloth is printed with alum before the madder bath."),
            ]
        )
        await opened.flush()
        opened.add_all(
            [
                cited(PASSES, GOOD, FOUND_QUOTE),
                cited(UNFOUND, LOST, LOST_QUOTE),
                cited(D_ONLY, WEAK, WEAK_QUOTE),
                cited(TWIN, GOOD, FOUND_QUOTE),
                cited(GATED, GOOD, FOUND_QUOTE),
                CandidateCheck(
                    claimId=GATED, gate="QUOTES", passed=True, reasons=["found"], checkedAt=LATELY
                ),
            ]
        )
        await opened.flush()
        yield opened


async def _sources(session: AsyncSession) -> None:
    session.add(Craft(id=CRAFT, slug="Write-Back-Audit-Craft", name="Write Back Audit Craft"))
    session.add_all(
        [
            source(GOOD, "PAPER", "https://audit.example.org/a", "B"),
            source(LOST, "PAPER", "https://audit.example.org/b", "B"),
            source(WEAK, "WEB_PAGE", "https://audit.example.org/c", "D"),
        ]
    )
    await session.flush()
    session.add(Concept(id=CONCEPT, craftId=CRAFT, type="MATERIAL", name="Alum"))
    session.add_all(
        [
            Chunk(sourceId=GOOD, ordinal=0, text=f"Printers say {FOUND_QUOTE}, after two washes."),
            Chunk(sourceId=LOST, ordinal=0, text="The page now speaks only of indigo vats."),
            Chunk(sourceId=WEAK, ordinal=0, text=f"Buy now: {WEAK_QUOTE} and dried in the sun."),
        ]
    )
    await session.flush()


async def test_the_gate_less_write_backs_are_re_checked_by_the_gates_that_need_no_model(
    session: AsyncSession,
) -> None:
    audit = await gate_less_write_backs(session, now=NOW, days=14)
    assert audit["claims"] == 4 and audit["byStatus"] == {"APPROVED": 4}
    assert audit["wouldPass"] == 1
    assert audit["wouldBeRefusedAt"] == {"DUPLICATE": 1, "QUOTES": 1, "SOURCE": 1}
    verdicts = {row["claimId"]: (row["wouldPass"], row["refusedAt"]) for row in audit["listed"]}
    assert verdicts == {
        str(PASSES): (True, None),
        str(UNFOUND): (False, "QUOTES"),
        str(D_ONLY): (False, "SOURCE"),
        str(TWIN): (False, "DUPLICATE"),
    }


async def test_the_re_check_writes_nothing(session: AsyncSession) -> None:
    checks = await session.scalar(select(func.count(CandidateCheck.id)))
    await gate_less_write_backs(session, now=NOW, days=14)
    assert await session.scalar(select(func.count(CandidateCheck.id))) == checks
    statuses = await session.scalars(
        select(Claim.status).where(Claim.id.in_([PASSES, UNFOUND, D_ONLY, TWIN]))
    )
    assert set(statuses.all()) == {"APPROVED"}


async def test_write_backs_outside_the_window_are_left_out(session: AsyncSession) -> None:
    audit = await gate_less_write_backs(session, now=NOW - timedelta(days=30), days=14)
    assert audit["claims"] == 0 and audit["listed"] == []
