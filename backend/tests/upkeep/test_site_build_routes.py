import uuid
from datetime import UTC, datetime
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.api.routes import site_build
from app.core.db import get_session
from app.core.deps import get_current_user
from app.core.errors import ExternalFailure, NotConfigured
from app.main import create_app
from app.models import User
from app.services.site_build import BuildTooSoon, SiteBuildState
from app.services.static_pages import StaticPages
from app.services.web_build_gate import ApiNotLive

from ..contracts.golden import golden_json
from .fakes import CountingHook

LAST = datetime(2026, 11, 19, 23, 50, tzinfo=UTC)


class QuietSession:
    async def commit(self) -> None:
        return None


def client(role: str | None, hook: Any = None) -> TestClient:
    app = create_app()
    if role is not None:
        user = User(id=uuid.UUID(int=5), name="Asha", email="asha@example.org", role=role)
        app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_session] = QuietSession
    app.dependency_overrides[site_build.site_build_hook] = lambda: hook
    app.dependency_overrides[site_build.api_commits] = lambda: None
    return TestClient(app)


@pytest.fixture
def quiet_build(monkeypatch: pytest.MonkeyPatch) -> list[dict[str, Any]]:
    triggered: list[dict[str, Any]] = []

    async def state(session: Any, *, configured: bool, now: datetime) -> SiteBuildState:
        return SiteBuildState(configured, LAST, None)

    async def not_early(session: Any, *, now: datetime) -> None:
        return None

    async def trigger(session: Any, hook: Any, *, actor: Any, origin: str) -> None:
        if hook is None:
            raise NotConfigured("VERCEL_DEPLOY_HOOK_URL", "unset")
        await hook.trigger()
        triggered.append({"actor": actor.role, "origin": origin})

    async def api_live(commits: Any, *, release: str) -> None:
        return None

    monkeypatch.setattr(site_build, "site_build_state", state)
    monkeypatch.setattr(site_build, "refuse_early_build", not_early)
    monkeypatch.setattr(site_build, "refuse_ahead_of_api", api_live)
    monkeypatch.setattr(site_build, "trigger_site_build", trigger)
    return triggered


@pytest.mark.parametrize("role", ["STUDENT", "RESEARCHER", "PROFESSOR"])
def test_below_admin_may_neither_see_nor_start_a_build(role: str, quiet_build: list[dict[str, Any]]) -> None:
    http = client(role, CountingHook())
    assert http.get("/api/site/build").status_code == 403
    assert http.post("/api/site/build").status_code == 403
    assert quiet_build == []


def test_signed_out_readers_cannot_start_a_build(quiet_build: list[dict[str, Any]]) -> None:
    assert client(None, CountingHook()).post("/api/site/build").status_code == 401


@pytest.mark.parametrize("role", ["ADMIN", "MASTER_ADMIN"])
def test_an_admin_starts_one_build(role: str, quiet_build: list[dict[str, Any]]) -> None:
    hook = CountingHook()
    answer = client(role, hook).post("/api/site/build")
    assert answer.status_code == 202
    assert answer.json() == {
        "configured": True,
        "lastTriggeredAt": "2026-11-19T23:50:00+00:00",
        "nextAllowedAt": None,
    }
    assert hook.triggered == 1
    assert quiet_build == [{"actor": role, "origin": "admin"}]


def test_an_unset_hook_is_a_503(quiet_build: list[dict[str, Any]]) -> None:
    answer = client("ADMIN", None).post("/api/site/build")
    assert answer.status_code == 503
    assert "deploy hook" in answer.json()["detail"]


def test_a_second_build_within_the_interval_waits(
    monkeypatch: pytest.MonkeyPatch, quiet_build: list[dict[str, Any]]
) -> None:
    async def early(session: Any, *, now: datetime) -> None:
        raise BuildTooSoon(125.2)

    monkeypatch.setattr(site_build, "refuse_early_build", early)
    hook = CountingHook()
    answer = client("ADMIN", hook).post("/api/site/build")
    assert answer.status_code == 429
    assert answer.headers["Retry-After"] == "126"
    assert hook.triggered == 0


def test_a_build_ahead_of_the_live_api_is_a_409_that_says_why_and_calls_no_hook(
    monkeypatch: pytest.MonkeyPatch, quiet_build: list[dict[str, Any]]
) -> None:
    async def ahead(commits: Any, *, release: str) -> None:
        raise ApiNotLive("Main changes the API since 1ab422fe0000, the release the API runs.")

    monkeypatch.setattr(site_build, "refuse_ahead_of_api", ahead)
    hook = CountingHook()
    answer = client("ADMIN", hook).post("/api/site/build")
    assert answer.status_code == 409
    assert answer.json()["detail"].startswith("Main changes the API since 1ab422fe0000")
    assert (hook.triggered, quiet_build) == (0, [])


def test_the_api_check_unreachable_is_a_502_that_names_the_check_and_calls_no_hook(
    monkeypatch: pytest.MonkeyPatch, quiet_build: list[dict[str, Any]]
) -> None:
    async def unknown(commits: Any, *, release: str) -> None:
        raise ExternalFailure("the check could not be reached", kind="unavailable", service="github")

    monkeypatch.setattr(site_build, "refuse_ahead_of_api", unknown)
    hook = CountingHook()
    answer = client("ADMIN", hook).post("/api/site/build")
    assert answer.status_code == 502 and answer.json()["detail"] == site_build.GATE_FAILED_DETAIL
    assert hook.triggered == 0


def test_a_refused_hook_is_a_502_that_names_no_address(quiet_build: list[dict[str, Any]]) -> None:
    hook = CountingHook(ExternalFailure("the deploy hook answered 404", kind="not_found", status=404))
    answer = client("ADMIN", hook).post("/api/site/build")
    assert answer.status_code == 502
    assert "vercel" not in answer.text.lower()


def test_the_static_page_list_is_public_and_matches_the_shared_golden(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def listed(session: Any) -> StaticPages:
        return StaticPages(
            crafts=("Bagh-Print", "Kutch-Ajrakh", "Sanganeri-Block-Print"),
            categories=("Textile-Craft-Category", "Leather-Craft-Category"),
        )

    monkeypatch.setattr(site_build, "static_pages", listed)
    answer = client(None).get("/api/site/pages")
    assert answer.status_code == 200
    assert answer.json() == golden_json("site.pages.golden.json")
    assert answer.headers["Cache-Control"] == "public, max-age=300"
