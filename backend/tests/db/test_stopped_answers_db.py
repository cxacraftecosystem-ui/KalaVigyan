import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime

import pytest
from sqlalchemy import select

from app.core.shielded import ShieldedWork
from app.models import Answer
from app.research.sections import AnswerPlans
from app.services.answer_store import SqlAnswerStore
from app.services.craft_resolver import CraftIndexStore

from ..craft_fixtures import FixedEmbedder
from .alerts_seed import Seeded, seeded

pytestmark = pytest.mark.db

REQUEST = "stopped-answer-request-0001"
OTHER = "stopped-answer-request-0002"


@pytest.fixture
async def db() -> AsyncIterator[Seeded]:
    async with seeded() as found:
        yield found


def store(db: Seeded) -> SqlAnswerStore:
    return SqlAnswerStore(db.sessions, embed=FixedEmbedder(), shield=ShieldedWork(), index=CraftIndexStore())


async def answer_row(db: Seeded, request_id: str, *, latency_ms: int | None = None) -> uuid.UUID:
    answer_id = uuid.uuid4()
    row = Answer(id=answer_id, question="Why is Ajrakh red?", mode="HYBRID", requestId=request_id)
    row.latencyMs = latency_ms
    db.session.add(row)
    await db.session.commit()
    return answer_id


async def stopped_at(db: Seeded, *ids: uuid.UUID) -> list[bool]:
    rows = dict(
        (await db.session.execute(select(Answer.id, Answer.stoppedAt).where(Answer.id.in_(ids)))).all()
    )
    return [rows[answer_id] is not None for answer_id in ids]


async def test_stopping_a_request_marks_only_its_answer_that_never_finished(db: Seeded) -> None:
    begun = await answer_row(db, REQUEST)
    finished = await answer_row(db, REQUEST, latency_ms=11_000)
    elsewhere = await answer_row(db, OTHER)
    await store(db).stop(REQUEST)
    db.session.expire_all()
    assert await stopped_at(db, begun, finished, elsewhere) == [True, False, False]


async def test_an_answer_that_finishes_after_it_was_marked_stopped_is_not_stopped(db: Seeded) -> None:
    begun = await answer_row(db, REQUEST)
    answers = store(db)
    await answers.stop(REQUEST)
    await answers.finish(
        begun, asked_at=datetime.now(UTC), plans=AnswerPlans(sections=[]), claim_ids=[], explainer=None
    )
    db.session.expire_all()
    assert await stopped_at(db, begun) == [False]
