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


async def no_documents(session: Session, *, report: Any, limit: int) -> None:
    return None


async def no_monographs(session: Session, slugs: Any, load: Any, *, now: Any, report: Any) -> None:
    return None


def patched(
    monkeypatch: pytest.MonkeyPatch,
    rebuild: Any,
    documents: Any = no_documents,
    monographs: Any = no_monographs,
) -> Session:
    session = Session()

    @asynccontextmanager
    async def scope() -> AsyncIterator[Session]:
        yield session

    async def disposed() -> None:
        return None

    monkeypatch.setattr(script, "session_scope", scope)
    monkeypatch.setattr(script, "dispose_engine", disposed)
    monkeypatch.setattr(script, "rebuild_stale_pages", rebuild)
    monkeypatch.setattr(script, "rebuild_documents", documents)
    monkeypatch.setattr(script, "rebuild_monographs", monographs)
    monkeypatch.setattr(script, "page_code_fingerprint", lambda: "c1")
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
    assert printed["pageCode"] == "c1"
    assert asked == {"skip": (), "limit": 100_000}


def test_a_rebuild_that_runs_out_of_time_stops_and_says_so(monkeypatch: pytest.MonkeyPatch) -> None:
    async def rebuild(session: Session, *, skip: Any, report: Any, limit: int) -> None:
        report.pages_rebuilt.append("Bidriware")
        await asyncio.sleep(5)

    session = patched(monkeypatch, rebuild)
    report = asyncio.run(script.run(0.05, 5))
    assert (report["pagesRebuilt"], report["finished"], session.rolled_back) == (1, False, True)
    assert report["documentsFinished"] is True


def test_stored_documents_are_rebuilt_after_the_snapshots_within_their_own_time(
    monkeypatch: pytest.MonkeyPatch, capsys: Any
) -> None:
    order: list[str] = []

    async def rebuild(session: Session, *, skip: Any, report: Any, limit: int) -> None:
        order.append("snapshots")

    async def documents(session: Session, *, report: Any, limit: int) -> None:
        order.append(f"documents {limit}")
        report.documents.rebuilt.extend(["craft:Bidriware", "category:Metal-Craft-Category"])
        report.documents.changed = 1
        await asyncio.sleep(5)

    session = patched(monkeypatch, rebuild, documents)
    assert script.main(["--seconds", "5", "--document-seconds", "0.05"]) == 0
    printed = json.loads(capsys.readouterr().out)
    assert order == ["snapshots", "documents 100000"]
    assert (printed["finished"], printed["documentsFinished"], session.rolled_back) == (True, False, True)
    assert (printed["documentsRebuilt"], printed["documentsChanged"]) == (2, 1)


def test_a_release_stores_each_authored_monograph_from_its_files_before_the_snapshots(
    monkeypatch: pytest.MonkeyPatch, capsys: Any
) -> None:
    order: list[str] = []

    async def monographs(session: Session, slugs: Any, load: Any, *, now: Any, report: Any) -> None:
        order.append(f"monographs {','.join(slugs)}")
        assert load is script.monograph_content
        report.monographs.append({"craftSlug": "Kutch-Ajrakh", "documentVersion": 6})

    async def rebuild(session: Session, *, skip: Any, report: Any, limit: int) -> None:
        order.append("snapshots")

    patched(monkeypatch, rebuild, monographs=monographs)
    assert script.main(["--seconds", "5"]) == 0
    printed = json.loads(capsys.readouterr().out)
    assert order == ["monographs Kutch-Ajrakh", "snapshots"]
    assert printed["monographs"] == [{"craftSlug": "Kutch-Ajrakh", "documentVersion": 6}]
