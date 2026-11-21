import asyncio
import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import pytest

from app.research.page_revalidation import PageOwners
from app.scripts import refresh_served_pages as script
from app.services.page_revalidation import BatchedRefresh, merged_owners

PAGES = {"page:craft:Kutch-Ajrakh": "e1", "page:craft:Bagh-Print": "e2"}
DOCUMENTS = {"document:craft:Kutch-Ajrakh": "v3-aa", "document:category:textiles": "v1-cc"}


class Session:
    async def rollback(self) -> None:
        return None


class Web:
    def __init__(self, *, refuses: PageOwners = PageOwners()) -> None:
        self.asked: list[PageOwners] = []
        self.refuses = refuses

    async def refresh(self, owners: PageOwners) -> BatchedRefresh:
        self.asked.append(owners)
        refused = PageOwners(
            crafts=tuple(slug for slug in owners.crafts if slug in self.refuses.crafts),
            categories=tuple(slug for slug in owners.categories if slug in self.refuses.categories),
        )
        done = PageOwners(
            crafts=tuple(slug for slug in owners.crafts if slug not in refused.crafts),
            categories=tuple(slug for slug in owners.categories if slug not in refused.categories),
        )
        return BatchedRefresh(merged_owners(done), merged_owners(refused), 1, 1)


def patched(monkeypatch: pytest.MonkeyPatch, served: dict[str, str], web: Web, *, slow: bool = False) -> None:
    @asynccontextmanager
    async def scope() -> AsyncIterator[Session]:
        yield Session()

    async def disposed() -> None:
        return None

    async def measure(session: Session, pages: Any) -> None:
        pages.digests.update({key: value for key, value in served.items() if key.startswith("page:")})
        if slow:
            pages.unmeasured.update({"craft:Kutch-Ajrakh", "category:textiles"})
            await asyncio.sleep(5)
        pages.digests.update({key: value for key, value in served.items() if key.startswith("document:")})
        pages.measured.update({"craft:Kutch-Ajrakh": 0.4, "category:textiles": 1.2})

    monkeypatch.setattr(script, "session_scope", scope)
    monkeypatch.setattr(script, "dispose_engine", disposed)
    monkeypatch.setattr(script, "measure_served", measure)
    monkeypatch.setattr(script, "refresh_in_batches", web.refresh)


def run(state: Path, capsys: Any) -> dict[str, Any]:
    assert script.main(["--state", str(state), "--seconds", "5"]) == 0
    return json.loads(capsys.readouterr().out)


def test_a_first_release_refreshes_every_page_and_records_what_it_served(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: Any
) -> None:
    web = Web()
    patched(monkeypatch, {**PAGES, **DOCUMENTS}, web)
    state = tmp_path / "served-pages.json"
    report = run(state, capsys)
    assert web.asked == [PageOwners(crafts=("Bagh-Print", "Kutch-Ajrakh"), categories=("textiles",))]
    assert (report["record"], report["finished"], report["changed"]) == (
        "missing",
        True,
        {"crafts": 2, "categories": 1},
    )
    assert json.loads(state.read_text(encoding="utf-8"))["digests"] == dict(
        sorted({**PAGES, **DOCUMENTS}.items())
    )


def test_a_release_that_changed_nothing_refreshes_nothing(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: Any
) -> None:
    state = tmp_path / "served-pages.json"
    state.write_text(json.dumps({"schemaVersion": 1, "digests": {**PAGES, **DOCUMENTS}}), encoding="utf-8")
    web = Web()
    patched(monkeypatch, {**PAGES, **DOCUMENTS}, web)
    report = run(state, capsys)
    assert web.asked == [PageOwners()]
    assert (report["record"], report["changed"], report["refreshed"]) == (
        "read",
        {"crafts": 0, "categories": 0},
        {"crafts": 0, "categories": 0},
    )


def test_a_changed_document_is_refreshed_and_a_refused_one_is_tried_again_next_time(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: Any
) -> None:
    state = tmp_path / "served-pages.json"
    state.write_text(json.dumps({"schemaVersion": 1, "digests": {**PAGES, **DOCUMENTS}}), encoding="utf-8")
    web = Web(refuses=PageOwners(categories=("textiles",)))
    changed = {**PAGES, "document:craft:Kutch-Ajrakh": "v4-ab", "document:category:textiles": "v2-cd"}
    patched(monkeypatch, changed, web)
    report = run(state, capsys)
    assert web.asked == [PageOwners(crafts=("Kutch-Ajrakh",), categories=("textiles",))]
    assert report["notRefreshed"] == {"crafts": 0, "categories": 1}
    kept = json.loads(state.read_text(encoding="utf-8"))["digests"]
    assert (kept["document:craft:Kutch-Ajrakh"], kept["document:category:textiles"]) == ("v4-ab", "v1-cc")


def test_documents_not_read_in_time_are_refreshed_and_the_run_says_it_stopped(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    state = tmp_path / "served-pages.json"
    state.write_text(json.dumps({"schemaVersion": 1, "digests": {**PAGES, **DOCUMENTS}}), encoding="utf-8")
    web = Web()
    patched(monkeypatch, {**PAGES, **DOCUMENTS}, web, slow=True)
    report = asyncio.run(script.run(state, 0.05))
    assert report["finished"] is False
    assert web.asked == [PageOwners(crafts=("Kutch-Ajrakh",), categories=("textiles",))]


def test_an_unreadable_record_is_named_and_every_page_is_refreshed(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: Any
) -> None:
    state = tmp_path / "served-pages.json"
    state.write_text("{", encoding="utf-8")
    web = Web()
    patched(monkeypatch, {**PAGES, **DOCUMENTS}, web)
    report = run(state, capsys)
    assert report["record"].startswith("unreadable")
    assert web.asked == [PageOwners(crafts=("Bagh-Print", "Kutch-Ajrakh"), categories=("textiles",))]
