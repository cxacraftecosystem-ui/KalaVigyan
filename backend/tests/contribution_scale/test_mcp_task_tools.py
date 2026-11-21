import uuid
from datetime import UTC, datetime
from typing import Any

import pytest

from app.api import mcp_work_tools
from app.api.mcp_tools import ToolContext, answer
from app.core.mcp_scopes import CONTRIBUTE_SCOPE, READ_SCOPE
from app.models import User
from app.research.my_tasks import MyTasks, TaskClaims
from app.research.open_work import TaskHold, TaskSubject
from app.research.stewardship import MyCrafts, StewardPackage, Stewardship
from app.services.craft_resolver import CraftIndexStore

SITE = "https://kalavigyan.example"
UNTIL = datetime(2026, 11, 20, 12, 0, tzinfo=UTC)
KEYS = ["THIN_FIELD:craft:Kutch-Ajrakh:HISTORY", "MISSING_FIELD:craft:Kutch-Ajrakh:POLICY"]
SUBJECT = TaskSubject(
    kind="craft", slug="Kutch-Ajrakh", name="Kutch Ajrakh", page_url=f"{SITE}/crafts/Kutch-Ajrakh"
)
PACKAGE = StewardPackage(
    craft=SUBJECT, adopted_at=UNTIL, seen_at=None, stewards=1, new_tasks=[], tasks=[], total=0
)
TASKS = MyTasks(
    tier="NEW", holding=0, holding_max=5, reservation_minutes=120, claimed=[], completed=[], outcomes=[]
)


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


@pytest.fixture
def mine(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    asked: list[str] = []

    async def my_tasks(session: Any, user: User, *, site: str, now: datetime) -> MyTasks:
        asked.append("tasks")
        return TASKS

    async def my_crafts(session: Any, user: User, *, site: str, now: datetime) -> MyCrafts:
        asked.append("crafts")
        return MyCrafts(crafts=[PACKAGE], adopted=1, adopted_max=10, message="This account stewards 1.")

    monkeypatch.setattr(mcp_work_tools.contribution_queue_tasks, "my_tasks", my_tasks)
    monkeypatch.setattr(mcp_work_tools.stewardship, "my_crafts", my_crafts)
    return asked


async def test_several_tasks_are_claimed_in_one_call(monkeypatch: pytest.MonkeyPatch) -> None:
    asked: list[tuple[uuid.UUID, list[str]]] = []

    async def claim_tasks(
        session: Any, user_id: uuid.UUID, keys: list[str], *, site: str, now: datetime
    ) -> TaskClaims:
        asked.append((user_id, keys))
        held = [TaskHold(task_key=key, held=True, reserved_until=UNTIL) for key in keys]
        return TaskClaims(held=held, refused=[], tier="NEW", holding=2, holding_max=5, message="Reserved 2.")

    monkeypatch.setattr(mcp_work_tools.task_reservations, "claim_tasks", claim_tasks)
    tool_context = context()
    result = await call("reserve_tasks", {"claim": KEYS}, tool_context)
    assert result["isError"] is False
    assert [item["taskKey"] for item in result["structuredContent"]["held"]] == KEYS
    assert (
        result["structuredContent"]["released"] == []
        and result["structuredContent"]["message"] == "Reserved 2."
    )
    assert asked == [(uuid.UUID(int=77), KEYS)]
    assert tool_context.session.commits == 1  # type: ignore[attr-defined]


async def test_reserving_and_my_work_need_a_signed_in_connection_with_the_contribute_scope() -> None:
    anonymous = await call("reserve_tasks", {"claim": KEYS}, context(None))
    assert anonymous["isError"] is True and "signed-in connection" in anonymous["content"][0]["text"]
    unscoped = await call("my_work", {}, context("RESEARCHER", READ_SCOPE))
    assert unscoped["isError"] is True and "contribute scope" in unscoped["content"][0]["text"]


async def test_my_work_holds_the_tasks_and_the_stewarded_crafts_and_keeps_what_was_seen(
    mine: list[str],
) -> None:
    tool_context = context()
    shown = (await call("my_work", {}, tool_context))["structuredContent"]
    assert mine == ["tasks", "crafts"]
    assert (shown["tier"], shown["holdingMax"], shown["craftsMax"]) == ("NEW", 5, 10)
    assert [craft["craft"]["slug"] for craft in shown["crafts"]] == ["Kutch-Ajrakh"]
    assert shown["message"] == "This account stewards 1."
    assert tool_context.session.commits == 1  # type: ignore[attr-defined]


async def test_a_student_s_work_is_its_tasks_alone(mine: list[str]) -> None:
    shown = (await call("my_work", {}, context("STUDENT")))["structuredContent"]
    assert mine == ["tasks"] and shown["crafts"] == []
    assert shown["message"].startswith("Stewardship is for accounts of Researcher or above")


async def test_stewardship_is_for_accounts_that_may_contribute(monkeypatch: pytest.MonkeyPatch) -> None:
    dropped: list[str] = []

    async def drop_craft(session: Any, user: User, slug: str, *, now: datetime) -> Stewardship:
        dropped.append(slug)
        return Stewardship(craft_slug=slug, adopted=False, message="Dropped.")

    async def adopt_craft(session: Any, user: User, slug: str, *, site: str, now: datetime) -> StewardPackage:
        return PACKAGE

    monkeypatch.setattr(mcp_work_tools.stewardship, "drop_craft", drop_craft)
    monkeypatch.setattr(mcp_work_tools.stewardship, "adopt_craft", adopt_craft)
    drop = {"craft_slug": "Kutch-Ajrakh", "action": "drop"}
    student = await call("steward_craft", drop, context("STUDENT"))
    assert student["isError"] is True and "Researcher or above" in student["content"][0]["text"]
    assert dropped == []
    researcher = await call("steward_craft", drop, context())
    assert (researcher["isError"], researcher["structuredContent"]["adopted"]) == (False, False)
    assert dropped == ["Kutch-Ajrakh"] and researcher["structuredContent"]["package"] is None
    adopted = (await call("steward_craft", drop | {"action": "adopt"}, context()))["structuredContent"]
    assert (adopted["adopted"], adopted["craftSlug"], adopted["package"]["total"]) == (
        True,
        "Kutch-Ajrakh",
        0,
    )
    wrong = await call("steward_craft", drop | {"action": "keep"}, context())
    assert wrong["isError"] is True and "action" in wrong["content"][0]["text"]
