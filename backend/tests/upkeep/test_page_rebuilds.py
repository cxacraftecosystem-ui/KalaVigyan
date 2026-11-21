import uuid
from typing import Any

import pytest

from app.core.errors import InvalidInput, NotConfigured
from app.research.page_revalidation import PageOwners
from app.services import upkeep_pages
from app.services.upkeep_pages import (
    PagesReport,
    StalePage,
    rebuild_monographs,
    rebuild_order,
    rebuild_stale_pages,
)

from .fakes import NIGHT


class Loaded:
    def __init__(self, slug: str) -> None:
        self.slug = slug
        self.craft_slug = slug
        self.sections_written: list[str] = []
        self.components_written: list[str] = []

    def as_dict(self) -> dict[str, Any]:
        return {"craftSlug": self.slug}


class Session:
    def __init__(self) -> None:
        self.commits = 0
        self.rollbacks = 0

    async def commit(self) -> None:
        self.commits += 1

    async def rollback(self) -> None:
        self.rollbacks += 1

    async def get(self, model: Any, key: uuid.UUID) -> Any:
        return type("Craft", (), {"id": key})()


async def test_each_monograph_is_loaded_and_a_failing_one_is_rolled_back_alone(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def load_monograph(session: Any, content: str, *, now: Any) -> Loaded:
        if content == "content:b":
            raise InvalidInput("No craft has the slug b")
        return Loaded(content.removeprefix("content:"))

    monkeypatch.setattr(upkeep_pages, "load_monograph", load_monograph)
    session, report = Session(), PagesReport()
    await rebuild_monographs(
        session, ["c", "b", "a"], lambda slug: f"content:{slug}", now=NIGHT, report=report
    )  # type: ignore[arg-type]
    assert report.monographs == [{"craftSlug": "a"}, {"craftSlug": "c"}]
    assert report.failed == ["monograph:b"]
    assert (session.commits, session.rollbacks) == (2, 1)


async def test_a_night_loads_only_its_window_of_monographs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    loaded: list[str] = []

    async def load_monograph(session: Any, content: str, *, now: Any) -> Loaded:
        loaded.append(content)
        return Loaded(content)

    monkeypatch.setattr(upkeep_pages, "load_monograph", load_monograph)
    monkeypatch.setattr(upkeep_pages, "MONOGRAPHS_PER_NIGHT", 2)
    assert NIGHT.date().toordinal() == 739_940
    await rebuild_monographs(Session(), list("edcba"), str, now=NIGHT, report=PagesReport())  # type: ignore[arg-type]
    assert loaded == ["a", "b"]


async def test_the_oldest_stale_pages_are_rebuilt_up_to_the_bound(monkeypatch: pytest.MonkeyPatch) -> None:
    stale = [
        (uuid.UUID(int=n), slug) for n, slug in enumerate(("Bagh-Print", "Bidri-Ware", "Chanderi"), start=1)
    ]
    skipped: list[frozenset[str]] = []

    async def stale_crafts(session: Any, *, skip: frozenset[str]) -> list[tuple[uuid.UUID, str]]:
        skipped.append(skip)
        return stale

    async def rebuild_snapshots(session: Any, craft: Any) -> bool:
        if craft.id == uuid.UUID(int=2):
            raise NotConfigured("page", "the page could not be built")
        return craft.id == uuid.UUID(int=1)

    monkeypatch.setattr(upkeep_pages, "stale_crafts", stale_crafts)
    monkeypatch.setattr(upkeep_pages, "rebuild_snapshots", rebuild_snapshots)
    session, report = Session(), PagesReport()
    await rebuild_stale_pages(session, skip=frozenset({"Kutch-Ajrakh"}), report=report, limit=2)  # type: ignore[arg-type]
    assert skipped == [frozenset({"Kutch-Ajrakh"})]
    assert report.as_dict() == {
        "monographs": [],
        "pagesStale": 3,
        "pagesRebuilt": 1,
        "pagesChanged": 1,
        "pagesFailed": ["page:Bidri-Ware"],
        "documentsStale": 0,
        "documentsRebuilt": 0,
        "documentsChanged": 0,
        "documentsRemoved": 0,
        "documentsFailed": [],
    }
    assert (session.commits, session.rollbacks) == (1, 1)


async def test_stored_documents_rebuilt_after_the_pages_report_their_failures_as_the_pages_do(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def rebuild_stale_documents(session: Any, *, report: Any, limit: int) -> None:
        report.stale = 3
        report.rebuilt.extend(["craft:Bagh-Print", "category:Metal-Craft-Category"])
        report.changed = 1
        report.failed.append("craft:Bidri-Ware")

    monkeypatch.setattr(upkeep_pages, "rebuild_stale_documents", rebuild_stale_documents)
    report = PagesReport()
    await upkeep_pages.rebuild_documents(Session(), report=report, limit=5)  # type: ignore[arg-type]
    shown = report.as_dict()
    assert (shown["documentsStale"], shown["documentsRebuilt"], shown["documentsChanged"]) == (3, 2, 1)
    assert shown["pagesFailed"] == ["document:craft:Bidri-Ware"]
    assert shown["documentsFailed"] == ["craft:Bidri-Ware"]


async def test_only_a_monograph_that_wrote_sections_or_components_names_its_craft_changed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def load_monograph(session: Any, content: str, *, now: Any) -> Loaded:
        loaded = Loaded(content)
        if content == "a":
            loaded.sections_written.append("chemistry")
        if content == "c":
            loaded.components_written.append("dip-player")
        return loaded

    monkeypatch.setattr(upkeep_pages, "load_monograph", load_monograph)
    report = PagesReport()
    await rebuild_monographs(Session(), ["a", "b", "c"], lambda slug: slug, now=NIGHT, report=report)  # type: ignore[arg-type]
    assert report.changed_crafts == ["a", "c"]


def test_curated_crafts_are_rebuilt_first_then_the_oldest() -> None:
    early, late = NIGHT.replace(hour=1), NIGHT.replace(hour=2)
    pages = [
        StalePage(uuid.UUID(int=1), "Agra-Durrie", early, curated=False),
        StalePage(uuid.UUID(int=2), "Bidriware", late, curated=True),
        StalePage(uuid.UUID(int=3), "Bastar-Dhokra", late, curated=True),
        StalePage(uuid.UUID(int=4), "Aari-Work", late, curated=False),
    ]
    assert [page.slug for page in rebuild_order(pages)] == [
        "Bastar-Dhokra",
        "Bidriware",
        "Agra-Durrie",
        "Aari-Work",
    ]


def test_the_night_s_changed_pages_are_the_crafts_and_documents_that_moved_once_each() -> None:
    report = PagesReport(changed_crafts=["Kutch-Ajrakh", "Bagru-Prints"])
    report.documents.moved.extend(["craft:Kutch-Ajrakh", "category:Textiles-Based-Craft-Category"])
    assert report.changed_owners() == PageOwners(
        crafts=("Bagru-Prints", "Kutch-Ajrakh"), categories=("Textiles-Based-Craft-Category",)
    )
    assert PagesReport().changed_owners().empty
