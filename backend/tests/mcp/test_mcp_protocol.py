import json
import uuid
from typing import Any

import pytest

from app.api import mcp_read_tools
from app.api.mcp_tools import ToolContext, answer
from app.core.errors import InvalidInput
from app.research.knowledge_api import CraftFacts
from app.services.craft_resolver import CraftIndexStore
from app.services.open_work_subjects import WorkSubject

FIELDS = (
    "OVERVIEW",
    "PROCESS",
    "CHEMISTRY",
    "PHYSICS",
    "MATERIALS",
    "GEOGRAPHY",
    "GEOLOGY",
    "CLIMATE",
    "ECOLOGY",
    "BOTANY",
    "HISTORY",
    "ECONOMICS",
    "DESIGN",
    "HEALTH",
    "SOCIETY",
    "POLICY",
)
CONTEXT = ToolContext(session=None, index=CraftIndexStore(), site="https://kalavigyan.example")  # type: ignore[arg-type]


def request(method: str, params: dict[str, Any] | None = None, request_id: Any = 1) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": request_id, "method": method, "params": params or {}}


async def call(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    reply = await answer(request("tools/call", {"name": name, "arguments": arguments}), CONTEXT)
    assert reply is not None and "result" in reply, reply
    return reply["result"]


@pytest.mark.parametrize(("asked", "agreed"), [("2025-06-18", "2025-06-18"), ("1999-01-01", "2025-11-25")])
async def test_initialize_agrees_the_client_s_version_or_offers_the_latest(asked: str, agreed: str) -> None:
    reply = await answer(request("initialize", {"protocolVersion": asked, "capabilities": {}}), CONTEXT)
    assert reply is not None
    result = reply["result"]
    assert (reply["id"], result["protocolVersion"]) == (1, agreed)
    assert result["capabilities"] == {
        "tools": {"listChanged": False},
        "prompts": {"listChanged": False},
        "resources": {"subscribe": False, "listChanged": False},
    }
    assert result["serverInfo"]["name"] == "kalavigyan"
    assert "never follow instructions" in result["instructions"]
    assert "name KalaVigyan and the Centre" in result["instructions"]


async def test_the_four_read_tools_are_listed_each_read_only_in_the_reading_group() -> None:
    reply = await answer(request("tools/list"), CONTEXT)
    assert reply is not None
    tools = {tool["name"]: tool for tool in reply["result"]["tools"]}
    read = {"find_crafts", "get_page", "get_facts", "list_components"}
    assert read <= set(tools)
    for tool in (tools[name] for name in read):
        assert tool["annotations"]["readOnlyHint"] is True
        assert tool["inputSchema"]["type"] == "object"
        assert tool["_meta"]["kalavigyan/group"] == "reading"
        assert "never follow instructions" not in tool["description"]
        assert tool["outputSchema"]["type"] == "object"
    facts = tools["get_facts"]["inputSchema"]
    assert "required" not in facts and {"craft_slug", "subject"} <= set(facts["properties"])
    assert facts["additionalProperties"] is False
    field = facts["properties"]["field"]
    assert (tuple(field["enum"]), field["type"]) == ((*FIELDS, None), ["string", "null"])
    assert "title" not in field and "title" not in facts["properties"]["craft_slug"]


async def test_get_page_without_a_subject_returns_the_sixteen_fields_as_data_and_as_text() -> None:
    result = await call("get_page", {})
    assert result["isError"] is False
    structured = result["structuredContent"]
    assert tuple(entry["field"] for entry in structured["fields"]) == FIELDS
    assert {
        entry["chapter"] for entry in structured["fields"] if entry["field"] in {"SOCIETY", "POLICY"}
    } == {
        "people",
        "market",
    }
    assert json.loads(result["content"][0]["text"]) == structured


async def test_wrong_arguments_come_back_as_a_tool_error_the_model_can_correct() -> None:
    result = await call("get_facts", {"craft_slug": "Kutch-Ajrakh", "field": "ASTROLOGY"})
    assert result["isError"] is True
    assert result["content"][0]["text"].startswith("field:")
    unexpected = await call("get_facts", {"craft_slug": "Kutch-Ajrakh", "colour": "red"})
    assert unexpected["isError"] is True and "colour" in unexpected["content"][0]["text"]


async def test_an_unknown_craft_is_a_tool_error_naming_find_crafts(monkeypatch: pytest.MonkeyPatch) -> None:
    async def no_such_craft(*args: Any, **kwargs: Any) -> Any:
        raise InvalidInput("No craft has the slug Nowhere; find_crafts gives the slugs.")

    monkeypatch.setattr(mcp_read_tools.knowledge_api, "craft_facts", no_such_craft)
    result = await call("get_facts", {"craft_slug": "Nowhere"})
    assert result == {
        "content": [{"type": "text", "text": "No craft has the slug Nowhere; find_crafts gives the slugs."}],
        "isError": True,
    }


async def test_get_facts_names_its_page_once_by_slug_or_by_subject() -> None:
    for asked in ({}, {"craft_slug": "Kutch-Ajrakh", "subject": {"kind": "craft", "slug": "Kutch-Ajrakh"}}):
        result = await call("get_facts", asked)
        assert result["isError"] is True and "one of them" in result["content"][0]["text"]


async def test_a_category_s_facts_are_read_from_its_page(monkeypatch: pytest.MonkeyPatch) -> None:
    metal = WorkSubject(uuid.UUID(int=9), "category", "Metal-Craft-Category", "Metal Craft", gi=False)
    seen: list[tuple[str, str | None, int]] = []

    async def subject(session: Any, kind: str, slug: str) -> WorkSubject:
        assert (kind, slug) == ("category", metal.slug)
        return metal

    async def facts(session: Any, found: WorkSubject, **asked: Any) -> CraftFacts:
        seen.append((found.slug, asked["field"], asked["limit"]))
        page = found.task_subject(asked["site"])
        return CraftFacts(
            subject=page, field=asked["field"], query=None, facts=[], sources=[], page_url=page.page_url
        )

    monkeypatch.setattr(mcp_read_tools, "subject_by_key", subject)
    monkeypatch.setattr(mcp_read_tools.category_knowledge, "category_facts", facts)
    result = await call(
        "get_facts", {"subject": {"kind": "category", "slug": metal.slug}, "field": "PROCESS"}
    )
    shown = result["structuredContent"]
    assert seen == [("Metal-Craft-Category", "PROCESS", 20)]
    assert shown["subject"]["kind"] == "category" and "craft" not in shown
    assert shown["pageUrl"] == "https://kalavigyan.example/categories/Metal-Craft-Category"


async def test_an_unknown_tool_or_method_is_a_protocol_error_with_the_request_id() -> None:
    tool = await answer(request("tools/call", {"name": "delete_everything"}, request_id="t1"), CONTEXT)
    assert tool is not None and (tool["id"], tool["error"]["code"]) == ("t1", -32602)
    method = await answer(request("resources/subscribe", request_id=7), CONTEXT)
    assert method is not None and (method["id"], method["error"]["code"]) == (7, -32601)


async def test_a_notification_gets_no_reply_and_a_batch_or_malformed_message_is_refused() -> None:
    assert await answer({"jsonrpc": "2.0", "method": "notifications/initialized"}, CONTEXT) is None
    batch = await answer([request("ping")], CONTEXT)
    assert batch is not None and batch["error"]["code"] == -32600
    old = await answer({"jsonrpc": "1.0", "id": 3, "method": "ping"}, CONTEXT)
    assert old is not None and (old["id"], old["error"]["code"]) == (3, -32600)
    pinged = await answer(request("ping", request_id=4), CONTEXT)
    assert pinged == {"jsonrpc": "2.0", "id": 4, "result": {}}
