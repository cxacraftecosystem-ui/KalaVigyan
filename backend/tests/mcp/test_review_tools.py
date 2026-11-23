import uuid
from types import SimpleNamespace
from typing import Any

import pytest

from app.api.mcp_tools import TOOLS, ToolContext, answer
from app.services.craft_resolver import CraftIndexStore

SITE = "https://kalavigyan.example"
ADMIN_TOOLS = ("review_queue", "stage_reviews", "refresh_pages", "admin_reports")
DECISION = {"kind": "FACTS", "id": str(uuid.uuid4()), "action": "approve", "reason": "Both quotes say this."}


class FakeSession:
    def __init__(self) -> None:
        self.commits = self.rollbacks = 0

    async def commit(self) -> None:
        self.commits += 1

    async def rollback(self) -> None:
        self.rollbacks += 1


def context(role: str | None, *scopes: str) -> ToolContext:
    user = None if role is None else SimpleNamespace(id=uuid.uuid4(), role=role, twoFactorEnabled=True)
    return ToolContext(
        session=FakeSession(),  # type: ignore[arg-type]
        index=CraftIndexStore(),
        site=SITE,
        user=user,  # type: ignore[arg-type]
        scopes=frozenset(scopes),
    )


async def called(tool: str, arguments: dict[str, Any], where: ToolContext) -> dict[str, Any]:
    message = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {"name": tool, "arguments": arguments},
    }
    reply = await answer(message, where)
    assert reply is not None
    return reply["result"]


def said(result: dict[str, Any]) -> str:
    return str(result["content"][0]["text"])


async def test_a_contributor_never_sees_the_admin_tools_and_an_admin_with_review_does() -> None:
    message = {"jsonrpc": "2.0", "id": 1, "method": "tools/list"}
    contributor = await answer(message, context("RESEARCHER", "read", "contribute"))
    admin = await answer(message, context("ADMIN", "read", "review"))
    assert contributor is not None and admin is not None
    names = {tool["name"] for tool in contributor["result"]["tools"]}
    assert names.isdisjoint(ADMIN_TOOLS)
    assert set(ADMIN_TOOLS) <= {tool["name"] for tool in admin["result"]["tools"]}


@pytest.mark.parametrize("tool", ["review_queue", "stage_reviews", "refresh_pages"])
async def test_an_admin_tool_needs_the_review_scope_and_an_admin_account(tool: str) -> None:
    arguments = {"decisions": [DECISION]} if tool == "stage_reviews" else {}
    unscoped = await called(tool, arguments, context("ADMIN", "read", "contribute"))
    assert unscoped["isError"] is True and "review scope" in said(unscoped)
    professor = await called(tool, arguments, context("PROFESSOR", "read", "review"))
    assert professor["isError"] is True and "Admin and Master Admin" in said(professor)


async def test_staging_takes_at_most_twenty_decisions_each_with_a_reason() -> None:
    admin = context("ADMIN", "read", "review")
    many = await called("stage_reviews", {"decisions": [DECISION] * 21}, admin)
    assert many["isError"] is True
    short = await called("stage_reviews", {"decisions": [DECISION | {"reason": "Fine."}]}, admin)
    assert short["isError"] is True and "reason" in said(short)


def test_the_staging_tool_says_plainly_that_nothing_is_published_until_a_person_confirms() -> None:
    description = TOOLS["stage_reviews"].description
    assert "Nothing is published" in description and "never applies what an app proposes" in description
    assert TOOLS["stage_reviews"].annotations["destructiveHint"] is False
    assert TOOLS["review_queue"].annotations["readOnlyHint"] is True
