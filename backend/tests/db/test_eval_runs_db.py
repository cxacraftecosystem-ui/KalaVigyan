from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import EvalRun
from app.retrieval.eval_floors import FloorCheck
from app.services.eval_run_store import EvalKind, EvalRunRecord, RunTimes, latest_eval_runs, store_eval_run

from .testimony_seed import rolled_back_session

pytestmark = pytest.mark.db

NOW = datetime(2031, 3, 10, 12, 0, tzinfo=UTC)
RELEASE = "45ce9a17" + "2" * 32
RECALL = "handWritten.reranked.recallAt5"


@pytest.fixture
async def session() -> AsyncIterator[AsyncSession]:
    async for opened in rolled_back_session():
        yield opened


def run(kind: EvalKind, days_ago: int, means: dict[str, float], **flags: bool | None) -> EvalRunRecord:
    finished = NOW - timedelta(days=days_ago)
    return EvalRunRecord(
        kind=kind,
        times=RunTimes(finished - timedelta(minutes=50), finished, RELEASE),
        spent_usd=Decimal("2.15"),
        cap_usd=Decimal("30.00") if kind == "ANSWERS" else None,
        means=means,
        floors=tuple(FloorCheck(measure, 0.9, value) for measure, value in means.items()),
        floors_held=flags.get("held"),
        fresh=bool(flags.get("fresh")),
    )


async def test_each_kind_reads_back_its_latest_finished_run(session: AsyncSession) -> None:
    for kept in (
        run("RETRIEVAL", 7, {RECALL: 0.95}, held=True),
        run("RETRIEVAL", 1, {RECALL: 0.97}, held=True),
        run("ANSWERS", 3, {"judgeMean": 0.81, "rubricMean": 0.92}, held=False, fresh=True),
    ):
        await store_eval_run(session, kept)
    latest = await latest_eval_runs(session)
    assert sorted(latest) == ["ANSWERS", "RETRIEVAL"]
    retrieval, answers = latest["RETRIEVAL"], latest["ANSWERS"]
    assert (retrieval.means, retrieval.times.finished_at) == ({RECALL: 0.97}, NOW - timedelta(days=1))
    assert (answers.fresh, answers.floors_held, answers.times.release) == (True, False, RELEASE)
    assert (answers.spent_usd, answers.cap_usd) == (Decimal("2.15"), Decimal("30.00"))
    assert [(c.measure, c.floor, c.value, c.held) for c in answers.floors] == [
        ("judgeMean", 0.9, 0.81, False),
        ("rubricMean", 0.9, 0.92, True),
    ]


async def test_a_run_of_no_known_kind_is_refused_by_the_table(session: AsyncSession) -> None:
    session.add(EvalRun(suite="WEEKLY", status="SUCCEEDED", startedAt=NOW, finishedAt=NOW))
    with pytest.raises(IntegrityError, match="EvalRun_suite_check"):
        await session.flush()
