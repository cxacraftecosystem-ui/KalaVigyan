import asyncio
from dataclasses import dataclass, field
from typing import Any

import pytest

from app.core.errors import ExternalFailure
from app.core.logging import request_id_scope
from app.research.evidence_pack import EvidencePack
from app.services.answering import answer_question

from .fakes import FakeResearch, FakeStore, pipeline, streamed
from .test_answer_flow import REPLY, detailed

REQUEST = "http-request-stopped-0001"


@dataclass
class HeldResearch(FakeResearch):
    started: asyncio.Event = field(default_factory=asyncio.Event)

    async def __call__(self, *args: Any, **kwargs: Any) -> EvidencePack:
        self.started.set()
        await asyncio.Event().wait()
        raise AssertionError("held research never returns")


async def ignored(name: str, data: Any) -> None:
    return None


async def test_an_answer_whose_stream_is_cancelled_after_it_began_is_marked_stopped() -> None:
    store, research = FakeStore(), HeldResearch()
    with request_id_scope(REQUEST):
        task = asyncio.create_task(
            answer_question(detailed(), pipeline(research=research, store=store), ignored)
        )
    await asyncio.wait_for(research.started.wait(), 5)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert (len(store.begun), store.finished, store.stopped) == (1, [], [REQUEST])


async def test_an_answer_that_fails_after_it_began_is_marked_stopped() -> None:
    store = FakeStore()
    failure = ExternalFailure("every source failed", kind="unavailable", service="live_research")
    with request_id_scope(REQUEST):
        await streamed(detailed(), pipeline(research=FakeResearch(failure=failure), store=store))
    assert (len(store.begun), store.finished, store.stopped) == (1, [], [REQUEST])


async def test_a_finished_answer_is_not_marked_stopped() -> None:
    store = FakeStore()
    with request_id_scope(REQUEST):
        await streamed(detailed(), pipeline(replies=[REPLY], store=store))
    assert (len(store.finished), store.stopped) == (1, [])
