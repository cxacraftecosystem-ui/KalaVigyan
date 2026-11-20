import uuid
from typing import Any

import pytest

from app.api import mcp_source_tools
from app.api.mcp_tools import ToolContext, answer
from app.core.errors import ExternalFailure
from app.core.mcp_scopes import CONTRIBUTE_SCOPE, READ_SCOPE
from app.models import User
from app.research.source_proposals import SourceProposal, SourceProposalReply
from app.services.craft_resolver import CraftIndexStore

from ..knowledge_writes.fakes import PAGE_URL, QUOTE, fact_id

SITE = "https://kalavigyan.example"
HELD = fact_id("held-claim")
PROPOSAL = {
    "claimId": str(HELD),
    "sources": [
        {"url": PAGE_URL, "title": "Indigo in Ajrakh", "quotes": [{"text": QUOTE, "locator": "p. 2"}]}
    ],
    "taskKey": "RESOURCE_FACT:craft:Kutch-Ajrakh:PROCESS",
}
REPLY = SourceProposalReply(
    outcome="ADDED", claim_id=HELD, quotes_added=1, held=False, gates=[], message="Added: 1 quote."
)


class EndedSession:
    async def commit(self) -> None:
        return None

    async def rollback(self) -> None:
        return None


def context(
    role: str | None, scopes: frozenset[str] = frozenset({READ_SCOPE, CONTRIBUTE_SCOPE})
) -> ToolContext:
    user = (
        None if role is None else User(id=uuid.UUID(int=31), name="Owner", email="s@example.org", role=role)
    )
    return ToolContext(session=EndedSession(), index=CraftIndexStore(), site=SITE, user=user, scopes=scopes)  # type: ignore[arg-type]


async def call(arguments: dict[str, Any], tool_context: ToolContext) -> dict[str, Any]:
    message = {
        "jsonrpc": "2.0",
        "id": 4,
        "method": "tools/call",
        "params": {"name": "propose_source", "arguments": arguments},
    }
    reply = await answer(message, tool_context)
    assert reply is not None and "result" in reply, reply
    return reply["result"]


def answered(outcome: Any, seen: list[tuple[SourceProposal, str, str]]) -> Any:
    async def source_proposed(
        session: Any, proposal: SourceProposal, user: User, *, origin: str, site: str
    ) -> SourceProposalReply:
        seen.append((proposal, origin, site))
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

    return source_proposed


async def test_propose_source_is_listed_as_a_write_needing_the_contribute_scope() -> None:
    reply = await answer({"jsonrpc": "2.0", "id": 1, "method": "tools/list"}, context(None))
    assert reply is not None
    (tool,) = [tool for tool in reply["result"]["tools"] if tool["name"] == "propose_source"]
    assert tool["annotations"] == {"readOnlyHint": False, "destructiveHint": False, "openWorldHint": False}
    assert tool["inputSchema"]["required"] == ["proposal"]
    assert mcp_source_tools.PROPOSE_SOURCE.scope == CONTRIBUTE_SCOPE


@pytest.mark.parametrize(
    ("tool_context", "said"),
    [
        (context(None), "needs a signed-in connection"),
        (context("RESEARCHER", frozenset({READ_SCOPE})), "needs the contribute scope"),
        (context("STUDENT"), "Researcher or above"),
    ],
)
async def test_a_source_without_sign_in_scope_or_rank_is_a_tool_error(
    monkeypatch: pytest.MonkeyPatch, tool_context: ToolContext, said: str
) -> None:
    seen: list[tuple[SourceProposal, str, str]] = []
    monkeypatch.setattr(mcp_source_tools, "source_proposed", answered(REPLY, seen))
    result = await call({"proposal": PROPOSAL}, tool_context)
    assert result["isError"] is True and said in result["content"][0]["text"]
    assert seen == []


async def test_an_agent_s_source_runs_with_the_agent_origin_and_an_outage_is_correctable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen: list[tuple[SourceProposal, str, str]] = []
    monkeypatch.setattr(mcp_source_tools, "source_proposed", answered(REPLY, seen))
    result = await call({"proposal": PROPOSAL}, context("RESEARCHER"))
    assert result["isError"] is False
    assert (result["structuredContent"]["outcome"], result["structuredContent"]["quotesAdded"]) == (
        "ADDED",
        1,
    )
    ((proposal, origin, site),) = seen
    assert (proposal.claim_id, origin, site) == (HELD, "AGENT", SITE)
    outage = ExternalFailure("the fetcher did not answer", kind="unavailable", retryable=True)
    monkeypatch.setattr(mcp_source_tools, "source_proposed", answered(outage, []))
    failed = await call({"proposal": PROPOSAL}, context("RESEARCHER"))
    assert failed["isError"] is True and "call propose_source again later" in failed["content"][0]["text"]
