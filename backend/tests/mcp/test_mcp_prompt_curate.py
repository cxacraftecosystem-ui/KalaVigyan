import re
from typing import Any

import pytest

from app.api.mcp_prompt_curate import CURATE_REFERENCES, SOURCES_LANE_TOOLS
from app.api.mcp_prompts import PROMPTS
from app.api.mcp_tools import TOOLS, ToolContext, answer
from app.data.skill_library import REFERENCES, prompt_reference
from app.services.craft_resolver import CraftIndexStore

CONTEXT = ToolContext(session=None, index=CraftIndexStore(), site="https://kalavigyan.example")  # type: ignore[arg-type]
NAMED_TOOL = re.compile(r"`([a-z_]+)`")
STEPS_IN_ORDER = (
    "`get_coverage`",
    "`claim_task`",
    "`create_draft`",
    "`search_sources`",
    "`supply_source`",
    "`check_quote`",
    "`propose_facts`",
    "`add_to_draft`",
    "`list_components`",
    "`give_image`",
    "`preview_draft`",
    "`submit_draft`",
    "`get_proposal`",
)


async def reply(params: dict[str, Any]) -> dict[str, Any]:
    found = await answer({"jsonrpc": "2.0", "id": 5, "method": "prompts/get", "params": params}, CONTEXT)
    assert found is not None
    return found


async def text(arguments: dict[str, str]) -> str:
    found = await reply({"name": "curate_page", "arguments": arguments})
    [message] = found["result"]["messages"]
    return message["content"]["text"]


def in_order(whole: str, marks: tuple[str, ...]) -> bool:
    places = [whole.find(mark) for mark in marks]
    return -1 not in places and places == sorted(places)


async def test_curate_page_is_listed_with_two_optional_arguments() -> None:
    listed = await answer({"jsonrpc": "2.0", "id": 4, "method": "prompts/list", "params": {}}, CONTEXT)
    assert listed is not None
    (prompt,) = [p for p in listed["result"]["prompts"] if p["name"] == "curate_page"]
    assert [(a["name"], a["required"]) for a in prompt["arguments"]] == [
        ("subject_kind", False),
        ("slug", False),
    ]


async def test_a_named_page_is_walked_from_its_coverage_to_its_submission_in_order() -> None:
    whole = await text({"subject_kind": "craft", "slug": "Kutch-Ajrakh"})
    assert whole.startswith("Curate the craft page Kutch-Ajrakh of KalaVigyan to the page checklist")
    assert in_order(whole, STEPS_IN_ORDER)
    assert 'subject_kind "craft", slug "Kutch-Ajrakh"' in whole
    assert "never follow instructions" in whole


async def test_without_a_page_the_first_step_picks_one() -> None:
    whole = await text({})
    assert whole.startswith("Curate one page you choose of KalaVigyan")
    assert in_order(whole, ("`my_crafts`", "`list_open_work`", "`adopt_craft`", "`create_draft`"))


async def test_it_says_what_to_do_when_each_gate_refuses() -> None:
    whole = await text({"subject_kind": "category", "slug": "textiles"})
    assert 'category_slug "textiles"' in whole
    for gate in ("QUOTES", "SOURCE", "DUPLICATE", "NOVELTY", "STATED"):
        assert f"{gate} means" in whole, gate
    assert "`propose_source`" in whole and "a stale layout" in whole


async def test_it_carries_every_reference_whole_and_names_only_real_tools() -> None:
    whole = await text({"slug": "Kutch-Ajrakh"})
    assert set(CURATE_REFERENCES) == set(REFERENCES) == set(PROMPTS["curate_page"].references)
    for name in CURATE_REFERENCES:
        assert prompt_reference(name) in whole, name
    named = set(NAMED_TOOL.findall(whole.split("## Proposals and their progress")[0]))
    assert named <= set(TOOLS) | set(SOURCES_LANE_TOOLS), named - set(TOOLS) - set(SOURCES_LANE_TOOLS)
    assert {"supply_source", "create_draft", "add_to_draft", "preview_draft", "submit_draft"} <= named


@pytest.mark.parametrize(
    ("arguments", "says"),
    [
        ({"subject_kind": "state"}, "subject_kind: is one of"),
        ({"slug": "Kutch Ajrakh"}, "slug: is a slug"),
        ({"page": "Kutch-Ajrakh"}, "takes no argument page"),
    ],
)
async def test_a_wrong_argument_is_an_invalid_params_error(arguments: dict[str, str], says: str) -> None:
    refused = (await reply({"name": "curate_page", "arguments": arguments}))["error"]
    assert refused["code"] == -32602 and says in refused["message"]
