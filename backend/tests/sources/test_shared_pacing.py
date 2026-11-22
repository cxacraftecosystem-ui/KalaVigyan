import dataclasses
from collections.abc import Sequence

import pytest

from app.core.errors import ExternalFailure
from app.core.logging import request_id_scope
from app.core.paces import (
    LeaseAsk,
    MemoryPaces,
    PaceAsk,
    PaceLane,
    PaceLease,
    PaceSlot,
    PaceUnread,
    SharedPaces,
)
from app.sources.scholarly.core_works import CORE_LIMITS
from app.sources.scholarly.crossref import CROSSREF_LIMITS, CrossrefAdapter
from app.sources.scholarly.pacing import (
    AnswerPace,
    PacedHttp,
    ScholarlyPacing,
    ServiceLimits,
    ServicePace,
    answer_pace,
    shared_pacing,
)
from app.sources.scholarly.registry import ScholarlyKeys, scholarly_sources
from app.sources.scholarly.semantic_scholar import SEMANTIC_SCHOLAR_LIMITS

from .paced import process
from .recorded import CONTACT, FakeClock, Recorder, Reply, fixed_clock, source_http

WORKS = "https://api.crossref.org/works"
PAPERS = "https://api.semanticscholar.org/graph/v1/paper/search"
CORE_SEARCH = "https://api.core.ac.uk/v3/search/works/"
CROSSREF_ROUTES = {"api.crossref.org/works": Reply("crossref_search.json")}
S2_ROUTE = "api.semanticscholar.org/graph/v1/paper/search"
CORE_ROUTES = {"api.core.ac.uk/v3/search/works/": Reply("core_search.json")}


def two_processes(
    recorder: Recorder, service: str, limits: ServiceLimits
) -> tuple[PacedHttp, PacedHttp, FakeClock]:
    clock = FakeClock()
    store = MemoryPaces(clock=clock)
    first = process(recorder.client(), service, limits, store, clock)
    return first, process(recorder.client(), service, limits, store, clock), clock


async def test_two_processes_on_one_store_share_crossref_s_search_pace_but_not_their_caches() -> None:
    recorder = Recorder(CROSSREF_ROUTES)
    first, second, clock = two_processes(recorder, "crossref", CROSSREF_LIMITS)
    await first.get(WORKS, params={"query": "khurja glaze"})
    await second.get(WORKS, params={"query": "khurja glaze"})
    assert clock.slept == [pytest.approx(5 / 12)]
    assert len(recorder.requests) == 2


async def test_a_long_retry_after_from_one_process_pauses_the_other_without_sending() -> None:
    refused = Reply("semantic_scholar_429.json", status=429, headers={"Retry-After": "30"})
    recorder = Recorder({S2_ROUTE: refused})
    first, second, _ = two_processes(recorder, "semantic_scholar", SEMANTIC_SCHOLAR_LIMITS)
    with pytest.raises(ExternalFailure):
        await first.get(PAPERS, params={"query": "khurja"})
    with pytest.raises(ExternalFailure, match="paused for 30 more seconds") as paused:
        await second.get(PAPERS, params={"query": "khurja glaze"})
    assert paused.value.kind == "rate_limit"
    assert len(recorder.requests) == 1


async def test_a_short_retry_after_from_one_process_is_waited_out_by_the_other() -> None:
    replies = [
        Reply("semantic_scholar_429.json", status=429, headers={"Retry-After": "4"}),
        Reply("semantic_scholar_search.json"),
        Reply("semantic_scholar_search.json"),
    ]
    recorder = Recorder({S2_ROUTE: replies})
    first, second, clock = two_processes(recorder, "semantic_scholar", SEMANTIC_SCHOLAR_LIMITS)
    await first.get(PAPERS, params={"query": "khurja"})
    await second.get(PAPERS, params={"query": "khurja glaze"})
    assert clock.slept == [4.0, 1.25]


async def test_an_answer_s_seats_queue_on_one_pace_and_its_record_sums_the_waits() -> None:
    recorder = Recorder({S2_ROUTE: Reply("semantic_scholar_search.json")})
    clock = FakeClock()
    store = MemoryPaces(clock=clock)
    http = process(recorder.client(), "semantic_scholar", SEMANTIC_SCHOLAR_LIMITS, store, clock)
    with request_id_scope("answer-0101"):
        for seat_query in ("khurja", "khurja glaze", "khurja clay"):
            await http.get(PAPERS, params={"query": seat_query})
    assert clock.slept == [1.25, 1.25]
    record = http.pacing.answer_pace("answer-0101")
    assert record == AnswerPace(
        "answer-0101", (ServicePace("semantic_scholar", waited_seconds=2.5, waited_requests=2),)
    )
    assert record.waited_seconds == 2.5
    with pytest.raises(dataclasses.FrozenInstanceError):
        record.services[0].__setattr__("waited_seconds", 0.0)


async def test_a_request_beyond_the_thirty_second_queue_is_not_sent_and_is_recorded() -> None:
    recorder = Recorder(CORE_ROUTES)
    clock = FakeClock()
    store = MemoryPaces(clock=clock)
    roomy = PaceAsk(interval=7.5, queue_max=1000.0, hold_max=10.0)
    for _ in range(5):
        await store.reserve(PaceLane("core", "search"), roomy)
    http = process(recorder.client(), "core", CORE_LIMITS, store, clock)
    with request_id_scope("answer-0102"):
        with pytest.raises(ExternalFailure, match="more than 30 seconds of requests waiting") as queued:
            await http.get(CORE_SEARCH, params={"q": "khurja"})
        clock.now += 7.5
        await http.get(CORE_SEARCH, params={"q": "khurja glaze"})
    assert queued.value.kind == "unavailable"
    assert clock.slept == [30.0]
    assert len(recorder.requests) == 1
    assert http.pacing.answer_pace("answer-0102").services == (
        ServicePace("core", waited_seconds=30.0, waited_requests=1, unsent=1),
    )


async def test_only_a_service_s_own_429_and_403_count_towards_its_two_refusals() -> None:
    replies = [
        Reply("semantic_scholar_429.json", status=429, headers={"Retry-After": "30"}),
        Reply("semantic_scholar_429.json", status=403),
    ]
    recorder = Recorder({S2_ROUTE: replies})
    http, _, clock = two_processes(recorder, "semantic_scholar", SEMANTIC_SCHOLAR_LIMITS)
    with request_id_scope("answer-0103"):
        for query in ("khurja", "khurja glaze"):
            with pytest.raises(ExternalFailure):
                await http.get(PAPERS, params={"query": query})
        clock.now += 31.0
        for query in ("khurja clay", "khurja cobalt"):
            with pytest.raises(ExternalFailure):
                await http.get(PAPERS, params={"query": query})
    assert len(recorder.requests) == 2
    assert http.pacing.answer_pace("answer-0103").services == (
        ServicePace("semantic_scholar", refusals=2, unsent=2),
    )


class UnreadPaces:
    async def reserve(self, lane: PaceLane, ask: PaceAsk) -> PaceSlot:
        raise PaceUnread(f"the {lane.lane} pace of {lane.service} was not read")

    async def hold(self, lanes: Sequence[PaceLane], seconds: float) -> None:
        raise PaceUnread("the hold was not written")

    async def lease(self, service: str, ask: LeaseAsk) -> PaceLease | None:
        raise PaceUnread(f"the leases of {service} were not read")

    async def release(self, lease: PaceLease) -> None:
        raise PaceUnread(f"the lease of {lease.service} was not deleted")


async def test_a_pace_that_cannot_be_read_sends_nothing() -> None:
    recorder = Recorder(CROSSREF_ROUTES)
    http = process(recorder.client(), "crossref", CROSSREF_LIMITS, UnreadPaces(), FakeClock())
    with pytest.raises(ExternalFailure, match="could not be paced") as unread:
        await http.get(WORKS, params={"query": "khurja"})
    assert unread.value.kind == "unavailable"
    assert recorder.requests == []


async def test_the_memory_store_spaces_a_lane_and_honours_a_hold() -> None:
    clock = FakeClock()
    store = MemoryPaces(clock=clock)
    lane = PaceLane("crossref", "search")
    ask = PaceAsk(interval=2.0, queue_max=30.0, hold_max=5.0)
    assert [(await store.reserve(lane, ask)).wait for _ in range(3)] == [0.0, 2.0, 4.0]
    await store.hold([lane, PaceLane("crossref", "lookup")], 10.0)
    assert await store.reserve(lane, ask) == PaceSlot(wait=None, held_for=10.0)
    assert await store.reserve(PaceLane("crossref", "lookup"), ask) == PaceSlot(wait=None, held_for=10.0)
    patient = PaceAsk(interval=2.0, queue_max=30.0, hold_max=20.0)
    assert await store.reserve(lane, patient) == PaceSlot(wait=10.0)


def test_every_build_of_the_sources_paces_on_the_one_shared_store() -> None:
    keys = ScholarlyKeys(contact_email=CONTACT)
    first, rebuilt = (scholarly_sources(keys, Recorder({}).client(), clock=fixed_clock()) for _ in range(2))
    paced = [adapter.http for adapter in (*first.adapters, *rebuilt.adapters)]
    assert all(isinstance(http, PacedHttp) and http.pacing is shared_pacing() for http in paced)
    assert isinstance(shared_pacing().store, SharedPaces)


@pytest.mark.parametrize(("key", "interval"), [(None, 0.125), ("oa-key", 1 / 24)])
def test_openalex_is_paced_at_thirty_a_second_only_with_its_key(key: str | None, interval: float) -> None:
    keys = ScholarlyKeys(contact_email=CONTACT, openalex_api_key=key)
    sources = scholarly_sources(keys, Recorder({}).client(), clock=fixed_clock(), pacing=ScholarlyPacing())
    named = {adapter.name: adapter.http for adapter in sources.adapters}
    assert named["openalex"].limits.search.interval == pytest.approx(interval)
    crossref = named["crossref"].limits
    assert crossref.lookup is not None and crossref.lookup.interval == pytest.approx(0.125)
    assert crossref.concurrency == 3


def test_the_answer_pace_is_read_for_the_current_request() -> None:
    assert answer_pace() is None
    with request_id_scope("answer-0104"):
        assert answer_pace() == AnswerPace("answer-0104")
    assert answer_pace("answer-0105") == AnswerPace("answer-0105")


def test_crossref_s_polite_pool_needs_the_contact_address() -> None:
    with pytest.raises(ValueError, match="RESEARCH_CONTACT_EMAIL"):
        CrossrefAdapter(source_http(Recorder({}), "crossref"), contact_email="", clock=fixed_clock())
