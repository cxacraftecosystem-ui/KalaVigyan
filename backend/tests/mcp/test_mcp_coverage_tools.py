from typing import Any

import pytest

from app.api import mcp_read_tools
from app.api.mcp_tools import ToolContext, answer
from app.research.coverage import CoverageSubject, Holdings, field_coverage
from app.research.knowledge_api import CraftSection, FieldList, SubjectCoverage
from app.services.craft_resolver import CraftIndexStore
from app.services.knowledge_api import field_list

SITE = "https://kalavigyan.example"
CONTEXT = ToolContext(session=None, index=CraftIndexStore(), site=SITE)  # type: ignore[arg-type]
COVERAGE = field_coverage(
    CoverageSubject("craft", "Kutch-Ajrakh", "Kutch Ajrakh"),
    Holdings(
        filed={
            "c1": frozenset({"CHEMISTRY"}),
            "c2": frozenset({"CHEMISTRY"}),
            "c3": frozenset({"CHEMISTRY"}),
        },
        sources={"c1": frozenset({"s1"}), "c2": frozenset({"s1"}), "c3": frozenset({"s2"})},
    ),
    claims_min=3,
)


async def call(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    request = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {"name": name, "arguments": arguments},
    }
    reply = await answer(request, CONTEXT)
    assert reply is not None and "result" in reply, reply
    return reply["result"]


async def test_get_coverage_is_a_read_tool_for_one_craft_or_one_category() -> None:
    reply = await answer({"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}}, CONTEXT)
    assert reply is not None
    tools = {tool["name"]: tool for tool in reply["result"]["tools"]}
    listed = tools["get_coverage"]
    assert listed["annotations"]["readOnlyHint"] is True
    assert set(listed["inputSchema"]["properties"]) == {"craft_slug", "category_slug"}
    assert {"coverage", "openWork", "pageUrl", "attribution"} <= set(listed["outputSchema"]["properties"])
    assert "craft_slug" in tools["list_fields"]["inputSchema"]["properties"]
    assert tools["get_section"]["inputSchema"]["required"] == ["craft_slug"]


@pytest.mark.parametrize("arguments", [{}, {"craft_slug": "Kutch-Ajrakh", "category_slug": "Textiles"}])
async def test_get_coverage_names_exactly_one_subject(arguments: dict[str, Any]) -> None:
    result = await call("get_coverage", arguments)
    assert result["isError"] is True
    assert "name a craft_slug or a category_slug" in result["content"][0]["text"]


async def test_get_coverage_returns_the_counts_per_field_and_the_open_field_work(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    asked: list[tuple[str, str]] = []

    async def read(session: Any, kind: str, slug: str, *, site: str) -> SubjectCoverage:
        asked.append((kind, slug))
        return SubjectCoverage(coverage=COVERAGE, open_work=[], page_url=f"{site}/crafts/{slug}")

    monkeypatch.setattr(mcp_read_tools.coverage_reads, "read_subject_coverage", read)
    result = await call("get_coverage", {"craft_slug": "Kutch-Ajrakh"})
    shown = result["structuredContent"]
    assert asked == [("craft", "Kutch-Ajrakh")]
    assert shown["coverage"]["covered"] == ["CHEMISTRY"]
    assert len(shown["coverage"]["missing"]) == 15
    chemistry = next(count for count in shown["coverage"]["fields"] if count["field"] == "CHEMISTRY")
    assert (chemistry["claims"], chemistry["sources"], chemistry["standing"]) == (3, 2, "COVERED")
    await call("get_coverage", {"category_slug": "Textiles"})
    assert asked[-1] == ("category", "Textiles")


async def test_list_fields_for_a_craft_carries_what_it_holds_in_each_field(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def held_field_list(session: Any, slug: str) -> FieldList:
        return field_list(COVERAGE)

    monkeypatch.setattr(mcp_read_tools.knowledge_api, "held_field_list", held_field_list)
    shown = (await call("list_fields", {"craft_slug": "Kutch-Ajrakh"}))["structuredContent"]
    assert shown["craftSlug"] == "Kutch-Ajrakh"
    chemistry = next(entry for entry in shown["fields"] if entry["field"] == "CHEMISTRY")
    assert (chemistry["chapter"], chemistry["held"]["claims"]) == ("chem", 3)
    plain = (await call("list_fields", {}))["structuredContent"]
    assert "craftSlug" not in plain and all("held" not in entry for entry in plain["fields"])
    assert {entry["field"]: entry["chapter"] for entry in plain["fields"]}["MATERIALS"] == "made"


async def test_get_section_without_a_field_reads_every_section(monkeypatch: pytest.MonkeyPatch) -> None:
    asked: list[str] = []

    async def craft_sections(session: Any, slug: str, *, site: str) -> CraftSection:
        asked.append(slug)
        return CraftSection.model_validate(
            {
                "craft": {"slug": slug, "name": "Kutch Ajrakh", "path": f"/crafts/{slug}"},
                "field": None,
                "section": None,
                "pageUrl": f"{site}/crafts/{slug}",
            }
        )

    monkeypatch.setattr(mcp_read_tools.knowledge_api, "craft_sections", craft_sections)
    shown = (await call("get_section", {"craft_slug": "Kutch-Ajrakh"}))["structuredContent"]
    assert asked == ["Kutch-Ajrakh"]
    assert (shown["field"], shown["sections"], shown["byField"], shown["openWork"]) == (None, [], [], [])
