import uuid
from datetime import UTC, datetime
from typing import Any

import pytest

from app.api import mcp_page_tools
from app.api.mcp_tools import TOOLS, ToolContext, answer
from app.core.rate_limit import PAGE_PROPOSALS, proposal_attempt
from app.models import User
from app.research.page_proposals import PageBundle, PagePreviewResult, PageProposalResult, PageSubject
from app.services.craft_resolver import CraftIndexStore

from ..research.general_spec_fixtures import TABLE

SITE = "https://kalavigyan.example"
USER_ID = uuid.UUID("0e000000-0000-4000-8000-000000000001")
PAGE_TOOL_NAMES = ("edit_draft", "preview_page", "propose_page")
VIEW = "ui://kalavigyan/page-preview.html"
COMPONENT = {
    "label": "kutch-ajrakh/chemistry/alum-table",
    "title": "Alum on cotton",
    "description": "A table of what alum does to the madder red on cotton, cited fact by fact.",
    "kind": "general_table",
    "field": "CHEMISTRY",
    "craft_slug": "Kutch-Ajrakh",
    "subjects": [{"kind": "CRAFT", "key": "Kutch-Ajrakh"}],
}
SUBJECT = {"kind": "craft", "slug": "Kutch-Ajrakh"}
BUNDLE = {"subject": SUBJECT, "layout": {"base_version": 0, "entries": []}}
UNITS = {ref: {"text": "Alum"} for ref in ("u0001", "u0002", "u0003", "u0004", "u0005", "u0006")}


class FakeSession:
    def __init__(self) -> None:
        self.commits = 0
        self.rollbacks = 0

    async def commit(self) -> None:
        self.commits += 1

    async def rollback(self) -> None:
        self.rollbacks += 1


def context(role: str = "RESEARCHER", session: Any = None, number: int = 1) -> ToolContext:
    user = User(id=uuid.UUID(int=number), name="Contributor", email="c@example.org", role=role)
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


def result(bundle: PageBundle, site: str) -> PageProposalResult:
    return PageProposalResult(
        subject=PageSubject(kind="craft", slug="Kutch-Ajrakh"),
        page_url=f"{site}/crafts/Kutch-Ajrakh",
        accepted=len(bundle.components),
        refused=0,
        parts=[],
        message="Parts.",
    )


@pytest.fixture
def proposed(monkeypatch: pytest.MonkeyPatch) -> list[tuple[PageBundle, str, str]]:
    seen: list[tuple[PageBundle, str, str]] = []

    async def page_proposed(
        session: Any, bundle: PageBundle, user: User, *, origin: str, site: str
    ) -> PageProposalResult:
        seen.append((bundle, origin, site))
        return result(bundle, site)

    monkeypatch.setattr(mcp_page_tools, "page_proposed", page_proposed)
    return seen


def test_the_page_tools_are_contribute_tools_in_the_pages_group() -> None:
    for name in PAGE_TOOL_NAMES:
        tool = TOOLS[name]
        assert tool.scope == "contribute" and tool.group == "pages", name
        assert tool.annotations["readOnlyHint"] is (name == "preview_page"), name
    assert TOOLS["preview_page"].records and TOOLS["preview_page"].commits
    meta = TOOLS["preview_page"].listed()["_meta"]
    assert meta == {
        "kalavigyan/group": "pages",
        "ui": {"resourceUri": VIEW, "visibility": ["model", "app"]},
        "ui/resourceUri": VIEW,
    }
    for name in ("propose_component", "propose_layout", "create_draft", "submit_draft", "preview_draft"):
        assert name not in TOOLS
    schema = TOOLS["propose_page"].listed()["inputSchema"]
    assert set(schema["properties"]) == {"bundle", "draft_id"}


@pytest.mark.parametrize("arguments", [{}, {"bundle": BUNDLE, "draft_id": str(USER_ID)}])
async def test_a_page_tool_takes_a_bundle_or_a_draft_one_of_them(arguments: dict[str, Any]) -> None:
    refused = await call("propose_page", arguments, context())
    assert (
        refused["isError"] is True and "a bundle or a draft_id, one of them" in refused["content"][0]["text"]
    )


async def test_a_component_without_its_spec_is_refused_before_anything_runs(
    proposed: list[tuple[PageBundle, str, str]],
) -> None:
    bundle = {"subject": SUBJECT, "components": [{"proposal": COMPONENT}]}
    refused = await call("propose_page", {"bundle": bundle}, context())
    assert refused["isError"] is True and "a component is delivered finished" in refused["content"][0]["text"]
    assert proposed == []


async def test_a_malformed_component_is_a_tool_error_before_anything_is_searched(
    proposed: list[tuple[PageBundle, str, str]],
) -> None:
    broken = COMPONENT | {"extends": "shared/chemistry/tannin-structure", "spec": TABLE, "units": UNITS}
    result = await call(
        "propose_page", {"bundle": {"subject": SUBJECT, "components": [{"proposal": broken}]}}, context()
    )
    assert result["isError"] is True and "extends and extension come together" in result["content"][0]["text"]
    assert proposed == []


async def test_a_component_alone_is_proposed_as_the_agent_with_its_own_allowance_only(
    proposed: list[tuple[PageBundle, str, str]],
) -> None:
    tool_context = context(number=61)
    assert tool_context.user is not None
    for _ in range(10):
        assert (await proposal_attempt(PAGE_PROPOSALS, tool_context.user)).granted == 1
    delivered = {"proposal": COMPONENT | {"spec": TABLE, "units": UNITS}}
    shown = await call(
        "propose_page", {"bundle": {"subject": SUBJECT, "components": [delivered]}}, tool_context
    )
    assert shown["isError"] is False and shown["structuredContent"]["accepted"] == 1
    ((bundle, origin, site),) = proposed
    assert (len(bundle.components), bundle.components[0].proposal.spec, origin, site) == (
        1,
        TABLE,
        "AGENT",
        SITE,
    )
    assert shown["structuredContent"]["nextStep"] == "Follow each part with get_proposal or my_work."
    link = {"proposal": COMPONENT | {"extends": COMPONENT["label"], "extension": "SUBJECT_LINK"}}
    linked = await call("propose_page", {"bundle": {"subject": SUBJECT, "components": [link]}}, tool_context)
    assert linked["isError"] is False and proposed[1][0].components[0].proposal.spec is None


async def test_a_bundle_of_several_parts_counts_as_a_page_bundle(
    proposed: list[tuple[PageBundle, str, str]],
) -> None:
    tool_context = context(number=62)
    assert tool_context.user is not None
    for _ in range(10):
        assert (await proposal_attempt(PAGE_PROPOSALS, tool_context.user)).granted == 1
    delivered = {"proposal": COMPONENT | {"spec": TABLE, "units": UNITS}}
    both = {"subject": SUBJECT, "components": [delivered], "layout": {"base_version": 0, "entries": []}}
    spent = await call("propose_page", {"bundle": both}, tool_context)
    assert spent["isError"] is True and "10 page bundles" in spent["content"][0]["text"]
    assert proposed == []


async def test_a_preview_returns_its_private_link_read_only_and_kept(monkeypatch: pytest.MonkeyPatch) -> None:
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

    async def no_report(*args: Any, **kwargs: Any) -> None:
        return None

    monkeypatch.setattr(mcp_page_tools.page_preview, "preview_page", previewed)
    monkeypatch.setattr(mcp_page_tools.page_report, "preview_report", no_report)
    session = FakeSession()
    shown = await call("preview_page", {"bundle": BUNDLE}, context(session=session))
    assert shown["structuredContent"]["previewUrl"] == f"{SITE}/preview/token"
    assert shown["structuredContent"]["draftId"] is None
    assert session.commits == 1


@pytest.mark.parametrize("name", PAGE_TOOL_NAMES)
async def test_a_student_cannot_deliver_pages_or_components(name: str) -> None:
    arguments = {"subject": SUBJECT, "lists": {"mechanisms": ["Alum fixes the red"]}}
    if name != "edit_draft":
        arguments = {"bundle": BUNDLE}
    result = await call(name, arguments, context(role="STUDENT"))
    assert result["isError"] is True and "Researcher or above" in result["content"][0]["text"]
