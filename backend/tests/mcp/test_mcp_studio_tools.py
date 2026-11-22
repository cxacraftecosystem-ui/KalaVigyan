import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from app.api import mcp_page_tools, mcp_studio_sources
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
SUBJECT = {"kind": "craft", "slug": "Kutch-Ajrakh"}
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


def owned(row: PageDraft) -> Any:
    async def own(session: Any, user: User, draft_id: uuid.UUID, **kwargs: Any) -> PageDraft:
        assert user.id == USER_ID and draft_id == DRAFT_ID
        return row

    return own


async def noop(*args: Any, **kwargs: Any) -> None:
    return None


def test_edit_draft_and_supply_source_are_contribute_writes_schemed_in_snake_case() -> None:
    for name, group in (("edit_draft", "pages"), ("supply_source", "sources")):
        tool = TOOLS[name]
        assert (tool.scope, tool.group, tool.annotations["readOnlyHint"]) == ("contribute", group, False)
        names = property_names(tool.listed()["inputSchema"])
        assert [each for each in names if each != each.lower()] == []
        assert "draft_id" in names
    assert {"subject", "add", "remove", "lists"} <= property_names(
        TOOLS["edit_draft"].listed()["inputSchema"]
    )
    for name in ("create_draft", "add_to_draft", "remove_from_draft", "get_draft"):
        assert name not in TOOLS


@pytest.mark.parametrize(
    ("name", "arguments"),
    [
        ("supply_source", {"identity": IDENTITY, "access": ACCESS, "passages": [PASSAGE]}),
        ("edit_draft", {"draft_id": str(DRAFT_ID), "add": {"note": "A note."}}),
        ("preview_page", {"draft_id": str(DRAFT_ID)}),
        ("propose_page", {"draft_id": str(DRAFT_ID)}),
    ],
)
async def test_a_student_cannot_use_the_studio(name: str, arguments: dict[str, Any]) -> None:
    result = await call(name, arguments, context(role="STUDENT"))
    assert result["isError"] is True and "Researcher or above" in result["content"][0]["text"]


async def test_the_draft_is_named_by_its_page_or_its_id_one_of_them() -> None:
    for arguments in ({}, {"subject": SUBJECT, "draft_id": str(DRAFT_ID)}):
        refused = await call("edit_draft", arguments)
        assert refused["isError"] is True and "one of them" in refused["content"][0]["text"]


async def test_the_first_edit_opens_the_page_s_draft_and_one_with_nothing_to_change_returns_it(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen: list[PageSubject] = []

    async def created(session: Any, user: User, subject: PageSubject, *, now: datetime) -> PageDraft:
        seen.append(subject)
        return draft_row()

    monkeypatch.setattr(mcp_page_tools.page_drafts, "create_draft", created)
    session = FakeSession()
    content = (await call("edit_draft", {"subject": SUBJECT}, context(session=session)))["structuredContent"]
    assert session.commits == 1 and seen == [PageSubject(kind="craft", slug="Kutch-Ajrakh")]
    assert content["draftId"] == str(DRAFT_ID) and content["state"] == "OPEN"
    assert content["counts"]["facts"] == 0 and content["limits"]["facts"] == 20
    assert content["message"].startswith("The draft for craft Kutch-Ajrakh is open")
    assert "edit_draft's add" in content["nextStep"] and content["draft"] is not None


async def test_parts_reach_the_draft_and_old_names_are_noted(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict[str, Any] = {}

    async def added(
        session: Any, user: User, draft_id: uuid.UUID, addition: Any, *, now: datetime
    ) -> PageDraft:
        seen["addition"] = addition
        return draft_row(addition.model_dump(mode="json", by_alias=True), version=2)

    monkeypatch.setattr(mcp_page_tools.page_drafts, "own_draft", owned(draft_row()))
    monkeypatch.setattr(mcp_page_tools.page_drafts, "add_to_draft", added)
    picture = {"contributionId": "6f1c2a4e-8d3b-4c5a-9e7f-0a1b2c3d4e5f"}
    arguments = {"draft_id": str(DRAFT_ID), "add": {"facts": [FACT], "pictures": [picture]}}
    content = (await call("edit_draft", arguments))["structuredContent"]
    addition = seen["addition"]
    assert len(addition.facts) == 1 and str(addition.pictures[0].contribution_id) == picture["contributionId"]
    assert (content["counts"]["facts"], content["counts"]["pictures"], content["version"]) == (1, 1, 2)
    assert [part["part"] for part in content["parts"]] == ["fact", "picture"]
    assert content["draft"] is None and "preview_page" in content["nextStep"]
    assert content["notices"] == [
        "contributionId is the old name of contribution_id; it works until the next release, so pass "
        "contribution_id from now on."
    ]


async def test_removals_run_before_additions_facts_last_and_from_the_highest_index(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    order: list[Any] = []

    async def removed(
        session: Any, user: User, draft_id: uuid.UUID, part: tuple[str, int], *, now: datetime
    ) -> PageDraft:
        order.append(part)
        return draft_row()

    async def added(
        session: Any, user: User, draft_id: uuid.UUID, addition: Any, *, now: datetime
    ) -> PageDraft:
        order.append(("lists", addition.lists.mechanisms))
        return draft_row()

    monkeypatch.setattr(mcp_page_tools.page_drafts, "own_draft", owned(draft_row()))
    monkeypatch.setattr(mcp_page_tools.page_drafts, "remove_from_draft", removed)
    monkeypatch.setattr(mcp_page_tools.page_drafts, "add_to_draft", added)
    remove = [{"part": "fact", "index": 0}, {"part": "component", "index": 0}, {"part": "fact", "index": 2}]
    lists = {"mechanisms": ["Alum fixes the red"]}
    await call("edit_draft", {"draft_id": str(DRAFT_ID), "remove": remove, "lists": lists})
    assert order == [("component", 0), ("fact", 2), ("fact", 0), ("lists", ["Alum fixes the red"])]
    wrong = await call("edit_draft", {"draft_id": str(DRAFT_ID), "remove": [{"part": "chapter", "index": 0}]})
    assert wrong["isError"] is True and "part" in wrong["content"][0]["text"]


async def test_a_refusal_from_the_draft_is_a_tool_error_and_rolls_back(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def gone(session: Any, user: User, draft_id: uuid.UUID, **kwargs: Any) -> PageDraft:
        raise InvalidInput(f"No open draft of yours has the id {draft_id}")

    monkeypatch.setattr(mcp_page_tools.page_drafts, "own_draft", gone)
    session = FakeSession()
    result = await call("propose_page", {"draft_id": str(DRAFT_ID)}, context(session=session))
    assert result["isError"] is True and "No open draft of yours" in result["content"][0]["text"]
    assert (session.commits, session.rollbacks) == (0, 1)


async def test_a_draft_s_preview_returns_the_private_link_and_the_report(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    row = draft_row({"facts": [FACT]})
    report = page_report(ReportInput(document=page_document()), {})
    recorded: list[Any] = []

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

    async def record(session: Any, draft: PageDraft, *args: Any) -> None:
        recorded.append(draft.id)

    monkeypatch.setattr(mcp_page_tools.page_drafts, "own_draft", owned(row))
    monkeypatch.setattr(mcp_page_tools.page_drafts, "record_preview", record)
    monkeypatch.setattr(mcp_page_tools.page_preview, "preview_page", previewed)
    monkeypatch.setattr(mcp_page_tools.page_report, "preview_report", reported)
    session = FakeSession()
    content = (await call("preview_page", {"draft_id": str(DRAFT_ID)}, context(session=session)))[
        "structuredContent"
    ]
    assert content["previewUrl"] == f"{SITE}/preview/token" and content["draftId"] == str(DRAFT_ID)
    assert (content["report"]["failed"], len(content["report"]["rules"])) == (report.failed, 27)
    assert recorded == [DRAFT_ID] and session.commits == 1


async def test_a_draft_is_proposed_once_as_the_agent(monkeypatch: pytest.MonkeyPatch) -> None:
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

    monkeypatch.setattr(mcp_page_tools.page_drafts, "own_draft", owned(row))
    monkeypatch.setattr(mcp_page_tools.page_drafts, "record_submission", noop)
    monkeypatch.setattr(mcp_page_tools, "page_proposed", proposed)
    content = (await call("propose_page", {"draft_id": str(DRAFT_ID)}))["structuredContent"]
    assert seen == {"origin": "AGENT", "components": 1}
    assert content["draftId"] == str(DRAFT_ID) and content["accepted"] == 2
    assert "get_proposal" in content["nextStep"] and "stays readable" in content["nextStep"]


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
