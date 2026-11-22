import asyncio
from typing import Any

from app.core.errors import ExternalFailure
from app.worker import every_day


async def test_the_daily_job_runs_at_start_and_again_after_its_interval() -> None:
    stop = asyncio.Event()
    runs: list[int] = []

    async def job() -> dict[str, Any]:
        runs.append(len(runs) + 1)
        if len(runs) == 2:
            stop.set()
        return {"ok": True}

    assert await every_day(stop, job, every_seconds=0.01) == 2
    assert runs == [1, 2]


async def test_a_failed_run_waits_for_the_next_day_instead_of_stopping_the_worker() -> None:
    stop = asyncio.Event()
    runs: list[str] = []

    async def job() -> dict[str, Any]:
        runs.append("run")
        if len(runs) == 1:
            raise ExternalFailure("ElevenLabs did not answer", kind="unavailable", service="elevenlabs")
        stop.set()
        return {"ok": False}

    assert await every_day(stop, job, every_seconds=0.01) == 2


async def test_a_stopped_worker_runs_no_daily_job() -> None:
    stop = asyncio.Event()
    stop.set()

    async def job() -> dict[str, Any]:
        raise AssertionError("a stopped worker starts nothing")

    assert await every_day(stop, job) == 0
