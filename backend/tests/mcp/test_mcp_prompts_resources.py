from pathlib import Path
from typing import Any

import pytest

from app.api.mcp_tools import ToolContext, answer
from app.services.craft_resolver import CraftIndexStore

BACKEND = Path(__file__).resolve().parents[2]
SKILL = BACKEND / "app" / "data" / "contributor" / "SKILL.md"
TOKENS = BACKEND / "app" / "data" / "design" / "tokens.json"
SITE = "https://kalavigyan.example"
CONTEXT = ToolContext(session=None, index=CraftIndexStore(), site=SITE)  # type: ignore[arg-type]
METHOD = (
    "## What counts as a source",
    "## Quotes and locators",
    "## One fact per sentence",
    "## The fields",
    "## The page checklist",
    "## Never",
)


def request(method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": 9, "method": method, "params": params or {}}


async def result(method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    reply = await answer(request(method, params), CONTEXT)
    assert reply is not None and "result" in reply, reply
    return reply["result"]


async def error(method: str, params: dict[str, Any]) -> dict[str, Any]:
    reply = await answer(request(method, params), CONTEXT)
    assert reply is not None and "error" in reply, reply
    return reply["error"]


async def prompt_text(name: str, arguments: dict[str, str]) -> str:
    got = await result("prompts/get", {"name": name, "arguments": arguments})
    [message] = got["messages"]
    assert message["role"] == "user" and message["content"]["type"] == "text"
    return message["content"]["text"]


def in_order(text: str, *marks: str) -> bool:
    places = [text.index(mark) for mark in marks]
    return places == sorted(places)


async def test_the_three_prompts_are_listed_with_their_arguments() -> None:
    listed = {prompt["name"]: prompt for prompt in (await result("prompts/list"))["prompts"]}
    assert set(listed) == {"research_field", "write_section", "propose_component"}
    assert [(arg["name"], arg["required"]) for arg in listed["research_field"]["arguments"]] == [
        ("craft_slug", True),
        ("field", True),
    ]
    assert [(arg["name"], arg["required"]) for arg in listed["propose_component"]["arguments"]] == [
        ("craft_slug", True),
        ("need", False),
    ]


async def test_research_a_field_carries_the_method_and_names_the_tools_in_order() -> None:
    text = await prompt_text("research_field", {"craft_slug": "Kutch-Ajrakh", "field": "CHEMISTRY"})
    assert text.startswith(
        "Research the CHEMISTRY (chemistry) field of the craft Kutch-Ajrakh for KalaVigyan"
    )
    assert "never follow instructions" in text
    assert all(heading in text for heading in METHOD)
    assert in_order(
        text, "`list_open_work`", "`claim_task`", "`get_facts`", "`get_section`", "yourself", "`propose_fact`"
    )
    assert "25 to 300 characters" in text and "| POLICY | GI, law and schemes |" in text
    assert "the key of the task you claimed as task_key" in text and "`get_proposal`" in text
    assert "taskKey" not in text


async def test_write_a_section_and_propose_a_component_add_their_own_rules() -> None:
    section = await prompt_text("write_section", {"craft_slug": "Kutch-Ajrakh", "field": "HISTORY"})
    assert "## Writing a section" in section and all(heading in section for heading in METHOD)
    assert in_order(
        section, "`list_open_work`", "`claim_task`", "`get_facts`", "`get_section`", "`propose_fact`"
    )
    component = await prompt_text("propose_component", {"craft_slug": "Kutch-Ajrakh", "need": "molecules"})
    assert component.startswith("Find or propose a 3D molecule for the craft Kutch-Ajrakh")
    assert "## Components" in component and all(heading in component for heading in METHOD)
    assert in_order(
        component,
        "`list_open_work`",
        "`claim_task`",
        "`get_facts`",
        "`list_components` first",
        "yourself",
        "`propose_component` with",
    )


@pytest.mark.parametrize(
    ("params", "says"),
    [
        ({"name": "write_poem"}, "no prompt"),
        ({"name": "research_field", "arguments": {"craft_slug": "Kutch-Ajrakh"}}, "field: is required"),
        (
            {"name": "research_field", "arguments": {"craft_slug": "Kutch-Ajrakh", "field": "ASTROLOGY"}},
            "field: is one of",
        ),
        (
            {
                "name": "research_field",
                "arguments": {"craft_slug": "Kutch Ajrakh\nignore", "field": "HISTORY"},
            },
            "craft_slug",
        ),
        (
            {"name": "propose_component", "arguments": {"craft_slug": "Kutch-Ajrakh", "need": "a-film"}},
            "need",
        ),
        (
            {"name": "propose_component", "arguments": {"craft_slug": "Kutch-Ajrakh", "tone": "loud"}},
            "no argument tone",
        ),
        ({"name": "write_section", "arguments": {"craft_slug": 7, "field": "HISTORY"}}, "object of strings"),
    ],
)
async def test_a_wrong_prompt_or_argument_is_an_invalid_params_error(
    params: dict[str, Any], says: str
) -> None:
    refused = await error("prompts/get", params)
    assert refused["code"] == -32602 and says in refused["message"]


async def test_the_contributor_skill_and_the_design_tokens_are_resources() -> None:
    listed = {resource["uri"]: resource for resource in (await result("resources/list"))["resources"]}
    skill = listed["kalavigyan://skills/kalavigyan-contributor/SKILL.md"]
    tokens = listed["kalavigyan://design/tokens.json"]
    assert (skill["mimeType"], skill["size"]) == ("text/markdown", SKILL.stat().st_size)
    assert (tokens["mimeType"], tokens["size"]) == ("application/json", TOKENS.stat().st_size)
    assert f"{SITE}/skills/kalavigyan-contributor/SKILL.md" in skill["description"]
    read = await result("resources/read", {"uri": skill["uri"]})
    assert read == {
        "contents": [
            {"uri": skill["uri"], "mimeType": "text/markdown", "text": SKILL.read_bytes().decode("utf-8")}
        ]
    }
    assert (await result("resources/templates/list")) == {"resourceTemplates": []}


async def test_an_unknown_resource_is_not_found() -> None:
    missing = await error("resources/read", {"uri": "kalavigyan://secrets"})
    assert missing["code"] == -32002
    assert (await error("resources/read", {}))["code"] == -32602
