import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.api import mcp_page_tools, mcp_picture_tools
from app.api.mcp_tools import ToolContext, answer
from app.api.proposal_limits import refuse_tool_when_spent, wait_words
from app.api.routes import knowledge_writes
from app.core.db import get_session
from app.core.deps import get_current_user
from app.core.mcp_scopes import CONTRIBUTE_SCOPE, READ_SCOPE
from app.core.rate_limit import (
    COMPONENT_PROPOSALS,
    FACT_PROPOSALS,
    IMAGE_UPLOADS,
    LAYOUT_PROPOSALS,
    PAGE_PREVIEWS,
    PAGE_PROPOSALS,
    STRUCTURE_PROPOSALS,
    proposal_attempt,
)
from app.main import create_app
from app.models import User
from app.research.page_proposals import PageBundle
from app.services import page_proposals, upload_links
from app.services.craft_resolver import CraftIndexStore
from app.services.open_work_subjects import WorkSubject
from app.services.page_proposals import PageTools

from ..research.general_spec_fixtures import TABLE

HOUR = 3600
LIMITS = {
    FACT_PROPOSALS: 30,
    COMPONENT_PROPOSALS: 10,
    LAYOUT_PROPOSALS: 10,
    IMAGE_UPLOADS: 20,
    STRUCTURE_PROPOSALS: 20,
    PAGE_PROPOSALS: 10,
    PAGE_PREVIEWS: 30,
}
SUBJECT = {"kind": "craft", "slug": "Kutch-Ajrakh"}
BUNDLE = {
    "bundle": {
        "subject": SUBJECT,
        "layout": {"base_version": 0, "entries": []},
        "pictures": [{"contribution_id": str(uuid.UUID(int=9))}],
    }
}
AJRAKH = WorkSubject(uuid.UUID(int=2), "craft", "Kutch-Ajrakh", "Kutch Ajrakh", gi=True)
COMPONENT = {
    "label": "kutch-ajrakh/chemistry/vat-surface",
    "title": "Indigo vat surface",
    "description": "Shows the blue film forming where the vat meets the air, step by step, with its reaction.",
    "kind": "general_table",
    "field": "CHEMISTRY",
    "craftSlug": "Kutch-Ajrakh",
    "subjects": [{"kind": "CRAFT", "key": "Kutch-Ajrakh"}],
    "spec": TABLE,
    "units": {ref: {"text": "Alum"} for ref in ("u0001", "u0002", "u0003", "u0004", "u0005", "u0006")},
}


class Nested:
    async def __aenter__(self) -> Nested:
        return self

    async def __aexit__(self, *problem: Any) -> bool:
        return False


def person(role: str, number: int = 31) -> User:
    return User(id=uuid.UUID(int=number), name=f"{role} person", email=f"{number}@example.org", role=role)


def spend(kind: str, user: User) -> None:
    for _ in range(LIMITS[kind]):
        assert proposal_attempt(kind, user)[0] is True


class FakeSession:
    async def commit(self) -> None:
        return None

    def begin_nested(self) -> Nested:
        return Nested()

    async def rollback(self) -> None:
        return None


def context(user: User) -> ToolContext:
    session: Any = FakeSession()
    scopes = frozenset({READ_SCOPE, CONTRIBUTE_SCOPE})
    return ToolContext(
        session=session, index=CraftIndexStore(), site="https://k.example", user=user, scopes=scopes
    )


async def tool_text(name: str, arguments: dict[str, Any], user: User) -> dict[str, Any]:
    message = {
        "jsonrpc": "2.0",
        "id": 9,
        "method": "tools/call",
        "params": {"name": name, "arguments": arguments},
    }
    reply = await answer(message, context(user))
    assert reply is not None and "result" in reply, reply
    return reply["result"]


def client(user: User) -> TestClient:
    app = create_app()
    app.dependency_overrides[get_current_user] = lambda: user

    async def opened() -> AsyncIterator[Any]:
        yield FakeSession()

    app.dependency_overrides[get_session] = opened
    return TestClient(app)


def never_called(*_: Any, **__: Any) -> Any:
    raise AssertionError("the limited work ran")


@pytest.mark.parametrize("kind", sorted(LIMITS))
def test_an_account_makes_its_kind_s_limit_in_an_hour_then_waits(kind: str) -> None:
    researcher = person("RESEARCHER")
    spend(kind, researcher)
    allowed, wait = proposal_attempt(kind, researcher)
    assert allowed is False and 0 < wait <= HOUR
    assert proposal_attempt(kind, person("RESEARCHER", 32))[0] is True
    other = next(each for each in LIMITS if each != kind)
    assert proposal_attempt(other, researcher)[0] is True


@pytest.mark.parametrize("role", ["ADMIN", "MASTER_ADMIN"])
def test_admins_are_never_limited(role: str) -> None:
    admin = person(role)
    for _ in range(LIMITS[FACT_PROPOSALS] + 5):
        assert proposal_attempt(FACT_PROPOSALS, admin) == (True, 0.0)


@pytest.mark.parametrize(
    ("seconds", "words"),
    [
        (0.2, "1 second"),
        (59.0, "59 seconds"),
        (60.0, "1 minute"),
        (61.0, "2 minutes"),
        (3599.0, "60 minutes"),
    ],
)
def test_the_wait_is_said_in_whole_seconds_or_minutes(seconds: float, words: str) -> None:
    assert wait_words(seconds) == words


async def test_spent_component_and_layout_limits_refuse_their_bundle_parts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    researcher = person("RESEARCHER", 34)
    for kind in (COMPONENT_PROPOSALS, LAYOUT_PROPOSALS):
        spend(kind, researcher)

    async def subject(session: Any, kind: str, slug: str) -> WorkSubject:
        return AJRAKH

    monkeypatch.setattr(page_proposals, "subject_by_key", subject)
    monkeypatch.setattr(page_proposals, "propose_component", never_called)
    monkeypatch.setattr(page_proposals, "propose_layout", never_called)
    nothing: Any = never_called
    tools = PageTools(
        gates=nothing,
        fetcher=nothing,
        start_picture=never_called,
        spend=lambda kind: refuse_tool_when_spent(kind, researcher),
        origin="AGENT",
        site="https://k.example",
    )
    bundle = PageBundle.model_validate(
        {
            "subject": SUBJECT,
            "components": [{"proposal": COMPONENT}],
            "layout": {"baseVersion": 0, "entries": []},
        }
    )
    session: Any = FakeSession()
    result = await page_proposals.propose_page(
        session, researcher, bundle, tools=tools, now=datetime(2026, 11, 21, tzinfo=UTC)
    )
    component, layout = result.parts
    assert (component.outcome, layout.outcome) == ("REFUSED", "REFUSED")
    assert "10 component proposals" in component.message and "10 layout proposals" in layout.message


async def test_a_spent_picture_limit_refuses_the_upload_before_a_slot_is_opened(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    researcher = person("RESEARCHER", 35)
    monkeypatch.setattr(upload_links, "start_upload", never_called)
    monkeypatch.setattr(mcp_picture_tools, "endpoints_or_none", lambda: None)
    spend(IMAGE_UPLOADS, researcher)
    picture = {"upload": True, "claim_ids": [str(uuid.UUID(int=5))]}
    result = await tool_text(
        "give_pictures", {"craft_slug": "Kutch-Ajrakh", "pictures": [picture]}, researcher
    )
    (place,) = result["structuredContent"]["uploads"]
    assert result["isError"] is False and "20 picture uploads" in place["refused"]


async def test_page_bundles_and_page_previews_have_their_own_hourly_allowances(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    researcher = person("RESEARCHER")
    monkeypatch.setattr(mcp_page_tools, "page_proposed", never_called)
    monkeypatch.setattr(mcp_page_tools.page_preview, "preview_page", never_called)
    spend(PAGE_PROPOSALS, researcher)
    proposed = await tool_text("propose_page", BUNDLE, researcher)
    assert proposed["isError"] is True and "10 page bundles" in proposed["content"][0]["text"]
    assert proposal_attempt(PAGE_PREVIEWS, researcher)[0] is True
    for _ in range(LIMITS[PAGE_PREVIEWS] - 1):
        assert proposal_attempt(PAGE_PREVIEWS, researcher)[0] is True
    previewed = await tool_text("preview_page", BUNDLE, researcher)
    assert previewed["isError"] is True and "30 page previews" in previewed["content"][0]["text"]
    assert proposal_attempt(COMPONENT_PROPOSALS, researcher)[0] is True


def test_a_spent_fact_limit_answers_429_with_retry_after(monkeypatch: pytest.MonkeyPatch) -> None:
    researcher = person("RESEARCHER")

    async def accepted(session: Any, user: User) -> None:
        return None

    monkeypatch.setattr(knowledge_writes, "require_terms", accepted)
    monkeypatch.setattr(knowledge_writes, "proposed", never_called)
    spend(FACT_PROPOSALS, researcher)
    proposal = {
        "subject": {"kind": "craft", "slug": "Kutch-Ajrakh"},
        "field": "PROCESS",
        "statement": "The cloth is printed with a lime and gum resist before dyeing.",
        "sources": [
            {"url": "https://example.org/a", "title": "A", "quotes": [{"text": "lime and gum resist"}]}
        ],
    }
    response = client(researcher).post("/api/knowledge/facts", json=proposal)
    assert response.status_code == 429
    assert 1 <= int(response.headers["retry-after"]) <= HOUR
    assert "30 fact proposals" in response.json()["detail"]


@pytest.mark.parametrize(
    ("path", "kind"),
    [
        ("/api/contributions/images", IMAGE_UPLOADS),
        ("/api/contributions/proposals/components", COMPONENT_PROPOSALS),
        ("/api/knowledge/pages", PAGE_PROPOSALS),
        ("/api/knowledge/pages/preview", PAGE_PREVIEWS),
    ],
)
def test_the_site_s_picture_and_component_routes_share_the_limits(path: str, kind: str) -> None:
    researcher = person("RESEARCHER")
    spend(kind, researcher)
    response = client(researcher).post(path, json={})
    assert response.status_code == 429 and "retry-after" in response.headers
    student = person("STUDENT", 33)
    assert client(student).post(path, json={}).status_code == 403
    assert proposal_attempt(kind, student)[0] is True
