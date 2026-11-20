import uuid
from collections.abc import AsyncIterator, Sequence
from datetime import UTC, datetime
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.api import mcp_page_tools
from app.api.mcp_tools import TOOLS, ToolContext, answer
from app.api.routes import knowledge_writes
from app.core.db import get_session
from app.core.deps import get_current_user
from app.core.errors import InvalidInput, Refused
from app.core.mcp_scopes import CONTRIBUTE_SCOPE, READ_SCOPE
from app.main import create_app
from app.models import LayoutProposal, User
from app.research.layout_proposals import LayoutProposalDraft, LayoutProposalResult, LayoutSubject
from app.research.page_layout import PageLayout, PageLayoutEntry
from app.research.page_proposals import PageBundle, PageProposalResult, PageSubject
from app.services import page_layout_proposals
from app.services.craft_resolver import CraftIndexStore
from app.services.open_work_subjects import WorkSubject
from app.services.page_layouts import STALE_LAYOUT

NOW = datetime(2026, 11, 20, 9, tzinfo=UTC)
SITE = "https://kalavigyan.example"
BAGH = WorkSubject(uuid.UUID(int=4), "craft", "Bagh-Print", "Bagh Print", gi=True)
TEXTILES = WorkSubject(uuid.UUID(int=3), "category", "Textile-Craft-Category", "Textiles", gi=False)
HERO = {"ref": "bagh-print/pictures/i02", "chapter": "glance", "order": 1, "role": "HERO"}
BODY = {
    "subject": {"kind": "craft", "slug": "Bagh-Print"},
    "baseVersion": 2,
    "entries": [HERO],
    "note": "Lead.",
}
RESULT = LayoutProposalResult(
    outcome="STORED",
    proposal_id=uuid.UUID(int=77),
    status="PENDING",
    subject=LayoutSubject(kind="craft", slug="Bagh-Print"),
    base_version=2,
    page_url=f"{SITE}/crafts/Bagh-Print",
    message="Stored for review.",
)


def person(role: str) -> User:
    return User(id=uuid.UUID(int=51), name=f"{role} person", email="p@example.org", role=role)


class FakeSession:
    def __init__(self) -> None:
        self.added: list[Any] = []
        self.ended: list[str] = []

    def add(self, row: Any) -> None:
        self.added.append(row)

    async def flush(self) -> None:
        return None

    async def commit(self) -> None:
        self.ended.append("commit")

    async def rollback(self) -> None:
        self.ended.append("rollback")


def stored_layout(version: int) -> PageLayout:
    return PageLayout(subject_kind="craft", subject_slug="Bagh-Print", version=version, entries=[])


@pytest.fixture
def written(monkeypatch: pytest.MonkeyPatch) -> list[tuple[WorkSubject, Sequence[PageLayoutEntry]]]:
    seen: list[tuple[WorkSubject, Sequence[PageLayoutEntry]]] = []

    async def subject(session: Any, kind: str, slug: str) -> WorkSubject:
        found = {(each.kind, each.slug): each for each in (BAGH, TEXTILES)}.get((kind, slug))
        if found is None:
            raise InvalidInput(f"No {kind} has the slug {slug}; find_crafts gives the slugs.")
        return found

    async def layout(session: Any, found: WorkSubject) -> PageLayout | None:
        return stored_layout(2) if found is BAGH else None

    async def store(
        session: Any, found: WorkSubject, entries: Sequence[PageLayoutEntry], *, actor: Any
    ) -> PageLayout:
        seen.append((found, entries))
        return stored_layout(3)

    monkeypatch.setattr(page_layout_proposals, "subject_by_key", subject)
    monkeypatch.setattr(page_layout_proposals, "layout_of", layout)
    monkeypatch.setattr(page_layout_proposals, "store_layout", store)
    return seen


async def proposed(
    user: User, body: dict[str, Any], origin: str = "AGENT"
) -> tuple[LayoutProposalResult, FakeSession]:
    session = FakeSession()
    opened: Any = session
    draft = LayoutProposalDraft.model_validate(body)
    result = await page_layout_proposals.propose_layout(
        opened, user, draft, origin=origin, site=SITE, now=NOW
    )
    return result, session


async def test_a_researcher_s_layout_waits_for_review_and_writes_nothing(written: list[Any]) -> None:
    result, session = await proposed(person("RESEARCHER"), BODY)
    assert (result.outcome, result.status, result.version, result.page_url) == (
        "STORED",
        "PENDING",
        None,
        f"{SITE}/crafts/Bagh-Print",
    )
    (row,) = session.added
    assert isinstance(row, LayoutProposal)
    assert (row.subjectKind, row.craftId, row.categoryId, row.baseVersion, row.origin, row.note) == (
        "craft",
        BAGH.id,
        None,
        2,
        "AGENT",
        "Lead.",
    )
    assert row.entries == [HERO] and written == []


async def test_an_admin_s_layout_is_written_at_once_as_the_next_version(written: list[Any]) -> None:
    admin = person("ADMIN")
    result, session = await proposed(admin, BODY, origin="CONTRIBUTION")
    assert (result.outcome, result.status, result.version) == ("WRITTEN", "APPROVED", 3)
    (row,) = session.added
    assert (row.status, row.reviewedById, row.reviewedAt, row.layoutVersion) == ("APPROVED", admin.id, NOW, 3)
    assert [(subject, [entry.ref for entry in entries]) for subject, entries in written] == [
        (BAGH, [HERO["ref"]])
    ]


async def test_a_layout_built_on_an_old_version_or_for_no_page_is_refused(written: list[Any]) -> None:
    with pytest.raises(Refused, match="at version 2, not 1") as stale:
        await proposed(person("RESEARCHER"), BODY | {"baseVersion": 1})
    assert stale.value.reason == STALE_LAYOUT
    with pytest.raises(InvalidInput, match="No family has the slug"):
        await proposed(person("RESEARCHER"), BODY | {"subject": {"kind": "family", "slug": "Bagh-Print"}})
    category = {
        "subject": {"kind": "category", "slug": "Textile-Craft-Category"},
        "baseVersion": 0,
        "entries": [],
    }
    result, session = await proposed(person("PROFESSOR"), category)
    assert result.status == "PENDING" and (session.added[0].craftId, session.added[0].categoryId) == (
        None,
        TEXTILES.id,
    )


def mcp_context(
    role: str | None, scopes: frozenset[str] = frozenset({READ_SCOPE, CONTRIBUTE_SCOPE})
) -> ToolContext:
    session: Any = FakeSession()
    user = None if role is None else person(role)
    return ToolContext(session=session, index=CraftIndexStore(), site=SITE, user=user, scopes=scopes)


async def call_tool(arguments: dict[str, Any], tool_context: ToolContext) -> dict[str, Any]:
    message = {
        "jsonrpc": "2.0",
        "id": 8,
        "method": "tools/call",
        "params": {"name": "propose_page", "arguments": arguments},
    }
    reply = await answer(message, tool_context)
    assert reply is not None and "result" in reply, reply
    return reply["result"]


async def test_a_layout_is_proposed_over_mcp_as_a_bundle_of_one_part() -> None:
    reply = await answer({"jsonrpc": "2.0", "id": 1, "method": "tools/list"}, mcp_context(None))
    assert reply is not None
    names = {tool["name"] for tool in reply["result"]["tools"]}
    assert "propose_layout" not in names and "get_layout" not in names
    assert TOOLS["propose_page"].scope == CONTRIBUTE_SCOPE
    assert TOOLS["propose_page"].annotations["readOnlyHint"] is False


async def test_an_agent_s_layout_alone_goes_to_the_page_proposal_as_the_agent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen: list[tuple[PageBundle, str]] = []

    async def proposed(session: Any, bundle: PageBundle, user: User, *, origin: str, site: str) -> Any:
        seen.append((bundle, origin))
        return PageProposalResult(
            subject=PageSubject(kind="craft", slug="Bagh-Print"),
            page_url=f"{site}/crafts/Bagh-Print",
            accepted=1,
            refused=0,
            parts=[],
            message="1 of 1.",
        )

    monkeypatch.setattr(mcp_page_tools, "page_proposed", proposed)
    layout = {"base_version": BODY["baseVersion"], "entries": [HERO], "note": BODY["note"]}
    bundle = {"subject": BODY["subject"], "layout": layout}
    stored = await call_tool({"bundle": bundle}, mcp_context("RESEARCHER"))
    assert stored["isError"] is False and stored["structuredContent"]["accepted"] == 1
    ((sent, origin),) = seen
    assert origin == "AGENT" and sent.layout is not None
    assert (sent.layout.base_version, sent.layout.entries[0].ref, sent.layout.note) == (
        2,
        HERO["ref"],
        "Lead.",
    )
    student = await call_tool({"bundle": bundle}, mcp_context("STUDENT"))
    assert student["isError"] is True and "Researcher or above" in student["content"][0]["text"]
    assert len(seen) == 1


def http(role: str, monkeypatch: pytest.MonkeyPatch, outcome: Any) -> TestClient:
    async def accepted(session: Any, user: User) -> None:
        return None

    async def propose(session: Any, user: User, draft: Any, *, origin: str, site: str, now: datetime) -> Any:
        assert origin == "CONTRIBUTION"
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

    monkeypatch.setattr(knowledge_writes, "require_terms", accepted)
    monkeypatch.setattr(knowledge_writes, "propose_layout", propose)
    app = create_app()
    app.dependency_overrides[get_current_user] = lambda: person(role)

    async def opened() -> AsyncIterator[Any]:
        yield FakeSession()

    app.dependency_overrides[get_session] = opened
    return TestClient(app)


@pytest.mark.parametrize(
    ("role", "outcome", "status"),
    [
        ("RESEARCHER", RESULT, 200),
        ("RESEARCHER", Refused(STALE_LAYOUT, "The layout of Bagh-Print is at version 3, not 2."), 409),
        ("RESEARCHER", InvalidInput("No craft has the slug Bagh-Print."), 422),
        ("STUDENT", RESULT, 403),
    ],
)
def test_the_knowledge_api_takes_a_layout_proposal_with_its_status(
    monkeypatch: pytest.MonkeyPatch, role: str, outcome: Any, status: int
) -> None:
    response = http(role, monkeypatch, outcome).post("/api/knowledge/layouts", json=BODY)
    assert response.status_code == status
    if status == 200:
        assert response.json()["proposalId"] == str(RESULT.proposal_id)


def test_a_malformed_layout_is_refused_before_anything_runs(monkeypatch: pytest.MonkeyPatch) -> None:
    twice = BODY | {"entries": [HERO, HERO | {"order": 2}]}
    assert (
        http("RESEARCHER", monkeypatch, AssertionError("ran"))
        .post("/api/knowledge/layouts", json=twice)
        .status_code
        == 422
    )
