import asyncio
import uuid
from collections.abc import AsyncIterator

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.db import sessionmaker
from app.core.paces import LeaseAsk, PaceAsk, PaceLane, PaceUnread, SharedPaces
from app.models import SourceLease, SourcePace
from app.sources.http import RatePolicy
from app.sources.scholarly.crossref import CROSSREF_LIMITS
from app.sources.scholarly.pacing import PacedHttp, ScholarlyPacing

from ..sources.recorded import FakeClock, Recorder, Reply

pytestmark = pytest.mark.db

UNREACHABLE = "postgresql+psycopg://nobody:nothing@127.0.0.1:1/nowhere"
TEN_APART = PaceAsk(interval=10.0, queue_max=1000.0, hold_max=10.0)


def fresh_service() -> str:
    return f"t{uuid.uuid4().hex}"


@pytest.fixture
async def two_processes() -> AsyncIterator[tuple[SharedPaces, SharedPaces]]:
    first, second = SharedPaces(), SharedPaces()
    yield first, second
    for paces in (first, second):
        await paces.dispose()


async def stored(lane: PaceLane) -> SourcePace | None:
    async with sessionmaker()() as session:
        return await session.get(SourcePace, (lane.service, lane.lane))


async def leases_of(service: str) -> int:
    counted = select(func.count()).select_from(SourceLease).where(SourceLease.service == service)
    async with sessionmaker()() as session:
        return int(await session.scalar(counted) or 0)


async def test_two_processes_leasing_at_once_never_hold_more_than_the_concurrency(
    two_processes: tuple[SharedPaces, SharedPaces],
) -> None:
    service = fresh_service()
    three = LeaseAsk(concurrency=3, seconds=60.0)
    leases = await asyncio.gather(*(two_processes[n % 2].lease(service, three) for n in range(8)))
    granted = [lease for lease in leases if lease is not None]
    assert len(granted) == 3
    assert await leases_of(service) == 3
    await two_processes[1].release(granted[0])
    assert await two_processes[0].lease(service, three) is not None
    assert await two_processes[0].lease(service, three) is None


async def test_an_expired_lease_frees_its_slot_and_a_release_sweeps_it(
    two_processes: tuple[SharedPaces, SharedPaces],
) -> None:
    first, second = two_processes
    service = fresh_service()
    assert await first.lease(service, LeaseAsk(concurrency=1, seconds=0.0)) is not None
    held = await second.lease(service, LeaseAsk(concurrency=1, seconds=60.0))
    assert held is not None
    assert await leases_of(service) == 2
    await first.release(held)
    assert await leases_of(service) == 0


async def test_two_processes_reserving_at_once_get_slots_one_interval_apart(
    two_processes: tuple[SharedPaces, SharedPaces],
) -> None:
    lane = PaceLane(fresh_service(), "search")
    slots = await asyncio.gather(*(two_processes[n % 2].reserve(lane, TEN_APART) for n in range(8)))
    assert sorted(round((slot.wait or 0.0) / 10.0) for slot in slots) == list(range(8))
    row = await stored(lane)
    assert row is not None
    assert (row.freeAt - row.heldUntil).total_seconds() == pytest.approx(80.0)


async def test_a_hold_written_by_one_process_is_honoured_by_the_other(
    two_processes: tuple[SharedPaces, SharedPaces],
) -> None:
    first, second = two_processes
    service = fresh_service()
    search, lookup = PaceLane(service, "search"), PaceLane(service, "lookup")
    assert (await first.reserve(search, TEN_APART)).wait == pytest.approx(0.0, abs=0.5)
    await first.hold([search, lookup], 30.0)
    refused = await second.reserve(lookup, TEN_APART)
    assert refused.wait is None
    assert refused.held_for == pytest.approx(30.0, abs=1.0)
    patient = PaceAsk(interval=10.0, queue_max=60.0, hold_max=60.0)
    assert (await second.reserve(search, patient)).wait == pytest.approx(30.0, abs=1.0)


async def test_a_reservation_past_the_queue_takes_no_slot(
    two_processes: tuple[SharedPaces, SharedPaces],
) -> None:
    first, second = two_processes
    lane = PaceLane(fresh_service(), "search")
    short_queue = PaceAsk(interval=20.0, queue_max=30.0, hold_max=10.0)
    waits = [(await paces.reserve(lane, short_queue)).wait for paces in (first, second, first)]
    assert waits[2] is None
    assert [round(wait or 0.0) for wait in waits[:2]] == [0, 20]
    long_queue = PaceAsk(interval=20.0, queue_max=100.0, hold_max=10.0)
    assert round((await second.reserve(lane, long_queue)).wait or 0.0) == 40


async def test_two_paced_clients_on_the_shared_store_space_crossref_searches(
    two_processes: tuple[SharedPaces, SharedPaces],
) -> None:
    recorder = Recorder({"api.crossref.org/works": Reply("crossref_search.json")})
    clock = FakeClock()
    service = fresh_service()
    clients = [
        PacedHttp(
            client=recorder.client(),
            service=service,
            policy=RatePolicy(min_interval=0.0),
            clock=clock,
            sleep=clock.sleep,
            limits=CROSSREF_LIMITS,
            pacing=ScholarlyPacing(paces),
        )
        for paces in two_processes
    ]
    for client, query in zip(clients, ("khurja glaze", "khurja clay"), strict=True):
        await client.get("https://api.crossref.org/works", params={"query": query})
    assert len(clock.slept) == 1
    assert 5 / 12 - 0.3 < clock.slept[0] <= 5 / 12 + 1e-6
    assert len(recorder.requests) == 2


async def test_a_pace_that_cannot_reach_the_database_is_unread() -> None:
    engine = create_async_engine(UNREACHABLE, connect_args={"connect_timeout": 2})
    try:
        with pytest.raises(PaceUnread):
            await SharedPaces(async_sessionmaker(engine)).reserve(
                PaceLane(fresh_service(), "search"), TEN_APART
            )
    finally:
        await engine.dispose()
