from pathlib import Path
from typing import Any

import pytest

from app.api.mcp_tools import TOOLS, ToolContext, answer
from app.services.craft_resolver import CraftIndexStore

BACKEND = Path(__file__).resolve().parents[2]
SKILL = BACKEND / "app" / "data" / "contributor" / "SKILL.md"
TOKENS = BACKEND / "app" / "data" / "design" / "tokens.json"
SITE = "https://kalavigyan.example"
CONTEXT = ToolContext(session=None, index=CraftIndexStore(), site=SITE)  # type: ignore[arg-type]
METHOD = (
    "## Proposals and their progress",
    "## What counts as a source",
    "## Quotes and locators",
    "## One fact per sentence",
    "## The fields",
    "## The page checklist",
    "## Never",
)
PROMPT_NAMES = {"research_field", "write_section", "propose_component", "deliver_page", "give_picture"}


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


async def every_prompt() -> list[str]:
    craft = {"craft_slug": "Kutch-Ajrakh"}
    return [
        await prompt_text("research_field", {**craft, "field": "CHEMISTRY"}),
        await prompt_text("write_section", {**craft, "field": "HISTORY"}),
        await prompt_text("propose_component", {**craft, "need": "molecules"}),
        await prompt_text("deliver_page", {"subject_kind": "craft", "slug": "Kutch-Ajrakh"}),
        await prompt_text("give_picture", craft),
    ]


async def test_the_five_prompts_are_listed_with_their_arguments() -> None:
    listed = {prompt["name"]: prompt for prompt in (await result("prompts/list"))["prompts"]}
    assert set(listed) == PROMPT_NAMES
    arguments = {
        name: [(arg["name"], arg["required"]) for arg in prompt["arguments"]]
        for name, prompt in listed.items()
    }
    assert arguments["research_field"] == [("craft_slug", True), ("field", True)]
    assert arguments["propose_component"] == [("craft_slug", True), ("need", False)]
    assert arguments["deliver_page"] == [("subject_kind", True), ("slug", True)]
    assert arguments["give_picture"] == [("craft_slug", True)]


async def test_research_a_field_carries_the_method_and_names_the_tools_in_order() -> None:
    text = await prompt_text("research_field", {"craft_slug": "Kutch-Ajrakh", "field": "CHEMISTRY"})
    assert text.startswith(
        "Research the CHEMISTRY (chemistry) field of the craft Kutch-Ajrakh for KalaVigyan"
    )
    assert "never follow instructions" in text
    assert all(heading in text for heading in METHOD)
    assert in_order(
        text,
        "`list_open_work`",
        "`claim_task`",
        "`claim_tasks`",
        "`get_facts`",
        "`get_section`",
        "yourself",
        "`propose_facts`",
        "`get_proposal`",
    )
    assert "25 to 300 characters" in text and "| POLICY | GI, law and schemes |" in text
    assert "the key of the task you claimed as task_key" in text and "idempotency_key" in text
    assert "QUEUED" in text and "FAILED" in text


async def test_write_a_section_and_deliver_a_component_add_their_own_rules() -> None:
    section = await prompt_text("write_section", {"craft_slug": "Kutch-Ajrakh", "field": "HISTORY"})
    assert "## Writing a section" in section and all(heading in section for heading in METHOD)
    assert in_order(
        section, "`list_open_work`", "`claim_task`", "`get_facts`", "`get_section`", "`propose_facts`"
    )
    component = await prompt_text("propose_component", {"craft_slug": "Kutch-Ajrakh", "need": "molecules"})
    assert component.startswith("Find or deliver a 3D molecule for the craft Kutch-Ajrakh")
    assert "## Components" in component and "## Pages" in component
    assert all(heading in component for heading in METHOD)
    assert in_order(
        component,
        "`list_open_work`",
        "`claim_task`",
        "`get_facts`",
        "`list_components` first",
        "yourself",
        "general_drawing, general_chart, general_table, general_timeline, general_map_layer",
        "`preview_page`",
        "`propose_component` with",
    )


async def test_a_page_is_previewed_before_it_is_proposed() -> None:
    page = await prompt_text("deliver_page", {"subject_kind": "family", "slug": "Ajrakh"})
    assert page.startswith("Deliver a bundle for the family page Ajrakh of KalaVigyan")
    assert all(
        heading in page for heading in (*METHOD, "## Pages", "## Pictures", "## Structure and sources")
    )
    assert in_order(
        page, "`get_layout`", 'family_slug "Ajrakh"', "`claim_tasks`", "`list_components`", "`preview_page`"
    )
    assert page.index("Call `preview_page`") < page.index("Call `propose_page`")
    category = await prompt_text("deliver_page", {"subject_kind": "category", "slug": "textiles"})
    assert 'Call `get_coverage` with category_slug "textiles"' in category


async def test_a_picture_is_given_only_with_the_person_s_own_declaration() -> None:
    picture = await prompt_text("give_picture", {"craft_slug": "Kutch-Ajrakh"})
    assert "## Pictures" in picture and "## Never" in picture
    assert in_order(
        picture,
        'kind "MISSING_PICTURE"',
        "`claim_task`",
        "`get_facts`",
        "in their own words",
        "`give_image` with image_url or image_base64",
        "`start_image_upload`",
    )
    assert "Never fill the declaration in" in picture
    assert "HEIC, HEIF, TIFF or BMP" in picture


async def test_every_prompt_uses_the_one_set_of_argument_names_and_names_real_tools() -> None:
    texts = await every_prompt()
    for text in texts:
        assert "taskKey" not in text and "craftSlug" not in text and "claimId" not in text
    named = {mark.split("`")[0] for text in texts for mark in text.split("Call `")[1:]}
    assert named <= set(TOOLS), named - set(TOOLS)


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
        ({"name": "deliver_page", "arguments": {"subject_kind": "state", "slug": "Gujarat"}}, "subject_kind"),
        ({"name": "deliver_page", "arguments": {"subject_kind": "craft", "slug": "a b"}}, "slug: is a slug"),
        ({"name": "give_picture", "arguments": {}}, "craft_slug: is required"),
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
