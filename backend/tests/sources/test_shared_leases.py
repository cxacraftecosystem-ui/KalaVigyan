import asyncio
from collections.abc import Callable

import httpx
import pytest

from app.core.errors import ExternalFailure
from app.core.logging import request_id_scope
from app.core.paces import LeaseAsk, MemoryPaces
from app.sources.scholarly.crossref import CROSSREF_LIMITS
from app.sources.scholarly.pacing import LEASE_SECONDS, ServicePace
from app.sources.scholarly.semantic_scholar import SEMANTIC_SCHOLAR_LIMITS

from .paced import YieldingClock, process
from .recorded import FakeClock, Recorder, Reply

PAPERS = "https://api.semanticscholar.org/graph/v1/paper/search"
S2_ROUTE = "api.semanticscholar.org/graph/v1/paper/search"
WORK = "https://api.crossref.org/works/10.9999/other"
ONE_AT_A_TIME = LeaseAsk(concurrency=1, seconds=LEASE_SECONDS)


async def test_two_processes_on_one_store_never_have_more_than_three_crossref_requests_in_flight() -> None:
    flight = {"now": 0, "most": 0}

    async def handle(request: httpx.Request) -> httpx.Response:
        flight["now"] += 1
        flight["most"] = max(flight["most"], flight["now"])
        for _ in range(3):
            await asyncio.sleep(0)
        flight["now"] -= 1
        return Reply("crossref_work.json").response()

    clock = YieldingClock()
    store = MemoryPaces(clock=clock)
    client = httpx.AsyncClient(transport=httpx.MockTransport(handle))
    first, second = (process(client, "crossref", CROSSREF_LIMITS, store, clock) for _ in range(2))
    await asyncio.gather(*(http.get(f"{WORK}.{n}") for n in range(3) for http in (first, second)))
    assert flight["most"] == 3
    freed = [await store.lease("crossref", LeaseAsk(concurrency=3, seconds=1.0)) for _ in range(4)]
    assert [lease is not None for lease in freed] == [True, True, True, False]


async def test_a_lease_left_by_a_process_that_died_frees_its_slot_when_it_expires() -> None:
    recorder = Recorder({S2_ROUTE: Reply("semantic_scholar_search.json")})
    clock = FakeClock()
    store = MemoryPaces(clock=clock)
    assert await store.lease("semantic_scholar", LeaseAsk(concurrency=1, seconds=2.0)) is not None
    http = process(recorder.client(), "semantic_scholar", SEMANTIC_SCHOLAR_LIMITS, store, clock)
    with request_id_scope("answer-0201"):
        await http.get(PAPERS, params={"query": "khurja"})
    assert clock.slept == [0.5, 0.5, 0.5, 0.5]
    assert len(recorder.requests) == 1
    assert http.pacing.answer_pace("answer-0201").services == (
        ServicePace("semantic_scholar", waited_seconds=2.0, waited_requests=1),
    )


def unreachable(request: httpx.Request) -> httpx.Response:
    raise httpx.ConnectError("refused", request=request)


@pytest.mark.parametrize(
    "client",
    [
        lambda: Recorder({S2_ROUTE: Reply("semantic_scholar_429.json", status=404)}).client(),
        lambda: httpx.AsyncClient(transport=httpx.MockTransport(unreachable)),
    ],
)
async def test_a_request_that_fails_gives_its_slot_back(client: Callable[[], httpx.AsyncClient]) -> None:
    clock = FakeClock()
    store = MemoryPaces(clock=clock)
    http = process(client(), "semantic_scholar", SEMANTIC_SCHOLAR_LIMITS, store, clock)
    with pytest.raises(ExternalFailure):
        await http.get(PAPERS, params={"query": "khurja"})
    assert await store.lease("semantic_scholar", ONE_AT_A_TIME) is not None


async def test_a_request_with_no_free_slot_within_thirty_seconds_is_not_sent() -> None:
    recorder = Recorder({S2_ROUTE: Reply("semantic_scholar_search.json")})
    clock = FakeClock()
    store = MemoryPaces(clock=clock)
    assert await store.lease("semantic_scholar", LeaseAsk(concurrency=1, seconds=1000.0)) is not None
    http = process(recorder.client(), "semantic_scholar", SEMANTIC_SCHOLAR_LIMITS, store, clock)
    with (
        request_id_scope("answer-0202"),
        pytest.raises(ExternalFailure, match="no free request slot within 30 seconds") as refused,
    ):
        await http.get(PAPERS, params={"query": "khurja"})
    assert refused.value.kind == "unavailable"
    assert clock.slept == [0.5] * 60
    assert recorder.requests == []
    assert http.pacing.answer_pace("answer-0202").services == (
        ServicePace("semantic_scholar", waited_seconds=30.0, waited_requests=1, unsent=1),
    )


async def test_the_memory_store_counts_each_service_s_live_leases() -> None:
    clock = FakeClock()
    store = MemoryPaces(clock=clock)
    two = LeaseAsk(concurrency=2, seconds=10.0)
    first = await store.lease("crossref", two)
    assert first is not None and await store.lease("crossref", two) is not None
    assert await store.lease("crossref", two) is None
    assert await store.lease("arxiv", two) is not None
    await store.release(first)
    assert await store.lease("crossref", two) is not None
    assert await store.lease("crossref", two) is None
    clock.now += 10.0
    assert [await store.lease("crossref", two) is not None for _ in range(3)] == [True, True, False]
