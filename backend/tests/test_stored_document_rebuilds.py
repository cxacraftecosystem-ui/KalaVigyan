from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from types import SimpleNamespace
from typing import Any

import pytest

from app.core.errors import InvalidInput
from app.research.page_revalidation import PageOwners
from app.services import stored_document_rebuilds as rebuilds
from app.services.stored_documents import Rebuilt


class Seen:
    def __init__(self) -> None:
        self.rebuilt: list[str] = []
        self.refreshed: list[PageOwners] = []


def patched(
    monkeypatch: pytest.MonkeyPatch, *, here: bool = True, locked: bool = True, outcome: Any = Rebuilt.CHANGED
) -> Seen:
    seen = Seen()

    @asynccontextmanager
    async def scope() -> AsyncIterator[object]:
        yield object()

    async def rebuilds_here(session: Any) -> bool:
        return here

    async def lock(session: Any) -> bool:
        return locked

    async def subject(session: Any, kind: str, slug: str) -> Any:
        if slug == "No-Such-Craft":
            raise InvalidInput("No craft has the slug No-Such-Craft.")
        return SimpleNamespace(kind=kind, slug=slug)

    async def rebuild(session: Any, subject: Any, *, now: Any) -> Rebuilt:
        seen.rebuilt.append(f"{subject.kind}:{subject.slug}")
        return outcome

    async def refresh(owners: PageOwners) -> bool:
        seen.refreshed.append(owners)
        return True

    monkeypatch.setattr(rebuilds, "session_scope", scope)
    monkeypatch.setattr(rebuilds, "rebuilds_here", rebuilds_here)
    monkeypatch.setattr(rebuilds, "_rebuild_lock", lock)
    monkeypatch.setattr(rebuilds, "subject_by_key", subject)
    monkeypatch.setattr(rebuilds, "rebuild_document", rebuild)
    monkeypatch.setattr(rebuilds, "refresh_pages", refresh)
    return seen


async def test_a_queued_rebuild_that_changes_a_craft_refreshes_its_page(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen = patched(monkeypatch)
    await rebuilds.rebuild_wanted("craft", "Bagh-Print")
    assert seen.rebuilt == ["craft:Bagh-Print"]
    assert seen.refreshed == [PageOwners(crafts=("Bagh-Print",))]


async def test_a_category_rebuild_refreshes_the_category_and_an_unchanged_one_refreshes_nothing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen = patched(monkeypatch, outcome=Rebuilt.REMOVED)
    await rebuilds.rebuild_wanted("category", "Metal-Craft-Category")
    assert seen.refreshed == [PageOwners(categories=("Metal-Craft-Category",))]
    quiet = patched(monkeypatch, outcome=Rebuilt.UNCHANGED)
    await rebuilds.rebuild_wanted("family", "Applique")
    assert (quiet.rebuilt, quiet.refreshed) == (["family:Applique"], [])


@pytest.mark.parametrize(("here", "locked"), [(False, True), (True, False)], ids=["older release", "busy"])
async def test_another_release_or_a_running_rebuild_leaves_the_read_s_request_for_later(
    monkeypatch: pytest.MonkeyPatch, here: bool, locked: bool
) -> None:
    seen = patched(monkeypatch, here=here, locked=locked)
    await rebuilds.rebuild_wanted("craft", "Bagh-Print")
    assert (seen.rebuilt, seen.refreshed) == ([], [])


async def test_a_subject_gone_since_the_read_is_logged_and_nothing_is_refreshed(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    seen = patched(monkeypatch)
    await rebuilds.rebuild_wanted("craft", "No-Such-Craft")
    assert (seen.rebuilt, seen.refreshed) == ([], [])
    assert "could not be rebuilt after a read" in caplog.text


def test_a_rebuilt_document_moved_only_when_it_was_built_changed_or_removed() -> None:
    assert [outcome.value for outcome in Rebuilt if outcome.moved] == ["built", "changed", "removed"]
