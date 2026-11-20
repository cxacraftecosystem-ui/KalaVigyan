import asyncio
import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

import pytest

from app.scripts import rebuild_stale_pages as script


class Session:
    def __init__(self) -> None:
        self.rolled_back = False

    async def rollback(self) -> None:
        self.rolled_back = True


def patched(monkeypatch: pytest.MonkeyPatch, rebuild: Any) -> Session:
    session = Session()

    @asynccontextmanager
    async def scope() -> AsyncIterator[Session]:
        yield session

    async def disposed() -> None:
        return None

    monkeypatch.setattr(script, "session_scope", scope)
    monkeypatch.setattr(script, "dispose_engine", disposed)
    monkeypatch.setattr(script, "rebuild_stale_pages", rebuild)
    return session


def test_every_stale_page_is_rebuilt_and_reported(monkeypatch: pytest.MonkeyPatch, capsys: Any) -> None:
    asked: dict[str, Any] = {}

    async def rebuild(session: Session, *, skip: Any, report: Any, limit: int) -> None:
        asked.update(skip=tuple(skip), limit=limit)
        report.pages_stale = 2
        report.pages_rebuilt.extend(["Bidriware", "Bastar-Dhokra"])

    patched(monkeypatch, rebuild)
    assert script.main(["--seconds", "5"]) == 0
    printed = json.loads(capsys.readouterr().out)
    assert (printed["pagesStale"], printed["pagesRebuilt"], printed["finished"]) == (2, 2, True)
    assert asked == {"skip": (), "limit": 100_000}


def test_a_rebuild_that_runs_out_of_time_stops_and_says_so(monkeypatch: pytest.MonkeyPatch) -> None:
    async def rebuild(session: Session, *, skip: Any, report: Any, limit: int) -> None:
        report.pages_rebuilt.append("Bidriware")
        await asyncio.sleep(5)

    session = patched(monkeypatch, rebuild)
    report = asyncio.run(script.run(0.05))
    assert (report["pagesRebuilt"], report["finished"], session.rolled_back) == (1, False, True)
