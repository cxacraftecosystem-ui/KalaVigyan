import asyncio
import uuid
from collections.abc import Callable
from datetime import UTC, datetime, timedelta

from app.media.queue import MediaQueue


class Store:
    def __init__(self, waiting: dict[str, list[uuid.UUID]], stale: list[uuid.UUID] | None = None) -> None:
        self.waiting = waiting
        self.stale_ids = stale or []
        self.asked: list[tuple[str, int]] = []
        self.renewals: list[datetime] = []

    async def stale(self, older_than: datetime) -> list[uuid.UUID]:
        found, self.stale_ids = self.stale_ids, []
        return found

    async def renew_holds(self, older_than: datetime) -> int:
        self.renewals.append(older_than)
        return 0

    async def claim(self, kind: str, *, limit: int, worker_id: str) -> list[uuid.UUID]:
        self.asked.append((kind, limit))
        taken, self.waiting[kind] = self.waiting[kind][:limit], self.waiting[kind][limit:]
        return taken


def queue(
    store: Store,
    gate: asyncio.Event,
    ran: list[uuid.UUID],
    abandoned: list[uuid.UUID],
    clock: Callable[[], datetime] = lambda: datetime.now(UTC),
) -> MediaQueue:
    async def run(job_id: uuid.UUID) -> str:
        ran.append(job_id)
        await gate.wait()
        return "SUCCEEDED"

    async def abandon(job_id: uuid.UUID) -> str:
        abandoned.append(job_id)
        return "QUEUED"

    return MediaQueue(
        store=store,
        run=run,
        abandon=abandon,
        worker_id="test",
        clock=clock,
        idle_seconds=0.01,
        drain_seconds=0.05,
    )


async def test_each_queue_runs_at_most_its_concurrency() -> None:
    store = Store({"IMAGE": [uuid.uuid4() for _ in range(6)], "VIDEO": [uuid.uuid4() for _ in range(3)]})
    gate, ran, abandoned = asyncio.Event(), [], []
    worker = queue(store, gate, ran, abandoned)
    assert await worker.tick() == 6
    assert store.asked == [("IMAGE", 4), ("VIDEO", 2)]
    assert (worker.running("IMAGE"), worker.running("VIDEO")) == (4, 2)
    assert await worker.tick() == 0
    gate.set()
    await asyncio.sleep(0)
    await asyncio.sleep(0)
    assert await worker.tick() == 3
    await worker.drain()


async def test_queued_holds_older_than_half_their_life_are_renewed_once_a_minute() -> None:
    store = Store({"IMAGE": [], "VIDEO": []})
    moments = [datetime(2026, 11, 23, 6, 0, tzinfo=UTC)]
    worker = queue(store, asyncio.Event(), [], [], clock=lambda: moments[-1])
    await worker.tick()
    moments.append(moments[0] + timedelta(seconds=59))
    await worker.tick()
    moments.append(moments[0] + timedelta(seconds=60))
    await worker.tick()
    assert store.renewals == [
        moments[0] - timedelta(minutes=7, seconds=30),
        moments[2] - timedelta(minutes=7, seconds=30),
    ]


async def test_stale_jobs_are_abandoned_before_new_claims() -> None:
    stuck = uuid.uuid4()
    store = Store({"IMAGE": [], "VIDEO": []}, stale=[stuck])
    worker = queue(store, asyncio.Event(), [], abandoned := [])
    await worker.tick()
    assert abandoned == [stuck]


async def test_stopping_drains_running_jobs_and_cancels_the_rest() -> None:
    store = Store({"IMAGE": [uuid.uuid4()], "VIDEO": []})
    gate, ran = asyncio.Event(), []
    worker = queue(store, gate, ran, [])
    stop = asyncio.Event()
    running = asyncio.create_task(worker.run(stop))
    await asyncio.sleep(0.05)
    stop.set()
    await asyncio.wait_for(running, timeout=5)
    assert len(ran) == 1 and worker.running("IMAGE") == 0
