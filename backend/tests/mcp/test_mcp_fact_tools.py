import uuid
from datetime import UTC, datetime
from typing import Any

import pytest

from app.api import mcp_fact_tools
from app.api.mcp_tools import ToolContext, answer
from app.core.mcp_scopes import CONTRIBUTE_SCOPE, READ_SCOPE
from app.models import User
from app.research.contribution_queue import BatchItem, ProposalTicket
from app.research.knowledge_writes import FactProposal
from app.services import contribution_queue
from app.services.contribution_queue import QueuedFact
from app.services.craft_resolver import CraftIndexStore

from ..knowledge_writes.fakes import PAGE_URL, QUOTE, STATEMENT

SITE = "https://kalavigyan.example"
QUEUED_AT = datetime(2026, 11, 20, 9, 0, tzinfo=UTC)
SOURCE = {"url": PAGE_URL, "title": "Indigo in Ajrakh", "quotes": [{"text": QUOTE, "locator": "p. 2"}]}
FACT = {"craft_slug": "Kutch-Ajrakh", "field": "PROCESS", "statement": STATEMENT, "sources": [SOURCE]}
TASK_KEY = "THIN_FIELD:craft:Kutch-Ajrakh:PROCESS"


class EndedSession:
    def __init__(self) -> None:
        self.ended: list[str] = []

    async def commit(self) -> None:
        self.ended.append("commit")

    async def rollback(self) -> None:
        self.ended.append("rollback")


def context(
    role: str | None, scopes: frozenset[str] = frozenset({READ_SCOPE, CONTRIBUTE_SCOPE})
) -> ToolContext:
    user = (
        None
        if role is None
        else User(id=uuid.UUID(int=21), name="An Agent's Owner", email="o@example.org", role=role)
    )
    return ToolContext(session=EndedSession(), index=CraftIndexStore(), site=SITE, user=user, scopes=scopes)  # type: ignore[arg-type]


async def call(name: str, arguments: dict[str, Any], tool_context: ToolContext) -> dict[str, Any]:
    message = {
        "jsonrpc": "2.0",
        "id": 3,
        "method": "tools/call",
        "params": {"name": name, "arguments": arguments},
    }
    reply = await answer(message, tool_context)
    assert reply is not None and "result" in reply, reply
    return reply["result"]


def ticket(fact: QueuedFact) -> ProposalTicket:
    return ProposalTicket(
        proposal_id=uuid.UUID(int=1000 + fact.index),
        state="QUEUED",
        idempotency_key=fact.key or f"fact:{fact.index:040d}",
        subject=fact.proposal.subject,
        field=fact.proposal.field,
        statement=fact.proposal.statement,
        task_key=fact.proposal.task_key,
        position=fact.index,
        attempts=0,
        queued_at=QUEUED_AT,
        message="Queued.",
    )


def queued(seen: list[tuple[list[QueuedFact], str]]) -> Any:
    async def enqueue(
        session: Any, user: User, facts: list[QueuedFact], *, origin: str, now: datetime
    ) -> Any:
        seen.append((list(facts), origin))
        items = [
            BatchItem(index=fact.index, accepted=True, idempotency_key=fact.key, ticket=ticket(fact))
            for fact in facts
        ]
        return contribution_queue.batch_of(items)

    return enqueue


async def test_the_fact_tools_are_listed_with_their_scopes_groups_and_hints() -> None:
    reply = await answer({"jsonrpc": "2.0", "id": 1, "method": "tools/list"}, context(None))
    assert reply is not None
    tools = {tool["name"]: tool for tool in reply["result"]["tools"]}
    assert "propose_fact" not in tools
    assert tools["propose_facts"]["annotations"]["readOnlyHint"] is False
    assert tools["propose_facts"]["_meta"]["kalavigyan/group"] == "proposing"
    assert tools["get_proposal"]["annotations"]["readOnlyHint"] is True
    assert tools["get_proposal"]["_meta"]["kalavigyan/group"] == "work"
    batch = tools["propose_facts"]["inputSchema"]
    assert batch["properties"]["facts"]["maxItems"] == 25
    single = batch["$defs"]["FactFields"]
    assert {
        "craft_slug",
        "category_slug",
        "field",
        "statement",
        "sources",
        "task_key",
        "idempotency_key",
    } <= set(single["properties"])
    assert set(single["required"]) == {"field", "statement", "sources"}
    assert all(tool.scope == CONTRIBUTE_SCOPE for tool in mcp_fact_tools.FACT_TOOLS)


@pytest.mark.parametrize(
    ("tool_context", "said"),
    [
        (context(None), "needs a signed-in connection"),
        (context("RESEARCHER", frozenset({READ_SCOPE})), "needs the contribute scope"),
        (context("STUDENT"), "Researcher or above"),
    ],
)
async def test_a_proposal_without_sign_in_scope_or_rank_is_a_tool_error(
    monkeypatch: pytest.MonkeyPatch, tool_context: ToolContext, said: str
) -> None:
    seen: list[tuple[list[QueuedFact], str]] = []
    monkeypatch.setattr(mcp_fact_tools.contribution_queue, "enqueue_facts", queued(seen))
    result = await call("propose_facts", {"facts": [FACT]}, tool_context)
    assert result["isError"] is True and said in result["content"][0]["text"]
    assert seen == []


async def test_one_fact_is_a_batch_of_one_queued_with_the_agent_origin_and_answered_at_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen: list[tuple[list[QueuedFact], str]] = []
    monkeypatch.setattr(mcp_fact_tools.contribution_queue, "enqueue_facts", queued(seen))
    tool_context = context("RESEARCHER")
    result = await call(
        "propose_facts", {"facts": [FACT | {"idempotency_key": "agent-run-7:fact-1"}]}, tool_context
    )
    assert result["isError"] is False
    structured = result["structuredContent"]
    (item,) = structured["items"]
    assert (item["ticket"]["state"], item["idempotencyKey"], structured["notices"]) == (
        "QUEUED",
        "agent-run-7:fact-1",
        [],
    )
    (([fact], origin),) = seen
    assert origin == "AGENT"
    assert fact.proposal == FactProposal.model_validate(
        {
            "subject": {"kind": "craft", "slug": "Kutch-Ajrakh"},
            "field": "PROCESS",
            "statement": STATEMENT,
            "sources": [SOURCE],
        }
    )
    assert tool_context.session.ended == ["commit"]  # type: ignore[attr-defined]


async def test_an_old_name_inside_a_fact_still_works_and_says_so(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[tuple[list[QueuedFact], str]] = []
    monkeypatch.setattr(mcp_fact_tools.contribution_queue, "enqueue_facts", queued(seen))
    renamed = await call("propose_facts", {"facts": [FACT | {"taskKey": TASK_KEY}]}, context("RESEARCHER"))
    assert renamed["structuredContent"]["notices"] == [
        "taskKey is the old name of task_key; it works until the next release, so pass task_key from now on."
    ]
    (([fact], _),) = seen
    assert (fact.proposal.subject.slug, fact.proposal.task_key) == ("Kutch-Ajrakh", TASK_KEY)


async def test_a_retired_tool_name_is_an_unknown_tool() -> None:
    reply = await answer(
        {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {"name": "propose_fact", "arguments": FACT},
        },
        context("RESEARCHER"),
    )
    assert reply is not None and reply["error"]["code"] == -32602


async def test_a_malformed_fact_is_refused_by_its_index_with_a_correctable_problem(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(mcp_fact_tools.contribution_queue, "enqueue_facts", queued([]))
    for changes, said in (
        ({"category_slug": "Textiles"}, "one of them"),
        ({"field": "ASTROLOGY"}, "field:"),
        ({"fields": ["PROCESS"]}, "secondary fields are distinct"),
    ):
        result = await call("propose_facts", {"facts": [FACT | changes]}, context("RESEARCHER"))
        structured = result["structuredContent"]
        assert (result["isError"], structured["accepted"], structured["refused"]) == (False, 0, 1)
        assert said in structured["items"][0]["problem"], said


async def test_a_batch_queues_each_good_fact_and_refuses_each_malformed_one_by_its_index(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen: list[tuple[list[QueuedFact], str]] = []
    monkeypatch.setattr(mcp_fact_tools.contribution_queue, "enqueue_facts", queued(seen))
    facts = [
        FACT | {"idempotency_key": "batch-key-0"},
        FACT | {"field": "ASTROLOGY", "idempotency_key": "batch-key-1"},
        FACT | {"statement": STATEMENT + " Each dip lasts minutes.", "idempotency_key": "batch-key-2"},
    ]
    result = await call("propose_facts", {"facts": facts}, context("RESEARCHER"))
    assert result["isError"] is False
    structured = result["structuredContent"]
    assert (structured["accepted"], structured["refused"]) == (2, 1)
    assert [(item["index"], item["accepted"], item["idempotencyKey"]) for item in structured["items"]] == [
        (0, True, "batch-key-0"),
        (1, False, "batch-key-1"),
        (2, True, "batch-key-2"),
    ]
    assert structured["items"][1]["problem"].startswith("field:")
    ((batch, _),) = seen
    assert [fact.index for fact in batch] == [0, 2]


async def test_a_batch_of_more_than_twenty_five_facts_is_refused_whole(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(mcp_fact_tools.contribution_queue, "enqueue_facts", queued([]))
    result = await call("propose_facts", {"facts": [FACT] * 26}, context("RESEARCHER"))
    assert result["isError"] is True and "facts" in result["content"][0]["text"]


async def test_a_proposal_s_progress_needs_a_signed_in_connection() -> None:
    result = await call("get_proposal", {"proposal_id": str(uuid.UUID(int=5))}, context(None))
    assert result["isError"] is True and "signed-in connection" in result["content"][0]["text"]
