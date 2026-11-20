import uuid
from collections.abc import AsyncIterator
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.api import mcp_structure_tools
from app.api.mcp_tools import ToolContext, answer
from app.api.routes import structure_proposals as route
from app.core.db import get_session
from app.core.deps import get_current_user
from app.core.errors import ExternalFailure, InvalidInput, Refused
from app.core.mcp_scopes import CONTRIBUTE_SCOPE, READ_SCOPE
from app.main import create_app
from app.models import User
from app.research.structure_proposals import StructureProposal, StructureProposalResult, StructureSubject
from app.services.craft_resolver import CraftIndexStore
from app.services.structure_proposals_write import STALE_STRUCTURE

from .pages import NAME_QUOTE, SLUG, source

SITE = "https://kalavigyan.example"
BODY = {
    "subject": {"kind": "craft", "slug": SLUG},
    "item": {"kind": "NATIVE_NAME", "text": "Ajrak", "language": "sd"},
    "field": "HISTORY",
    "statement": "Printers in the delta call the cloth ajrak, after their word for blue.",
    "sources": [source(NAME_QUOTE)],
}
RESULT = StructureProposalResult(
    outcome="STORED",
    proposal_id=uuid.UUID(int=77),
    status="PENDING",
    kind="NATIVE_NAME",
    subject=StructureSubject(slug=SLUG),
    checks=[],
    page_url=f"{SITE}/crafts/{SLUG}",
    message="Stored for review.",
)


def person(role: str) -> User:
    return User(id=uuid.UUID(int=51), name=f"{role} person", email="p@example.org", role=role)


def http(role: str, monkeypatch: pytest.MonkeyPatch, outcome: Any, seen: list[str]) -> TestClient:
    async def accepted(session: Any, user: User) -> None:
        return None

    async def proposed(
        session: Any, proposal: StructureProposal, user: User, *, origin: str, site: str
    ) -> Any:
        seen.append(origin)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

    monkeypatch.setattr(route, "require_terms", accepted)
    monkeypatch.setattr(route, "structure_proposed", proposed)
    app = create_app()
    app.dependency_overrides[get_current_user] = lambda: person(role)

    async def opened() -> AsyncIterator[Any]:
        yield object()

    app.dependency_overrides[get_session] = opened
    return TestClient(app)


@pytest.mark.parametrize(
    ("role", "outcome", "status"),
    [
        ("RESEARCHER", RESULT, 200),
        ("RESEARCHER", Refused(STALE_STRUCTURE, "The page has moved on."), 409),
        ("RESEARCHER", Refused("no_account", "The account behind this proposal no longer exists."), 403),
        ("RESEARCHER", InvalidInput("Structure-Test-Craft has no curated page yet."), 422),
        (
            "RESEARCHER",
            ExternalFailure("the fetcher could not be reached", kind="unavailable", retryable=True),
            503,
        ),
        ("STUDENT", RESULT, 403),
    ],
)
def test_the_knowledge_api_takes_a_structure_proposal_with_its_status(
    monkeypatch: pytest.MonkeyPatch, role: str, outcome: Any, status: int
) -> None:
    seen: list[str] = []
    response = http(role, monkeypatch, outcome, seen).post("/api/knowledge/structure", json=BODY)
    assert response.status_code == status
    if status == 200:
        assert response.json()["proposalId"] == str(RESULT.proposal_id)
    assert seen == ([] if role == "STUDENT" else ["CONTRIBUTION"])


def test_a_malformed_structure_proposal_never_reaches_the_service(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[str] = []
    unlocated = BODY | {"sources": [source(NAME_QUOTE, quotes=[{"text": NAME_QUOTE}])]}
    response = http("RESEARCHER", monkeypatch, RESULT, seen).post("/api/knowledge/structure", json=unlocated)
    assert response.status_code == 422 and seen == []


def test_the_twenty_first_structure_proposal_in_an_hour_waits(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[str] = []
    client = http("RESEARCHER", monkeypatch, RESULT, seen)
    statuses = [client.post("/api/knowledge/structure", json=BODY).status_code for _ in range(21)]
    assert statuses[:20] == [200] * 20 and statuses[20] == 429
    assert len(seen) == 20


class Ended:
    def __init__(self) -> None:
        self.ended: list[str] = []

    async def commit(self) -> None:
        self.ended.append("commit")

    async def rollback(self) -> None:
        self.ended.append("rollback")


def mcp_context(
    role: str | None, scopes: frozenset[str] = frozenset({READ_SCOPE, CONTRIBUTE_SCOPE})
) -> ToolContext:
    session: Any = Ended()
    user = None if role is None else person(role)
    return ToolContext(session=session, index=CraftIndexStore(), site=SITE, user=user, scopes=scopes)


async def call_tool(arguments: dict[str, Any], tool_context: ToolContext) -> dict[str, Any]:
    message = {
        "jsonrpc": "2.0",
        "id": 8,
        "method": "tools/call",
        "params": {"name": "propose_structure", "arguments": arguments},
    }
    reply = await answer(message, tool_context)
    assert reply is not None and "result" in reply, reply
    return reply["result"]


async def test_propose_structure_is_a_contribute_write() -> None:
    reply = await answer({"jsonrpc": "2.0", "id": 1, "method": "tools/list"}, mcp_context(None))
    assert reply is not None
    (tool,) = [tool for tool in reply["result"]["tools"] if tool["name"] == "propose_structure"]
    assert tool["annotations"]["readOnlyHint"] is False
    assert tool["inputSchema"]["required"] == ["proposal"]
    assert mcp_structure_tools.PROPOSE_STRUCTURE.scope == CONTRIBUTE_SCOPE


async def test_an_agent_s_structure_carries_the_agent_origin_and_refusals_are_tool_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    origins: list[str] = []

    async def proposed(
        session: Any, proposal: StructureProposal, user: User, *, origin: str, site: str
    ) -> Any:
        origins.append(origin)
        if proposal.item.kind == "STAGE_WHY":
            raise Refused(STALE_STRUCTURE, "The page has moved on since this was proposed.")
        return RESULT

    monkeypatch.setattr(mcp_structure_tools, "structure_proposed", proposed)
    stored = await call_tool({"proposal": BODY}, mcp_context("RESEARCHER"))
    assert stored["isError"] is False and stored["structuredContent"]["outcome"] == "STORED"
    why = BODY | {"item": {"kind": "STAGE_WHY", "stageKey": "P01"}, "field": "CHEMISTRY"}
    moved = await call_tool({"proposal": why}, mcp_context("RESEARCHER"))
    assert moved["isError"] is True and "moved on" in moved["content"][0]["text"]
    student = await call_tool({"proposal": BODY}, mcp_context("STUDENT"))
    assert student["isError"] is True and "Researcher or above" in student["content"][0]["text"]
    assert origins == ["AGENT", "AGENT"]
