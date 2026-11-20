import uuid
from datetime import UTC, datetime
from typing import Any

import pytest

from app.api import mcp_steward_tools, mcp_task_tools
from app.api.mcp_tools import ToolContext, answer
from app.core.mcp_scopes import CONTRIBUTE_SCOPE, READ_SCOPE
from app.models import User
from app.research.my_tasks import TaskClaims
from app.research.open_work import TaskHold
from app.research.stewardship import Stewardship
from app.services.craft_resolver import CraftIndexStore

SITE = "https://kalavigyan.example"
UNTIL = datetime(2026, 11, 20, 12, 0, tzinfo=UTC)
KEYS = ["THIN_FIELD:craft:Kutch-Ajrakh:HISTORY", "MISSING_FIELD:craft:Kutch-Ajrakh:POLICY"]
WRITES = {"readOnlyHint": False, "destructiveHint": False, "openWorldHint": False}


class FakeSession:
    def __init__(self) -> None:
        self.commits = 0

    async def commit(self) -> None:
        self.commits += 1

    async def rollback(self) -> None:
        return None


def context(role: str | None = "RESEARCHER", *scopes: str) -> ToolContext:
    user = (
        None if role is None else User(id=uuid.UUID(int=77), name="Steward", email="s@example.org", role=role)
    )
    granted = frozenset(scopes or (READ_SCOPE, CONTRIBUTE_SCOPE))
    return ToolContext(session=FakeSession(), index=CraftIndexStore(), site=SITE, user=user, scopes=granted)  # type: ignore[arg-type]


async def call(name: str, arguments: dict[str, Any], tool_context: ToolContext) -> dict[str, Any]:
    message = {
        "jsonrpc": "2.0",
        "id": 4,
        "method": "tools/call",
        "params": {"name": name, "arguments": arguments},
    }
    reply = await answer(message, tool_context)
    assert reply is not None and "result" in reply, reply
    return reply["result"]


async def test_the_task_and_steward_tools_are_listed_with_their_hints() -> None:
    reply = await answer({"jsonrpc": "2.0", "id": 1, "method": "tools/list"}, context())
    assert reply is not None
    tools = {tool["name"]: tool for tool in reply["result"]["tools"]}
    for name in ("claim_tasks", "adopt_craft", "drop_craft", "my_crafts"):
        assert tools[name]["annotations"] == WRITES, name
    assert tools["my_tasks"]["annotations"]["readOnlyHint"] is True
    assert tools["claim_tasks"]["inputSchema"]["properties"]["task_keys"]["maxItems"] == 10
    assert tools["adopt_craft"]["inputSchema"]["required"] == ["craft_slug"]
    assert "new 5, established 10, proven 20" in tools["claim_tasks"]["description"]


async def test_several_tasks_are_claimed_in_one_call_and_the_old_name_is_answered(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    asked: list[tuple[uuid.UUID, list[str]]] = []

    async def claim_tasks(
        session: Any, user_id: uuid.UUID, keys: list[str], *, site: str, now: datetime
    ) -> TaskClaims:
        asked.append((user_id, keys))
        held = [TaskHold(task_key=key, held=True, reserved_until=UNTIL) for key in keys]
        return TaskClaims(held=held, refused=[], tier="NEW", holding=2, holding_max=5, message="Reserved 2.")

    monkeypatch.setattr(mcp_task_tools.task_reservations, "claim_tasks", claim_tasks)
    tool_context = context()
    result = await call("claim_tasks", {"taskKeys": KEYS}, tool_context)
    assert result["isError"] is False
    assert [item["taskKey"] for item in result["structuredContent"]["held"]] == KEYS
    assert result["structuredContent"]["notices"][0].startswith("taskKeys is the old name of task_keys")
    assert asked == [(uuid.UUID(int=77), KEYS)]
    assert tool_context.session.commits == 1  # type: ignore[attr-defined]


async def test_claiming_and_my_tasks_need_a_signed_in_connection_with_the_contribute_scope() -> None:
    anonymous = await call("claim_tasks", {"task_keys": KEYS}, context(None))
    assert anonymous["isError"] is True and "signed-in connection" in anonymous["content"][0]["text"]
    unscoped = await call("my_tasks", {}, context("RESEARCHER", READ_SCOPE))
    assert unscoped["isError"] is True and "contribute scope" in unscoped["content"][0]["text"]


async def test_stewardship_is_for_accounts_that_may_contribute(monkeypatch: pytest.MonkeyPatch) -> None:
    dropped: list[str] = []

    async def drop_craft(session: Any, user: User, slug: str, *, now: datetime) -> Stewardship:
        dropped.append(slug)
        return Stewardship(craft_slug=slug, adopted=False, message="Dropped.")

    monkeypatch.setattr(mcp_steward_tools.stewardship, "drop_craft", drop_craft)
    student = await call("drop_craft", {"craft_slug": "Kutch-Ajrakh"}, context("STUDENT"))
    assert student["isError"] is True and "Researcher or above" in student["content"][0]["text"]
    assert dropped == []
    researcher = await call("drop_craft", {"craftSlug": "Kutch-Ajrakh"}, context())
    assert (researcher["isError"], researcher["structuredContent"]["adopted"]) == (False, False)
    assert dropped == ["Kutch-Ajrakh"]
