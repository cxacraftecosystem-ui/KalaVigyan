import uuid
from datetime import UTC, datetime
from typing import Any

import pytest

from app.api import mcp_work_tools
from app.api.mcp_tools import ToolContext, answer
from app.core.errors import InvalidInput
from app.models import User
from app.research.my_tasks import TaskClaims
from app.research.open_work import OpenWork, TaskHold, Viewer, WorkFilters
from app.services.craft_resolver import CraftIndexStore

SITE = "https://kalavigyan.example"
USER_ID = uuid.UUID("0d000000-0000-4000-8000-000000000001")
UNTIL = datetime(2026, 11, 19, 14, 0, tzinfo=UTC)
KEY = "THIN_FIELD:craft:Kutch-Ajrakh:HISTORY"
WRITES = {"readOnlyHint": False, "destructiveHint": False, "openWorldHint": False}
RETIRED = {"claim_task", "claim_tasks", "release_task", "my_tasks", "my_crafts", "adopt_craft", "drop_craft"}


class FakeSession:
    def __init__(self) -> None:
        self.commits = 0
        self.rollbacks = 0

    async def commit(self) -> None:
        self.commits += 1

    async def rollback(self) -> None:
        self.rollbacks += 1


def context(*scopes: str, role: str | None = "RESEARCHER", session: Any = None) -> ToolContext:
    user = None if role is None else User(id=USER_ID, name="Contributor", email="c@example.org", role=role)
    return ToolContext(
        session=session or FakeSession(),
        index=CraftIndexStore(),
        site=SITE,
        user=user,
        scopes=frozenset(scopes),
    )


def request(method: str, params: dict[str, Any] | None = None, request_id: Any = 1) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": request_id, "method": method, "params": params or {}}


async def call(name: str, arguments: dict[str, Any], tool_context: ToolContext) -> dict[str, Any]:
    reply = await answer(request("tools/call", {"name": name, "arguments": arguments}), tool_context)
    assert reply is not None and "result" in reply, reply
    return reply["result"]


def claims(held: list[str]) -> TaskClaims:
    holds = [TaskHold(task_key=key, held=True, reserved_until=UNTIL) for key in held]
    return TaskClaims(
        held=holds, refused=[], tier="NEW", holding=len(held), holding_max=5, message="Reserved."
    )


async def test_the_work_tools_are_listed_in_the_work_group_with_their_hints() -> None:
    reply = await answer(request("tools/list"), context())
    assert reply is not None
    tools = {tool["name"]: tool for tool in reply["result"]["tools"]}
    assert not RETIRED & set(tools)
    for name in ("list_open_work", "my_work", "reserve_tasks", "steward_craft", "get_proposal"):
        assert tools[name]["_meta"]["kalavigyan/group"] == "work", name
    for name in ("list_open_work", "my_work", "get_proposal"):
        assert tools[name]["annotations"]["readOnlyHint"] is True, name
    for name in ("reserve_tasks", "steward_craft"):
        assert tools[name]["annotations"] == WRITES, name
    reserve = tools["reserve_tasks"]["inputSchema"]["properties"]
    assert reserve["claim"]["maxItems"] == reserve["release"]["maxItems"] == 10
    assert "new 5, established 10, proven 20" in tools["reserve_tasks"]["description"]
    assert set(tools["steward_craft"]["inputSchema"]["required"]) == {"craft_slug", "action"}


async def test_reserving_needs_a_signed_in_connection_with_the_contribute_scope() -> None:
    anonymous = await call("reserve_tasks", {"claim": [KEY]}, context(role=None))
    assert anonymous["isError"] is True and "signed-in connection" in anonymous["content"][0]["text"]
    unscoped = await call("reserve_tasks", {"claim": [KEY]}, context("read"))
    assert unscoped["isError"] is True and "contribute scope" in unscoped["content"][0]["text"]
    empty = await call("reserve_tasks", {}, context("contribute"))
    assert empty["isError"] is True and "to claim, to release, or both" in empty["content"][0]["text"]


async def test_open_work_is_filtered_by_one_subject_at_most() -> None:
    result = await call(
        "list_open_work", {"craft_slug": "Kutch-Ajrakh", "family_slug": "Cane-Bamboo-Craft"}, context()
    )
    assert result["isError"] is True and "not several" in result["content"][0]["text"]


@pytest.mark.parametrize(
    ("scopes", "role", "expected"),
    [
        ((), None, Viewer()),
        (("read", "contribute"), "ADMIN", Viewer(user_id=USER_ID)),
        (("read", "review"), "ADMIN", Viewer(user_id=USER_ID, review_role="ADMIN")),
    ],
)
async def test_review_queues_reach_only_a_connection_holding_the_review_scope(
    monkeypatch: pytest.MonkeyPatch, scopes: tuple[str, ...], role: str | None, expected: Viewer
) -> None:
    seen: dict[str, Any] = {}

    async def listed(
        session: Any, filters: WorkFilters, viewer: Viewer, *, site: str, now: datetime
    ) -> OpenWork:
        seen.update(filters=filters, viewer=viewer, site=site)
        return OpenWork(filters=filters, total=0, reservation_minutes=120, tasks=[])

    monkeypatch.setattr(mcp_work_tools.open_work, "list_open_work", listed)
    result = await call(
        "list_open_work", {"craft_slug": "Kutch-Ajrakh", "field": "HISTORY"}, context(*scopes, role=role)
    )
    assert result["isError"] is False
    assert seen["viewer"] == expected and seen["site"] == SITE
    assert seen["filters"] == WorkFilters(craft_slug="Kutch-Ajrakh", field="HISTORY")
    assert result["structuredContent"]["filters"]["craftSlug"] == "Kutch-Ajrakh"


async def test_releases_run_before_claims_and_a_refused_release_is_listed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    order: list[str] = []
    other = "MISSING_FIELD:craft:Kutch-Ajrakh:POLICY"

    async def release(session: Any, user_id: uuid.UUID, key: str, *, now: datetime) -> TaskHold:
        order.append(f"release {key}")
        if key == other:
            raise InvalidInput(f"You hold no reservation of {key}.")
        return TaskHold(task_key=key, held=False, reserved_until=None)

    async def claim(
        session: Any, user_id: uuid.UUID, keys: list[str], *, site: str, now: datetime
    ) -> TaskClaims:
        order.append(f"claim {', '.join(keys)}")
        return claims(keys)

    monkeypatch.setattr(mcp_work_tools.task_reservations, "release_task", release)
    monkeypatch.setattr(mcp_work_tools.task_reservations, "claim_tasks", claim)
    session = FakeSession()
    arguments = {"release": [KEY, other], "claim": ["SECTION:craft:Kutch-Ajrakh:HISTORY"]}
    shown = (await call("reserve_tasks", arguments, context("contribute", session=session)))[
        "structuredContent"
    ]
    assert order == [f"release {KEY}", f"release {other}", "claim SECTION:craft:Kutch-Ajrakh:HISTORY"]
    assert [hold["taskKey"] for hold in shown["released"]] == [KEY]
    assert shown["refused"] == [{"taskKey": other, "problem": f"You hold no reservation of {other}."}]
    assert [hold["taskKey"] for hold in shown["held"]] == ["SECTION:craft:Kutch-Ajrakh:HISTORY"]
    assert session.commits == 1
    gave_back = (await call("reserve_tasks", {"release": [KEY]}, context("contribute")))["structuredContent"]
    assert gave_back["message"] == "Gave back 1 tasks and refused 0; this account now holds 0 of its 5."


async def test_a_refused_call_rolls_back(monkeypatch: pytest.MonkeyPatch) -> None:
    async def refused(*args: Any, **kwargs: Any) -> TaskClaims:
        raise InvalidInput("No open task has the key; list_open_work gives the open tasks.")

    monkeypatch.setattr(mcp_work_tools.task_reservations, "claim_tasks", refused)
    session = FakeSession()
    result = await call("reserve_tasks", {"claim": [KEY]}, context("contribute", session=session))
    assert result["isError"] is True and "list_open_work" in result["content"][0]["text"]
    assert (session.commits, session.rollbacks) == (0, 1)
