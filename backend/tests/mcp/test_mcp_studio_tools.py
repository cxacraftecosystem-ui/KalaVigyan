import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from app.api import mcp_studio_sources, mcp_studio_tools
from app.api.mcp_tools import TOOLS, ToolContext, answer
from app.core.errors import InvalidInput
from app.models import PageDraft, SuppliedSource, User
from app.research.page_proposals import PageBundle, PagePreviewResult, PageProposalResult, PageSubject
from app.research.page_report import page_report
from app.research.page_report_rules import ReportInput
from app.services.craft_resolver import CraftIndexStore
from app.services.supplied_sources import Supplied

from ..research.page_report_rules_fixtures import page_document
from ..research.test_page_proposals import COMPONENT, FACT

SITE = "https://kalavigyan.example"
API = "https://api.kalavigyan.example"
USER_ID = uuid.UUID("0e000000-0000-4000-8000-0000000057d1")
DRAFT_ID = uuid.UUID("0e000000-0000-4000-8000-0000000057d2")
SUPPLIED_ID = uuid.UUID("0e000000-0000-4000-8000-0000000057d3")
NOW = datetime(2026, 11, 21, 9, tzinfo=UTC)
STUDIO = (
    "supply_source",
    "create_draft",
    "add_to_draft",
    "remove_from_draft",
    "get_draft",
    "preview_draft",
    "submit_draft",
)
VIEW = "ui://kalavigyan/page-preview.html"
IDENTITY = {
    "title": "Mordant printing with alum and madder",
    "doi": "10.1000/kv.42",
    "authors": ["Meera Shah"],
}
ACCESS = {"how": "SUBSCRIPTION", "accessed_on": "2026-11-20"}
PASSAGE = {"text": "Alum is printed before the madder bath so the red fixes only there.", "locator": "p. 14"}


class FakeSession:
    def __init__(self) -> None:
        self.commits = 0
        self.rollbacks = 0

    async def commit(self) -> None:
        self.commits += 1

    async def rollback(self) -> None:
        self.rollbacks += 1


@dataclass(frozen=True)
class Endpoints:
    issuer: str


def context(role: str = "RESEARCHER", session: Any = None) -> ToolContext:
    user = User(id=USER_ID, name="Contributor", email="studio@example.org", role=role, tokenVersion=0)
    return ToolContext(
        session=session or FakeSession(),
        index=CraftIndexStore(),
        site=SITE,
        user=user,
        scopes=frozenset({"read", "contribute"}),
    )


async def call(
    name: str, arguments: dict[str, Any], tool_context: ToolContext | None = None
) -> dict[str, Any]:
    message = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {"name": name, "arguments": arguments},
    }
    reply = await answer(message, tool_context or context())
    assert reply is not None and "result" in reply, reply
    return reply["result"]


def draft_row(parts: dict[str, Any] | None = None, **changes: Any) -> PageDraft:
    values: dict[str, Any] = {
        "id": DRAFT_ID,
        "userId": USER_ID,
        "subjectKind": "craft",
        "subjectSlug": "Kutch-Ajrakh",
        "state": "OPEN",
        "parts": parts or {},
        "bytes": 0,
        "version": 1,
        "expiresAt": NOW + timedelta(days=14),
        "createdAt": NOW,
        "updatedAt": NOW,
    }
    return PageDraft(**(values | changes))


def property_names(schema: Any) -> set[str]:
    found: set[str] = set()
    pending = [schema]
    while pending:
        current = pending.pop()
        if isinstance(current, dict):
            found |= set(current.get("properties", {}))
            pending += list(current.values())
        elif isinstance(current, list):
            pending += current
    return found


def test_the_studio_tools_are_contribute_tools_and_the_previews_name_their_view() -> None:
    for name in STUDIO:
        tool = TOOLS[name]
        assert tool.scope == "contribute", name
        assert tool.annotations["readOnlyHint"] is (name == "get_draft"), name
    for name in ("preview_draft", "preview_page"):
        meta = TOOLS[name].listed()["_meta"]
        assert meta == {"ui": {"resourceUri": VIEW, "visibility": ["model", "app"]}, "ui/resourceUri": VIEW}
    assert {"report", "draftId", "previewUrl"} <= set(
        TOOLS["preview_draft"].listed()["outputSchema"]["properties"]
    )


@pytest.mark.parametrize("name", ["add_to_draft", "supply_source", "create_draft"])
def test_the_studio_tools_are_schemed_in_snake_case(name: str) -> None:
    names = property_names(TOOLS[name].listed()["inputSchema"])
    assert [each for each in names if each != each.lower()] == []
    assert "draft_id" in names or name == "create_draft"


@pytest.mark.parametrize("name", STUDIO)
async def test_a_student_cannot_use_the_studio(name: str) -> None:
    arguments: dict[str, Any] = {"draft_id": str(DRAFT_ID)}
    if name == "supply_source":
        arguments = {"identity": IDENTITY, "access": ACCESS, "passages": [PASSAGE]}
    elif name == "create_draft":
        arguments = {"subject_kind": "craft", "slug": "Kutch-Ajrakh"}
    elif name == "add_to_draft":
        arguments |= {"note": "A note."}
    elif name == "remove_from_draft":
        arguments |= {"part": "fact", "index": 0}
    result = await call(name, arguments, context(role="STUDENT"))
    assert result["isError"] is True and "Researcher or above" in result["content"][0]["text"]


async def test_create_draft_opens_the_page_s_draft_and_says_what_comes_next(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen: dict[str, Any] = {}

    async def created(session: Any, user: User, subject: PageSubject, *, now: datetime) -> PageDraft:
        seen["subject"] = subject
        return draft_row()

    monkeypatch.setattr(mcp_studio_tools.page_drafts, "create_draft", created)
    session = FakeSession()
    result = await call(
        "create_draft", {"subject_kind": "craft", "slug": "Kutch-Ajrakh"}, context(session=session)
    )
    content = result["structuredContent"]
    assert result["isError"] is False and session.commits == 1
    assert seen["subject"] == PageSubject(kind="craft", slug="Kutch-Ajrakh")
    assert content["draftId"] == str(DRAFT_ID) and content["state"] == "OPEN"
    assert content["counts"]["facts"] == 0 and content["limits"]["facts"] == 20
    assert "add_to_draft" in content["nextStep"]


async def test_an_empty_addition_is_refused_before_the_draft_is_touched() -> None:
    result = await call("add_to_draft", {"draft_id": str(DRAFT_ID)})
    assert result["isError"] is True and "add at least one" in result["content"][0]["text"]


async def test_parts_reach_the_draft_and_old_names_are_noted(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict[str, Any] = {}

    async def added(
        session: Any, user: User, draft_id: uuid.UUID, addition: Any, *, now: datetime
    ) -> PageDraft:
        seen["addition"] = addition
        return draft_row(addition.model_dump(mode="json", by_alias=True), version=2)

    monkeypatch.setattr(mcp_studio_tools.page_drafts, "add_to_draft", added)
    picture = {"contributionId": "6f1c2a4e-8d3b-4c5a-9e7f-0a1b2c3d4e5f"}
    arguments = {"draft_id": str(DRAFT_ID), "facts": [FACT], "pictures": [picture]}
    content = (await call("add_to_draft", arguments))["structuredContent"]
    assert (
        len(seen["addition"].facts) == 1
        and str(seen["addition"].pictures[0].contribution_id) == picture["contributionId"]
    )
    assert (content["counts"]["facts"], content["counts"]["pictures"], content["version"]) == (1, 1, 2)
    assert [part["part"] for part in content["parts"]] == ["fact", "picture"]
    assert content["notices"] == [
        "contributionId is the old name of contribution_id; it works until the next release, so pass "
        "contribution_id from now on."
    ]


async def test_a_part_is_removed_by_a_kind_the_draft_knows() -> None:
    result = await call("remove_from_draft", {"draft_id": str(DRAFT_ID), "part": "chapter", "index": 0})
    assert result["isError"] is True and "part" in result["content"][0]["text"]


async def test_a_refusal_from_the_draft_is_a_tool_error_and_rolls_back(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def gone(session: Any, user: User, draft_id: uuid.UUID, **kwargs: Any) -> PageDraft:
        raise InvalidInput(f"No open draft of yours has the id {draft_id}")

    monkeypatch.setattr(mcp_studio_tools.page_drafts, "own_draft", gone)
    session = FakeSession()
    result = await call("submit_draft", {"draft_id": str(DRAFT_ID)}, context(session=session))
    assert result["isError"] is True and "No open draft of yours" in result["content"][0]["text"]
    assert (session.commits, session.rollbacks) == (0, 1)


def owned(row: PageDraft) -> Any:
    async def own(session: Any, user: User, draft_id: uuid.UUID, **kwargs: Any) -> PageDraft:
        assert user.id == USER_ID and draft_id == DRAFT_ID
        return row

    return own


async def noop(*args: Any, **kwargs: Any) -> None:
    return None


async def test_preview_draft_returns_the_private_link_and_the_report(monkeypatch: pytest.MonkeyPatch) -> None:
    row = draft_row({"facts": [FACT]})
    report = page_report(ReportInput(document=page_document()), {})

    async def previewed(
        session: Any, user: User, bundle: PageBundle, *, site: str, now: datetime
    ) -> PagePreviewResult:
        assert len(bundle.facts) == 1
        return PagePreviewResult(
            subject=bundle.subject,
            page_url=f"{site}/crafts/Kutch-Ajrakh",
            preview_url=f"{site}/preview/token",
            expires_at=NOW + timedelta(hours=24),
            chapters=["opening", "chem"],
            components=1,
            sources=2,
            parts=[],
            message="Private to you for 24 hours.",
        )

    async def reported(*args: Any, **kwargs: Any) -> Any:
        return report

    monkeypatch.setattr(mcp_studio_tools.page_drafts, "own_draft", owned(row))
    monkeypatch.setattr(mcp_studio_tools.page_drafts, "record_preview", noop)
    monkeypatch.setattr(mcp_studio_tools.page_preview, "preview_page", previewed)
    monkeypatch.setattr(mcp_studio_tools.page_report, "preview_report", reported)
    content = (await call("preview_draft", {"draft_id": str(DRAFT_ID)}))["structuredContent"]
    assert content["previewUrl"] == f"{SITE}/preview/token" and content["draftId"] == str(DRAFT_ID)
    assert (content["report"]["failed"], len(content["report"]["rules"])) == (report.failed, 26)


async def test_submit_draft_proposes_its_bundle_as_the_agent(monkeypatch: pytest.MonkeyPatch) -> None:
    row = draft_row(
        {"facts": [FACT], "components": [{"proposal": COMPONENT, "cites": {"u0006": ["fact:0"]}}]}
    )
    seen: dict[str, Any] = {}

    async def proposed(
        session: Any, bundle: PageBundle, user: User, *, origin: str, site: str
    ) -> PageProposalResult:
        seen.update(origin=origin, components=len(bundle.components))
        return PageProposalResult(
            subject=bundle.subject,
            page_url=f"{site}/crafts/Kutch-Ajrakh",
            accepted=2,
            refused=0,
            parts=[],
            message="2 of 2.",
        )

    monkeypatch.setattr(mcp_studio_tools.page_drafts, "own_draft", owned(row))
    monkeypatch.setattr(mcp_studio_tools.page_drafts, "record_submission", noop)
    monkeypatch.setattr(mcp_studio_tools, "page_proposed", proposed)
    content = (await call("submit_draft", {"draft_id": str(DRAFT_ID)}))["structuredContent"]
    assert seen == {"origin": "AGENT", "components": 1}
    assert (
        content["draftId"] == str(DRAFT_ID)
        and content["accepted"] == 2
        and "get_proposal" in content["nextStep"]
    )


def supplied_row(state: str = "READY") -> SuppliedSource:
    return SuppliedSource(
        id=SUPPLIED_ID,
        userId=USER_ID,
        state=state,
        citeUrl="https://doi.org/10.1000/kv.42",
        title=IDENTITY["title"],
        licence=None,
        grade="A",
        gradeReason="found in openalex as paper, graded A",
        confirmation=None,
        characters=68 if state == "READY" else 0,
        passages=[PASSAGE] if state == "READY" else [],
        textSha256="a" * 64 if state == "READY" else None,
        upload=None if state == "READY" else "pdf",
        slotExpiresAt=None if state == "READY" else NOW + timedelta(minutes=30),
    )


@pytest.fixture
def lookups(monkeypatch: pytest.MonkeyPatch) -> list[Any]:
    seen: list[Any] = []

    @asynccontextmanager
    async def lookup(session: Any) -> AsyncIterator[Any]:
        async def none(identity: Any) -> None:
            return None

        yield none

    monkeypatch.setattr(mcp_studio_sources, "scholarly_lookup", lookup)
    monkeypatch.setattr(mcp_studio_sources, "endpoints_or_none", lambda: Endpoints(API))
    return seen


async def test_a_supplied_source_says_how_to_cite_it(
    monkeypatch: pytest.MonkeyPatch, lookups: list[Any]
) -> None:
    async def supply(session: Any, user: User, draft: Any, *, lookup: Any, now: datetime) -> Supplied:
        lookups.append(draft)
        return Supplied(row=supplied_row(), slot_token=None)

    monkeypatch.setattr(mcp_studio_sources.supplied_sources, "supply_source", supply)
    content = (await call("supply_source", {"identity": IDENTITY, "access": ACCESS, "passages": [PASSAGE]}))[
        "structuredContent"
    ]
    assert lookups[0].identity.doi == "10.1000/kv.42" and lookups[0].access.how == "SUBSCRIPTION"
    assert content["citeAs"]["url"] == "https://doi.org/10.1000/kv.42" and content["state"] == "READY"
    assert content["upload"] is None and "QUOTES gate" in content["nextStep"]


async def test_an_upload_returns_its_private_slot(
    monkeypatch: pytest.MonkeyPatch, lookups: list[Any]
) -> None:
    async def supply(session: Any, user: User, draft: Any, *, lookup: Any, now: datetime) -> Supplied:
        return Supplied(row=supplied_row("AWAITING_FILE"), slot_token="kvss_token")

    monkeypatch.setattr(mcp_studio_sources.supplied_sources, "supply_source", supply)
    content = (await call("supply_source", {"identity": IDENTITY, "access": ACCESS, "upload": "pdf"}))[
        "structuredContent"
    ]
    assert content["upload"]["uploadUrl"] == f"{API}/api/knowledge/supplied-sources/slots/kvss_token"
    assert (
        content["upload"]["uploadTypes"] == ["application/pdf"] and content["upload"]["uploadMethod"] == "PUT"
    )


async def test_a_source_s_words_come_one_way_and_uploads_need_the_api_origin(
    monkeypatch: pytest.MonkeyPatch, lookups: list[Any]
) -> None:
    both = await call(
        "supply_source", {"identity": IDENTITY, "access": ACCESS, "passages": [PASSAGE], "upload": "pdf"}
    )
    assert both["isError"] is True and "one way" in both["content"][0]["text"]
    monkeypatch.setattr(mcp_studio_sources, "endpoints_or_none", lambda: None)
    upload = await call("supply_source", {"identity": IDENTITY, "access": ACCESS, "upload": "pdf"})
    assert upload["isError"] is True and "cannot be uploaded" in upload["content"][0]["text"]
