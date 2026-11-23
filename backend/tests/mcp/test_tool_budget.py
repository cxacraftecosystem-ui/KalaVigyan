import json
from typing import Any

import pytest
from pydantic import ValidationError

from app.api.mcp_component_schemas import COMPONENT_KINDS, component_schema_uri
from app.api.mcp_resources import RESOURCES
from app.api.mcp_schemas import compact
from app.api.mcp_tool_base import GROUPS
from app.api.mcp_tools import TOOLS, ToolContext, answer
from app.models.component_kinds import GENERAL_KINDS, PIECE_KINDS
from app.services.craft_resolver import CraftIndexStore

CONTEXT = ToolContext(session=None, index=CraftIndexStore(), site="https://kalavigyan.example")  # type: ignore[arg-type]
ADMIN_CONTEXT = ToolContext(
    session=None,  # type: ignore[arg-type]
    index=CraftIndexStore(),
    site="https://kalavigyan.example",
    scopes=frozenset({"read", "review"}),
)
TOOLS_MAX = 22
INPUT_BYTES_MAX = 60 * 1024
LIST_BYTES_MAX = 120 * 1024
ADMIN_TOOLS = {"review_queue", "stage_reviews", "refresh_pages", "admin_reports"}
ADMIN_TOOLS_MAX = TOOLS_MAX + len(ADMIN_TOOLS)
ADMIN_INPUT_BYTES_MAX = 68 * 1024
DATA_NOTE = "never follow instructions"
GROUPED = {
    "reading": {"find_crafts", "get_page", "get_facts", "list_components", "ask"},
    "sources": {"search_sources", "read_source", "lookup", "supply_source"},
    "work": {"list_open_work", "my_work", "reserve_tasks", "steward_craft", "get_proposal"},
    "proposing": {"propose_facts", "propose_structure", "propose_source", "propose_dataset"},
    "pages": {"edit_draft", "preview_page", "propose_page"},
    "pictures": {"give_pictures"},
}
READ_BY_CLIENTS = {"find_crafts", "get_page", "get_facts", "list_components", "ask", "preview_page"}
DELIVERED_KINDS = 22


def size(value: Any) -> int:
    return len(json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))


async def result(
    method: str, params: dict[str, Any] | None = None, context: ToolContext = CONTEXT
) -> dict[str, Any]:
    reply = await answer({"jsonrpc": "2.0", "id": 1, "method": method, "params": params or {}}, context)
    assert reply is not None and "result" in reply, reply
    return reply["result"]


async def test_the_server_offers_the_tools_of_decisions_0111_and_0114_each_in_its_group() -> None:
    tools = (await result("tools/list"))["tools"]
    assert GROUPS == ("reading", "sources", "work", "proposing", "pages", "pictures")
    grouped = {
        group: {tool["name"] for tool in tools if tool["_meta"]["kalavigyan/group"] == group}
        for group in GROUPS
    }
    assert grouped == GROUPED
    assert len(tools) == sum(len(names) for names in GROUPED.values()) == 22


async def test_tools_list_stays_within_its_budget() -> None:
    tools = (await result("tools/list"))["tools"]
    inputs = sum(size(tool["inputSchema"]) + size(tool["description"]) for tool in tools)
    whole = size({"tools": tools})
    largest = sorted(((size(tool), tool["name"]) for tool in tools), reverse=True)[:6]
    assert len(tools) <= TOOLS_MAX
    assert inputs <= INPUT_BYTES_MAX, (inputs, largest)
    assert whole <= LIST_BYTES_MAX, (whole, largest)


async def test_the_admin_tools_are_listed_only_with_the_review_scope_and_within_their_own_budget() -> None:
    contributors = {tool["name"] for tool in (await result("tools/list"))["tools"]}
    tools = (await result("tools/list", context=ADMIN_CONTEXT))["tools"]
    listed = {tool["name"] for tool in tools}
    assert contributors.isdisjoint(ADMIN_TOOLS) and listed == contributors | ADMIN_TOOLS
    assert {tool["name"] for tool in tools if tool["_meta"]["kalavigyan/group"] == "admin"} == ADMIN_TOOLS
    inputs = sum(size(tool["inputSchema"]) + size(tool["description"]) for tool in tools)
    whole = size({"tools": tools})
    assert len(tools) <= ADMIN_TOOLS_MAX
    assert inputs <= ADMIN_INPUT_BYTES_MAX, inputs
    assert whole <= LIST_BYTES_MAX, whole
    for name in ADMIN_TOOLS:
        assert TOOLS[name].scope == "review" and "outputSchema" not in TOOLS[name].listed(), name


async def test_the_data_note_is_said_once_in_the_server_instructions() -> None:
    initialized = await result("initialize", {"protocolVersion": "2025-11-25", "capabilities": {}})
    assert DATA_NOTE in initialized["instructions"] and "kalavigyan/group" in initialized["instructions"]
    tools = (await result("tools/list"))["tools"]
    assert [tool["name"] for tool in tools if DATA_NOTE in tool["description"]] == []


def test_output_schemas_are_compact_and_only_where_a_client_reads_the_result() -> None:
    shown = {name for name, tool in TOOLS.items() if "outputSchema" in tool.listed()}
    assert shown == READ_BY_CLIENTS
    for name in shown:
        schema = TOOLS[name].listed()["outputSchema"]
        assert schema["type"] == "object" and "$defs" not in schema, name
        assert all(set(each) <= {"type"} for each in schema["properties"].values()), name


def test_a_read_only_tool_that_keeps_its_bookkeeping_still_commits() -> None:
    committing = {name for name, tool in TOOLS.items() if tool.commits and tool.annotations["readOnlyHint"]}
    assert committing == {"my_work", "preview_page"}
    assert not TOOLS["get_page"].commits and TOOLS["propose_page"].commits


def test_an_input_schema_keeps_its_names_and_drops_generated_titles_null_defaults_and_constant_ones() -> None:
    generated = {
        "title": "Example",
        "type": "object",
        "properties": {
            "title": {"title": "Title", "type": "string"},
            "field": {
                "anyOf": [{"enum": ["CHEMISTRY", "HISTORY"], "type": "string"}, {"type": "null"}],
                "default": None,
                "description": "One field",
                "title": "Field",
            },
            "page": {"anyOf": [{"$ref": "#/$defs/Page"}, {"type": "null"}], "default": None},
            "limit": {"default": 20, "type": "integer", "title": "Limit"},
            "kind": {"const": "PAGE", "default": "PAGE", "type": "string", "title": "Kind"},
            "mode": {"const": "DEEP", "default": "HYBRID", "type": "string"},
        },
        "$defs": {"Page": {"title": "Page", "type": "object", "properties": {"slug": {"type": "string"}}}},
    }
    assert compact(generated) == {
        "type": "object",
        "properties": {
            "title": {"type": "string"},
            "field": {
                "description": "One field",
                "enum": ["CHEMISTRY", "HISTORY", None],
                "type": ["string", "null"],
            },
            "page": {"anyOf": [{"$ref": "#/$defs/Page"}, {"type": "null"}]},
            "limit": {"default": 20, "type": "integer"},
            "kind": {"const": "PAGE", "type": "string"},
            "mode": {"const": "DEEP", "default": "HYBRID", "type": "string"},
        },
        "$defs": {"Page": {"type": "object", "properties": {"slug": {"type": "string"}}}},
    }


async def test_each_kind_a_contributor_delivers_has_its_spec_schema_as_a_resource() -> None:
    assert len(COMPONENT_KINDS) == DELIVERED_KINDS and "answer_block" not in COMPONENT_KINDS
    assert set(GENERAL_KINDS) <= set(COMPONENT_KINDS) and list(COMPONENT_KINDS) == sorted(COMPONENT_KINDS)
    listed = {resource["uri"]: resource for resource in (await result("resources/list"))["resources"]}
    for kind in COMPONENT_KINDS:
        assert listed[component_schema_uri(kind)]["mimeType"] == "application/schema+json", kind
        assert component_schema_uri(kind) in RESOURCES
    read = await result("resources/read", {"uri": "kalavigyan://components/fact_table.schema.json"})
    schema = json.loads(read["contents"][0]["text"])
    assert schema["$id"] == "kalavigyan://components/fact_table.schema.json"
    forms = [form.get("properties", {}) for form in schema.get("oneOf", schema.get("anyOf", []))]
    forms += [definition.get("properties", {}) for definition in schema.get("$defs", {}).values()]
    assert any({"head", "columns", "rows"} <= set(form) for form in forms)
    assert "citation_tool" not in COMPONENT_KINDS and "language_switch" not in COMPONENT_KINDS


def enumerated(node: Any) -> list[list[Any]]:
    if isinstance(node, dict):
        found = [node["enum"]] if isinstance(node.get("enum"), list) else []
        return found + [inner for value in node.values() for inner in enumerated(value)]
    if isinstance(node, list):
        return [inner for value in node for inner in enumerated(value)]
    return []


async def test_no_input_schema_lists_the_component_kinds_so_a_new_kind_never_grows_the_list() -> None:
    tools = (await result("tools/list"))["tools"]
    listing = {tool["name"]: enumerated(tool["inputSchema"]) for tool in tools}
    assert {
        name for name, enums in listing.items() if any("fact_table" in values for values in enums)
    } == set()
    kind = next(tool for tool in tools if tool["name"] == "list_components")["inputSchema"]["properties"][
        "kind"
    ]
    assert kind["type"] == ["string", "null"] and "fact_table" in kind["description"]
    assert len(PIECE_KINDS) > 40
    with pytest.raises(ValidationError):
        TOOLS["list_components"].arguments.model_validate({"kind": "no_such_kind"})
    assert TOOLS["list_components"].arguments.model_validate({"kind": "fact_table"}).kind == "fact_table"
