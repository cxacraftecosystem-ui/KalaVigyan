import asyncio

import httpx
import pytest

from app.core.errors import ExternalFailure
from app.core.logging import request_id_scope
from app.sources.http import RatePolicy
from app.sources.scholarly.crossref import CROSSREF_LIMITS
from app.sources.scholarly.pacing import PacedHttp, ScholarlyPacing, ServiceLimits
from app.sources.scholarly.semantic_scholar import SEMANTIC_SCHOLAR_LIMITS

from .recorded import FakeClock, Recorder, Reply

WORKS = "https://api.crossref.org/works"
WORK = "https://api.crossref.org/works/10.55041/ijsrem46137"
OTHER_WORK = "https://api.crossref.org/works/10.9999/other"
PAPERS = "https://api.semanticscholar.org/graph/v1/paper/search"
CROSSREF_ROUTES = {
    "api.crossref.org/works": Reply("crossref_search.json"),
    "api.crossref.org/works/10.55041/ijsrem46137": Reply("crossref_work.json"),
    "api.crossref.org/works/10.9999/other": Reply("crossref_work.json"),
}


def paced(
    client: httpx.AsyncClient, service: str, limits: ServiceLimits, pacing: ScholarlyPacing, clock: FakeClock
) -> PacedHttp:
    return PacedHttp(
        client=client,
        service=service,
        policy=RatePolicy(min_interval=0.0),
        cache=pacing.cache(service),
        clock=clock,
        sleep=clock.sleep,
        limits=limits,
        pacing=pacing,
    )


def two_clients(
    recorder: Recorder, service: str, limits: ServiceLimits
) -> tuple[PacedHttp, PacedHttp, FakeClock]:
    clock = FakeClock()
    pacing = ScholarlyPacing(cache_clock=clock)
    first = paced(recorder.client(), service, limits, pacing, clock)
    return first, paced(recorder.client(), service, limits, pacing, clock), clock


async def test_two_clients_in_one_process_share_crossref_s_one_search_a_second() -> None:
    recorder = Recorder(CROSSREF_ROUTES)
    first, second, clock = two_clients(recorder, "crossref", CROSSREF_LIMITS)
    await first.get(WORKS, params={"query": "bidri"})
    await second.get(WORKS, params={"query": "bidri alloy"})
    assert clock.slept == [1.25]
    assert len(recorder.requests) == 2


async def test_crossref_lookups_keep_their_own_faster_pace() -> None:
    recorder = Recorder(CROSSREF_ROUTES)
    first, second, clock = two_clients(recorder, "crossref", CROSSREF_LIMITS)
    await first.get(WORKS, params={"query": "bidri"})
    await first.get(WORK)
    await second.get(OTHER_WORK)
    assert clock.slept == [0.25]


async def test_a_long_retry_after_pauses_the_source_for_every_client_without_sending() -> None:
    refused = Reply("semantic_scholar_429.json", status=429, headers={"Retry-After": "30"})
    recorder = Recorder({"api.semanticscholar.org/graph/v1/paper/search": refused})
    first, second, _ = two_clients(recorder, "semantic_scholar", SEMANTIC_SCHOLAR_LIMITS)
    with pytest.raises(ExternalFailure) as asked:
        await first.get(PAPERS, params={"query": "bidri"})
    with pytest.raises(ExternalFailure) as paused:
        await second.get(PAPERS, params={"query": "bidri alloy"})
    assert (asked.value.kind, paused.value.kind) == ("rate_limit", "rate_limit")
    assert "paused for 30 more seconds" in str(paused.value)
    assert len(recorder.requests) == 1


async def test_a_short_retry_after_is_waited_out_by_the_next_client_too() -> None:
    replies = [
        Reply("semantic_scholar_429.json", status=429, headers={"Retry-After": "4"}),
        Reply("semantic_scholar_search.json"),
        Reply("semantic_scholar_search.json"),
    ]
    recorder = Recorder({"api.semanticscholar.org/graph/v1/paper/search": replies})
    first, second, clock = two_clients(recorder, "semantic_scholar", SEMANTIC_SCHOLAR_LIMITS)
    await first.get(PAPERS, params={"query": "bidri"})
    await second.get(PAPERS, params={"query": "bidri alloy"})
    assert clock.slept == [4.0, 1.25]
    assert len(recorder.requests) == 3


async def test_a_source_that_refused_twice_is_not_asked_again_in_that_answer() -> None:
    refusals = [Reply("semantic_scholar_429.json", status=403) for _ in range(3)]
    recorder = Recorder({"api.semanticscholar.org/graph/v1/paper/search": refusals})
    http, _, _ = two_clients(recorder, "semantic_scholar", SEMANTIC_SCHOLAR_LIMITS)
    with request_id_scope("answer-0001"):
        for query in ("bidri", "bidri alloy", "bidri soil"):
            with pytest.raises(ExternalFailure):
                await http.get(PAPERS, params={"query": query})
    assert len(recorder.requests) == 2
    with request_id_scope("answer-0002"), pytest.raises(ExternalFailure):
        await http.get(PAPERS, params={"query": "bidri soil"})
    assert len(recorder.requests) == 3


async def test_a_lookup_that_failed_is_not_repeated_within_its_answer() -> None:
    missing = [Reply("crossref_missing.txt", status=404) for _ in range(2)]
    recorder = Recorder({"api.crossref.org/works/10.55041/ijsrem46137": missing})
    http, _, _ = two_clients(recorder, "crossref", CROSSREF_LIMITS)
    with request_id_scope("answer-0003"):
        for _ in range(2):
            with pytest.raises(ExternalFailure) as failed:
                await http.get(WORK)
            assert failed.value.kind == "not_found"
    assert len(recorder.requests) == 1
    with pytest.raises(ExternalFailure):
        await http.get(WORK)
    assert len(recorder.requests) == 2


async def test_a_lookup_is_answered_from_the_process_cache_after_the_sources_are_rebuilt() -> None:
    recorder = Recorder(CROSSREF_ROUTES)
    first, rebuilt, _ = two_clients(recorder, "crossref", CROSSREF_LIMITS)
    shown = await first.get(WORK)
    assert await rebuilt.get(WORK) is shown
    assert len(recorder.requests) == 1


async def test_crossref_never_has_two_requests_in_flight() -> None:
    flight = {"now": 0, "most": 0}

    async def handle(request: httpx.Request) -> httpx.Response:
        flight["now"] += 1
        flight["most"] = max(flight["most"], flight["now"])
        for _ in range(3):
            await asyncio.sleep(0)
        flight["now"] -= 1
        return Reply("crossref_work.json").response()

    clock = FakeClock()
    pacing = ScholarlyPacing(cache_clock=clock)
    client = httpx.AsyncClient(transport=httpx.MockTransport(handle))
    http = paced(client, "crossref", CROSSREF_LIMITS, pacing, clock)
    await asyncio.gather(http.get(WORK), http.get(OTHER_WORK))
    assert flight["most"] == 1
