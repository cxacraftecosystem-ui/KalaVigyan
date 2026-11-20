import uuid
from typing import Any

import pytest

from app.api import mcp_source_tools, mcp_structure_tools
from app.api.mcp_argument_names import camel_keys
from app.api.mcp_tools import TOOLS, ToolContext, answer
from app.core.mcp_scopes import CONTRIBUTE_SCOPE, READ_SCOPE
from app.models import User
from app.research.source_proposals import SourceProposal, SourceProposalReply
from app.research.structure_proposals import StructureProposal, StructureProposalResult, StructureSubject
from app.services.craft_resolver import CraftIndexStore

from ..knowledge_writes.fakes import PAGE_URL, QUOTE, fact_id
from ..structure.pages import NAME_QUOTE, SLUG, source

SITE = "https://kalavigyan.example"
HELD = fact_id("held-claim")
TASK = "RESOURCE_FACT:craft:Kutch-Ajrakh:PROCESS"
SNAKE_SOURCE = {
    "claim_id": str(HELD),
    "sources": [
        {"url": PAGE_URL, "title": "Indigo in Ajrakh", "quotes": [{"text": QUOTE, "locator": "p. 2"}]}
    ],
    "task_key": TASK,
}
CAMEL_SOURCE = {"claimId": str(HELD), "sources": SNAKE_SOURCE["sources"], "taskKey": TASK}
WHY = {
    "subject": {"kind": "craft", "slug": SLUG},
    "field": "HISTORY",
    "statement": "Printers in the delta call the cloth ajrak, after their word for blue.",
    "sources": [source(NAME_QUOTE)],
}
SOURCE_REPLY = SourceProposalReply(
    outcome="ADDED", claim_id=HELD, quotes_added=1, held=False, gates=[], message="Added: 1 quote."
)
STRUCTURE_REPLY = StructureProposalResult(
    outcome="STORED",
    proposal_id=uuid.UUID(int=77),
    status="PENDING",
    kind="STAGE_WHY",
    subject=StructureSubject(slug=SLUG),
    checks=[],
    page_url=f"{SITE}/crafts/{SLUG}",
    message="Stored for review.",
)


class Ended:
    async def commit(self) -> None:
        return None

    async def rollback(self) -> None:
        return None


def researcher() -> ToolContext:
    user = User(id=uuid.UUID(int=41), name="Researcher", email="r@example.org", role="RESEARCHER")
    session: Any = Ended()
    scopes = frozenset({READ_SCOPE, CONTRIBUTE_SCOPE})
    return ToolContext(session=session, index=CraftIndexStore(), site=SITE, user=user, scopes=scopes)


async def call(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    message = {
        "jsonrpc": "2.0",
        "id": 5,
        "method": "tools/call",
        "params": {"name": name, "arguments": arguments},
    }
    reply = await answer(message, researcher())
    assert reply is not None and "result" in reply, reply
    return reply["result"]


def property_names(schema: Any) -> set[str]:
    found: set[str] = set()
    pending = [schema]
    while pending:
        current = pending.pop()
        if isinstance(current, dict):
            found |= (
                set(current.get("properties", {})) if isinstance(current.get("properties"), dict) else set()
            )
            pending += list(current.values())
        elif isinstance(current, list):
            pending += current
    return found


@pytest.fixture
def seen(monkeypatch: pytest.MonkeyPatch) -> list[Any]:
    calls: list[Any] = []

    async def sourced(session: Any, proposal: SourceProposal, user: User, *, origin: str, site: str) -> Any:
        calls.append(proposal)
        return SOURCE_REPLY

    async def structured(
        session: Any, proposal: StructureProposal, user: User, *, origin: str, site: str
    ) -> Any:
        calls.append(proposal)
        return STRUCTURE_REPLY

    monkeypatch.setattr(mcp_source_tools, "source_proposed", sourced)
    monkeypatch.setattr(mcp_structure_tools, "structure_proposed", structured)
    return calls


@pytest.mark.parametrize("name", ["propose_structure", "propose_source"])
def test_the_proposal_body_is_described_and_schemed_in_snake_case(name: str) -> None:
    listed = TOOLS[name].listed()
    names = property_names(listed["inputSchema"])
    assert {"task_key", "schema_version"} <= names
    assert [each for each in names if each != each.lower()] == []
    assert "taskKey" not in listed["description"] and "claimId" not in listed["description"]
    assert "task_key" in listed["description"]


def test_the_structure_items_name_their_parts_in_snake_case() -> None:
    names = property_names(TOOLS["propose_structure"].listed()["inputSchema"])
    assert {
        "stage_key",
        "material_key",
        "botanical_name",
        "claim_ids",
        "reaction_kind",
        "settled_by",
    } <= names
    assert "claim_id" in property_names(TOOLS["propose_source"].listed()["inputSchema"])


async def test_snake_case_bodies_pass_without_notices(seen: list[Any]) -> None:
    sourced = await call("propose_source", {"proposal": SNAKE_SOURCE})
    assert sourced["isError"] is False and sourced["structuredContent"]["notices"] == []
    why = WHY | {"item": {"kind": "STAGE_WHY", "stage_key": "P01"}}
    structured = await call("propose_structure", {"proposal": why})
    assert structured["isError"] is False and structured["structuredContent"]["notices"] == []
    assert seen[0].claim_id == HELD and seen[0].task_key == TASK
    assert seen[1].item.stage_key == "P01"


async def test_old_camel_case_names_still_work_and_say_so(seen: list[Any]) -> None:
    sourced = await call("propose_source", {"proposal": CAMEL_SOURCE})
    assert sourced["isError"] is False
    assert sourced["structuredContent"]["notices"] == [
        "claimId is the old name of claim_id; it works until the next release, so pass claim_id from now on.",
        "taskKey is the old name of task_key; it works until the next release, so pass task_key from now on.",
    ]
    why = WHY | {"item": {"kind": "STAGE_WHY", "stageKey": "P01"}}
    structured = await call("propose_structure", {"proposal": why})
    assert structured["structuredContent"]["notices"] == [
        "stageKey is the old name of stage_key; it works until the next release, so pass stage_key from now on."
    ]
    assert (seen[0].claim_id, seen[0].task_key, seen[1].item.stage_key) == (HELD, TASK, "P01")


def test_camel_keys_are_found_once_each_at_any_depth_in_the_order_met() -> None:
    body = {
        "claimId": 1,
        "sources": [{"url": "u", "quotes": [{"text": "t", "pageNumber": 2}]}, {"pageNumber": 3}],
        "item": {"claimIds": [], "stage_key": "S01"},
    }
    assert camel_keys(body) == ("claimId", "claimIds", "pageNumber")
    assert camel_keys(None) == () and camel_keys(["taskKey"]) == ()
