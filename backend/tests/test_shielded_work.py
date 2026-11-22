import asyncio
import logging
from typing import Any

import pytest

from app.core.shielded import ShieldedWork
from app.services.answer_store import SqlAnswerStore
from app.services.craft_resolver import CraftIndexStore

from .answering.fakes import ANSWER_ID
from .craft_fixtures import FixedEmbedder


async def write_back(started: asyncio.Event, release: asyncio.Event, kept: list[str]) -> str:
    started.set()
    await release.wait()
    kept.append("committed")
    return "kept"


async def caller_leaves(shield: ShieldedWork, work: Any) -> asyncio.Task[Any]:
    caller = asyncio.create_task(shield.run(work, name="answer write-back"))
    await asyncio.sleep(0)
    caller.cancel()
    with pytest.raises(asyncio.CancelledError):
        await caller
    return caller


async def test_work_finishes_when_its_caller_leaves() -> None:
    shield, started, release, kept = ShieldedWork(), asyncio.Event(), asyncio.Event(), []
    await caller_leaves(shield, write_back(started, release, kept))
    assert started.is_set() and kept == [] and shield.running == 1
    release.set()
    assert await shield.drain() == 0
    assert kept == ["committed"] and shield.running == 0


async def test_a_caller_that_stays_gets_the_result_and_the_error() -> None:
    shield, started, release, kept = ShieldedWork(), asyncio.Event(), asyncio.Event(), []
    release.set()
    assert await shield.run(write_back(started, release, kept), name="answer write-back") == "kept"

    async def fails() -> None:
        raise RuntimeError("write-back failed")

    with pytest.raises(RuntimeError, match="write-back failed"):
        await shield.run(fails(), name="answer write-back")
    assert shield.running == 0


async def test_a_failure_after_the_caller_left_is_logged(caplog: pytest.LogCaptureFixture) -> None:
    shield, release = ShieldedWork(), asyncio.Event()

    async def fails_later() -> None:
        await release.wait()
        raise RuntimeError("database went away")

    await caller_leaves(shield, fails_later())
    with caplog.at_level(logging.INFO):
        release.set()
        await shield.drain()
    assert "answer write-back failed after its caller left" in caplog.text


async def test_shutdown_waits_a_bounded_time_and_reports_what_is_left(
    caplog: pytest.LogCaptureFixture,
) -> None:
    shield, started, release, kept = ShieldedWork(), asyncio.Event(), asyncio.Event(), []
    await caller_leaves(shield, write_back(started, release, kept))
    with caplog.at_level(logging.WARNING):
        assert await shield.drain(timeout=0.01) == 1
    assert "answer write-back was still running when the process stopped" in caplog.text
    release.set()
    assert await shield.drain() == 0


async def test_the_answer_stores_write_back_outlives_a_learner_who_leaves() -> None:
    shield, release = ShieldedWork(), asyncio.Event()
    store = SqlAnswerStore(None, embed=FixedEmbedder(), shield=shield, index=CraftIndexStore())
    written: list[Any] = []

    async def kept(answer_id: Any, *_: Any) -> tuple[()]:
        await release.wait()
        written.append(answer_id)
        return ()

    store._kept = kept
    caller = asyncio.create_task(store.keep(ANSWER_ID, None, None))
    await asyncio.sleep(0)
    caller.cancel()
    with pytest.raises(asyncio.CancelledError):
        await caller
    release.set()
    await shield.drain()
    assert written == [ANSWER_ID]
