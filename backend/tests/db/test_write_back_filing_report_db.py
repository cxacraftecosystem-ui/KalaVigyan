import json
import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Answer, CandidateCheck, Chunk, Claim, ClaimSource, Concept, Craft, ReviewEvent, Source
from app.services.claim_writer import HELD_WRITE_BACK_ACTOR
from app.services.craft_resolver import CraftIndexStore
from app.services.write_back_crafts import HELD_UNNAMED, SKIP_ABROAD
from app.services.write_back_filing import report_lines
from app.services.write_back_filing_store import filing_report

from .testimony_seed import rolled_back_session

pytestmark = pytest.mark.db

WRITTEN = datetime(2031, 3, 1, tzinfo=UTC)
SLUG = "Vornel-Glaze-Pottery"
AGED = "the body is aged for two days"


def key(name: str) -> uuid.UUID:
    return uuid.uuid5(uuid.NAMESPACE_URL, f"test-write-back-filing-report/{name}")


CRAFT, CONCEPT, ANSWER, OTHER_ANSWER = key("craft"), key("concept"), key("answer"), key("other-answer")
STUDY, HANDBOOK = key("study"), key("handbook")
TITLED, ABROAD, HELD, ELSEWHERE = key("titled"), key("abroad"), key("held"), key("elsewhere")


def claim(claim_id: uuid.UUID, text: str, status: str = "IN_REVIEW") -> Claim:
    return Claim(
        id=claim_id,
        subjectType="CONCEPT",
        subjectId=CONCEPT,
        predicate="states",
        text=text,
        evidenceLevel="PROVISIONAL",
        origin="LIVE_RESEARCH",
        status=status,
        field="PROCESS",
        createdAt=WRITTEN,
    )


def cited(claim_id: uuid.UUID, source_id: uuid.UUID, answer_id: uuid.UUID, chunk: uuid.UUID | None = None):
    quote = AGED if chunk is not None else None
    return ClaimSource(
        claimId=claim_id,
        sourceId=source_id,
        chunkId=chunk,
        quote=quote,
        quoteCheck="PASS" if quote else "NA",
        foundBy="ANSWER",
        answerId=answer_id,
    )


@pytest.fixture
async def session() -> AsyncIterator[AsyncSession]:
    async for opened in rolled_back_session():
        opened.add(Craft(id=CRAFT, slug=SLUG, name="Vornel Glaze Pottery"))
        opened.add_all(
            [
                Source(id=STUDY, kind="PAPER", title="Studies of Vornel glazes", reliability="B"),
                Source(id=HANDBOOK, kind="BOOK", title="A handbook of ceramic glazes", reliability="B"),
            ]
        )
        await opened.flush()
        opened.add(Concept(id=CONCEPT, craftId=CRAFT, type="MATERIAL", name="Clay body"))
        opened.add_all(
            [
                Answer(id=ANSWER, question="How is Vornel pottery fired?", mode="HYBRID", craftId=CRAFT),
                Answer(id=OTHER_ANSWER, question="How is clay aged?", mode="HYBRID", craftId=CRAFT),
            ]
        )
        chunk = Chunk(sourceId=HANDBOOK, ordinal=0, text=f"Potters say {AGED} before wedging.")
        opened.add(chunk)
        await opened.flush()
        await _claims(opened, chunk.id)
        yield opened


async def _claims(session: AsyncSession, chunk: uuid.UUID) -> None:
    session.add_all(
        [
            claim(TITLED, "The body is aged for two days."),
            claim(ABROAD, "In Khorezm practice, the body is kneaded by hand."),
            claim(HELD, "The body is aged for two days before wedging.", status="DRAFT"),
            claim(ELSEWHERE, "The kiln is fired for a day."),
        ]
    )
    await session.flush()
    session.add_all(
        [
            cited(TITLED, STUDY, ANSWER),
            cited(ABROAD, HANDBOOK, ANSWER),
            cited(HELD, HANDBOOK, ANSWER, chunk),
            cited(ELSEWHERE, HANDBOOK, OTHER_ANSWER),
            CandidateCheck(claimId=TITLED, gate="QUOTES", passed=True, reasons=["found"], checkedAt=WRITTEN),
            CandidateCheck(claimId=HELD, gate="QUOTES", passed=True, reasons=["found"], checkedAt=WRITTEN),
            ReviewEvent(
                claimId=HELD, actorKind="SYSTEM", systemActor=HELD_WRITE_BACK_ACTOR, toStatus="DRAFT"
            ),
        ]
    )
    await session.flush()


async def test_the_report_shows_where_each_answer_s_fact_is_and_where_today_s_rule_files_it(
    session: AsyncSession,
) -> None:
    rows = await filing_report(session, CraftIndexStore(), answer_id=ANSWER)
    found = {row.claim_id: (row.place, row.would, row.why, row.checked) for row in rows}
    assert found == {
        TITLED: (f"craft:{SLUG}", f"craft:{SLUG}", None, True),
        ABROAD: (f"craft:{SLUG}", "refused", SKIP_ABROAD.format(places="Khorezm"), False),
        HELD: (f"held:{SLUG}", f"held:{SLUG}", HELD_UNNAMED, True),
    }
    summary = json.loads(report_lines(rows)[-1])
    assert (summary["claims"], summary["moves"], summary["unchecked"]) == (3, 1, [str(ABROAD)])


async def test_the_report_reads_a_day_onwards_and_writes_nothing(session: AsyncSession) -> None:
    rows = await filing_report(session, CraftIndexStore(), since=WRITTEN)
    assert {row.claim_id for row in rows} >= {TITLED, ABROAD, HELD, ELSEWHERE}
    later = await filing_report(session, CraftIndexStore(), since=datetime(2031, 3, 2, tzinfo=UTC))
    assert {TITLED, ABROAD, HELD, ELSEWHERE}.isdisjoint(row.claim_id for row in later)
    assert not session.new and not session.dirty and not session.deleted
