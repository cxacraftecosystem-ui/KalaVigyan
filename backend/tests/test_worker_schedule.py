import asyncio
import socket
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy.exc import SQLAlchemyError

from app.core.errors import ExternalFailure
from app.core.service_notify import notify_service
from app.worker import beating, every_day


async def test_the_daily_job_runs_at_start_and_again_after_its_interval() -> None:
    stop = asyncio.Event()
    runs: list[int] = []

    async def job() -> dict[str, Any]:
        runs.append(len(runs) + 1)
        if len(runs) == 2:
            stop.set()
        return {"ok": True}

    assert await every_day(stop, job, name="daily voice upkeep", every_seconds=0.01) == 2
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

    assert await every_day(stop, job, name="daily voice upkeep", every_seconds=0.01) == 2


async def test_a_stopped_worker_runs_no_daily_job() -> None:
    stop = asyncio.Event()
    stop.set()

    async def job() -> dict[str, Any]:
        raise AssertionError("a stopped worker starts nothing")

    assert await every_day(stop, job, name="daily score sweep") == 0


async def test_the_heartbeat_keeps_beating_when_one_write_fails_and_pings_the_watchdog_each_time(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    stop = asyncio.Event()
    address = str(tmp_path / "notify")
    heard = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
    heard.bind(address)
    monkeypatch.setenv("NOTIFY_SOCKET", address)
    tries: list[str] = []

    async def heartbeat() -> None:
        tries.append("beat")
        if len(tries) == 1:
            raise SQLAlchemyError("the database went away")
        if len(tries) == 3:
            stop.set()

    with heard:
        assert await beating(stop, heartbeat, every_seconds=0.01) == 2
        pings = [heard.recv(64) for _ in tries]
    assert tries == ["beat"] * 3 and pings == [b"WATCHDOG=1"] * 3


def test_without_a_notify_socket_nothing_is_sent() -> None:
    assert notify_service("READY=1", environ={}) is False
