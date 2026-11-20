import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Any

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import InvalidInput
from app.models import AuditLog, ClaimSource, TaskReservation, User
from app.research.open_work import TaskSubject, task_key
from app.research.source_proposals import SourceProposal
from app.services.claim_holds import held_claim_ids
from app.services.source_proposals import SOURCE_ADDED, SourceAsk, propose_source
from app.services.task_reservations import claim_task

from ..knowledge_writes.fakes import PAGE_URL, QUOTE, FakeFetcher, page
from .claim_holds_seed import HELD, SLUG, SOUND, held_session

pytestmark = pytest.mark.db

NOW = datetime(2026, 11, 20, 9, 0, tzinfo=UTC)
SITE = "https://kalavigyan.example"
SUBJECT = TaskSubject(
    kind="craft", slug=SLUG, name="Claim Holds Test Craft", page_url=f"{SITE}/crafts/{SLUG}"
)
RESOURCE_KEY = task_key("RESOURCE_FACT", SUBJECT, "CHEMISTRY")


@pytest.fixture
async def session() -> AsyncIterator[AsyncSession]:
    async for opened in held_session():
        yield opened


@pytest.fixture
async def researcher(session: AsyncSession) -> User:
    token = uuid.uuid4()
    user = User(id=token, name="Researcher", email=f"{token.hex[:12]}@example.org", role="RESEARCHER")
    session.add(user)
    await session.flush()
    return user


def proposal(claim_id: uuid.UUID = HELD, quote: str = QUOTE, **changes: Any) -> SourceProposal:
    body: dict[str, Any] = {
        "claimId": str(claim_id),
        "sources": [
            {"url": PAGE_URL, "title": "Indigo in Ajrakh", "quotes": [{"text": quote, "locator": "p. 2"}]}
        ],
        **changes,
    }
    return SourceProposal.model_validate(body)


def ask(user: User) -> SourceAsk:
    return SourceAsk(
        proposer=user, origin="AGENT", fetcher=FakeFetcher({PAGE_URL: page()}), site=SITE, now=NOW
    )


async def test_a_found_quote_joins_the_held_fact_and_lifts_the_hold(
    session: AsyncSession, researcher: User
) -> None:
    await claim_task(session, researcher.id, RESOURCE_KEY, site=SITE, now=NOW)
    reply = await propose_source(session, proposal(taskKey=RESOURCE_KEY), ask(researcher))
    assert (reply.outcome, reply.quotes_added, reply.held) == ("ADDED", 1, False)
    assert reply.message.endswith("The fact shows on its page again.")
    added = await session.scalars(
        select(ClaimSource).where(ClaimSource.claimId == HELD, ClaimSource.quote == QUOTE)
    )
    (row,) = added.all()
    assert (row.quoteCheck, row.foundBy, row.locator) == ("PASS", "AGENT", "p. 2")
    assert await held_claim_ids(session, [HELD]) == frozenset()
    ended = await session.scalar(
        select(TaskReservation.ending).where(TaskReservation.taskKey == RESOURCE_KEY)
    )
    assert ended == "COMPLETED"
    logged = await session.scalars(select(AuditLog.targetId).where(AuditLog.action == SOURCE_ADDED))
    assert str(HELD) in logged.all()


async def test_a_quote_the_page_does_not_hold_adds_nothing(session: AsyncSession, researcher: User) -> None:
    reply = await propose_source(
        session, proposal(quote="The cloth is never dipped in any vat at all"), ask(researcher)
    )
    assert (reply.outcome, reply.quotes_added, reply.held) == ("REFUSED", 0, True)
    assert reply.gates[0].gate == "QUOTES" and not reply.gates[0].passed
    assert await held_claim_ids(session, [HELD]) == frozenset({HELD})


async def test_an_unknown_fact_a_cited_quote_and_another_fact_s_task_are_refused(
    session: AsyncSession, researcher: User
) -> None:
    with pytest.raises(InvalidInput, match="No shown fact has the id"):
        await propose_source(session, proposal(claim_id=uuid.uuid4()), ask(researcher))
    cited = (await session.scalars(select(ClaimSource.quote).where(ClaimSource.claimId == SOUND))).one()
    with pytest.raises(InvalidInput, match="already cites the quote"):
        await propose_source(session, proposal(claim_id=SOUND, quote=str(cited)), ask(researcher))
    with pytest.raises(InvalidInput, match="lists other facts than"):
        await propose_source(session, proposal(claim_id=SOUND, taskKey=RESOURCE_KEY), ask(researcher))
