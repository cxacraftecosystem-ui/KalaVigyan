import uuid
from datetime import UTC, datetime
from typing import Any

import pytest

from app.api import mcp_page_tools
from app.api.mcp_tools import TOOLS, ToolContext, answer
from app.api.mcp_work_tools import WORK_TOOLS
from app.models import User
from app.research.component_proposals import ComponentProposalResult
from app.research.page_proposals import PageBundle, PagePreviewResult, PageProposalResult, PageSubject
from app.services.craft_resolver import CraftIndexStore

from ..research.general_spec_fixtures import TABLE

SITE = "https://kalavigyan.example"
USER_ID = uuid.UUID("0e000000-0000-4000-8000-000000000001")
PAGE_TOOL_NAMES = ("propose_component", "propose_page", "preview_page")
COMPONENT = {
    "label": "kutch-ajrakh/chemistry/alum-table",
    "title": "Alum on cotton",
    "description": "A table of what alum does to the madder red on cotton, cited fact by fact.",
    "kind": "general_table",
    "field": "CHEMISTRY",
    "craft_slug": "Kutch-Ajrakh",
    "subjects": [{"kind": "CRAFT", "key": "Kutch-Ajrakh"}],
}
BUNDLE = {"subject": {"kind": "craft", "slug": "Kutch-Ajrakh"}, "layout": {"baseVersion": 0, "entries": []}}


class FakeSession:
    def __init__(self) -> None:
        self.commits = 0
        self.rollbacks = 0

    async def commit(self) -> None:
        self.commits += 1

    async def rollback(self) -> None:
        self.rollbacks += 1


def context(role: str = "RESEARCHER", session: Any = None) -> ToolContext:
    user = User(id=USER_ID, name="Contributor", email="c@example.org", role=role)
    return ToolContext(
        session=session or FakeSession(),
        index=CraftIndexStore(),
        site=SITE,
        user=user,
        scopes=frozenset({"read", "contribute"}),
    )


async def call(name: str, arguments: dict[str, Any], tool_context: ToolContext) -> dict[str, Any]:
    message = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {"name": name, "arguments": arguments},
    }
    reply = await answer(message, tool_context)
    assert reply is not None and "result" in reply, reply
    return reply["result"]


def test_the_page_tools_are_contribute_writes_and_propose_component_left_the_work_tools() -> None:
    for name in PAGE_TOOL_NAMES:
        tool = TOOLS[name]
        assert tool.scope == "contribute" and tool.annotations["readOnlyHint"] is False
        assert tool in mcp_page_tools.PAGE_TOOLS
    assert "propose_component" not in {tool.name for tool in WORK_TOOLS}
    schema = TOOLS["propose_component"].listed()["inputSchema"]
    assert {"spec", "units", "considered_labels", "extends", "extension"} <= set(schema["properties"])


async def test_a_component_without_its_spec_is_refused_before_anything_runs() -> None:
    result = await call("propose_component", COMPONENT, context())
    assert result["isError"] is True and "a component is delivered finished" in result["content"][0]["text"]


async def test_a_subject_link_carries_no_spec_and_reaches_the_service(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen: dict[str, Any] = {}

    async def proposed(session: Any, user: User, draft: Any, *, now: datetime) -> ComponentProposalResult:
        seen["draft"] = draft
        return ComponentProposalResult(outcome="STORED", label=draft.label, message="Stored for review.")

    monkeypatch.setattr(mcp_page_tools.component_proposals, "propose_component", proposed)
    link = {**COMPONENT, "extends": COMPONENT["label"], "extension": "SUBJECT_LINK"}
    session = FakeSession()
    result = await call("propose_component", link, context(session=session))
    assert result["isError"] is False and seen["draft"].spec is None
    assert session.commits == 1


async def test_a_delivered_component_reaches_the_service_with_its_spec(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen: dict[str, Any] = {}

    async def proposed(session: Any, user: User, draft: Any, *, now: datetime) -> ComponentProposalResult:
        seen["spec"] = draft.spec
        return ComponentProposalResult(outcome="STORED", label=draft.label, message="Stored for review.")

    monkeypatch.setattr(mcp_page_tools.component_proposals, "propose_component", proposed)
    units = {ref: {"text": "Alum"} for ref in ("u0001", "u0002", "u0003", "u0004", "u0005", "u0006")}
    result = await call("propose_component", {**COMPONENT, "spec": TABLE, "units": units}, context())
    assert result["isError"] is False and seen["spec"] == TABLE


async def test_a_page_bundle_is_proposed_by_the_agent_on_the_connection_s_site(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen: dict[str, Any] = {}

    async def proposed(
        session: Any, bundle: PageBundle, user: User, *, origin: str, site: str
    ) -> PageProposalResult:
        seen.update(origin=origin, site=site, slug=bundle.subject.slug)
        return PageProposalResult(
            subject=PageSubject(kind="craft", slug="Kutch-Ajrakh"),
            page_url=f"{site}/crafts/Kutch-Ajrakh",
            accepted=0,
            refused=0,
            parts=[],
            message="0 of 0 parts.",
        )

    monkeypatch.setattr(mcp_page_tools, "page_proposed", proposed)
    result = await call("propose_page", {"proposal": BUNDLE}, context())
    assert result["isError"] is False
    assert seen == {"origin": "AGENT", "site": SITE, "slug": "Kutch-Ajrakh"}
    assert result["structuredContent"]["pageUrl"] == f"{SITE}/crafts/Kutch-Ajrakh"


async def test_a_preview_returns_its_private_link(monkeypatch: pytest.MonkeyPatch) -> None:
    async def previewed(
        session: Any, user: User, bundle: PageBundle, *, site: str, now: datetime
    ) -> PagePreviewResult:
        return PagePreviewResult(
            subject=PageSubject(kind="craft", slug="Kutch-Ajrakh"),
            page_url=f"{site}/crafts/Kutch-Ajrakh",
            preview_url=f"{site}/preview/token",
            expires_at=datetime(2026, 11, 21, 12, tzinfo=UTC),
            chapters=["opening", "sources"],
            components=0,
            sources=1,
            parts=[],
            message="Private to you for 24 hours.",
        )

    monkeypatch.setattr(mcp_page_tools.page_preview, "preview_page", previewed)
    session = FakeSession()
    result = await call("preview_page", {"proposal": BUNDLE}, context(session=session))
    assert result["structuredContent"]["previewUrl"] == f"{SITE}/preview/token"
    assert session.commits == 1


@pytest.mark.parametrize("name", PAGE_TOOL_NAMES)
async def test_a_student_cannot_deliver_pages_or_components(name: str) -> None:
    arguments = {"proposal": BUNDLE} if name != "propose_component" else {**COMPONENT, "spec": TABLE}
    result = await call(name, arguments, context(role="STUDENT"))
    assert result["isError"] is True and "Researcher or above" in result["content"][0]["text"]
