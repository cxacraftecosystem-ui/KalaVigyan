from typing import Any

import pytest

from app.api.mcp_guides import GUIDE_PREFIX, GUIDES, bar_text, contents_text, guide_sheets
from app.api.mcp_resources import RESOURCES
from app.api.mcp_tools import ToolContext, answer
from app.data.guide_pages import PAGE_BYTES, PagedText, guide_title, paged
from app.data.skill_library import INDEX_URI
from app.research.bar_references import KIT_GUIDES
from app.services.bar_references import worked_topics
from app.services.craft_resolver import CraftIndexStore

CONTEXT = ToolContext(session=None, index=CraftIndexStore(), site="https://kalavigyan.example")  # type: ignore[arg-type]
SERVED = {
    "kalavigyan-contributor",
    "kalavigyan-datasets",
    "kalavigyan-interactives",
    "flagships",
    "storyboard",
    "kalavigyan-design",
    "system",
    "playbook",
    "cookbook",
    "page-checklist",
    "sources",
    "quotes",
    "fields",
    "components",
    "datasets",
    "knowledge-writes",
    "open-work",
    "component-specs-general",
    "image-contributions",
    "mcp-ask-and-upload",
    "answer-kit",
    "drawing",
    "bar",
    "contents",
    "map-layers",
    *KIT_GUIDES,
    *worked_topics(),
}
SMALL = "# T\n\nIntro.\n\n## A\n\naaaa\n\n## B\n\nbbbbbbbb\n\nbbbbbbbb\n\n## C\n\nc\n"
CHECKLIST_BYTES_FLOOR = 12001


async def reply(method: str, params: dict[str, Any]) -> dict[str, Any]:
    found = await answer({"jsonrpc": "2.0", "id": 3, "method": method, "params": params}, CONTEXT)
    assert found is not None
    return found


async def get_page(arguments: dict[str, Any]) -> dict[str, Any]:
    found = await reply("tools/call", {"name": "get_page", "arguments": arguments})
    return found["result"]


def test_a_guide_is_cut_at_its_sections_and_an_oversized_section_at_its_paragraphs() -> None:
    assert paged(SMALL, size=25) == (
        PagedText(body="# T\n\nIntro.\n\n## A\n\naaaa\n\n", sections=("T", "A")),
        PagedText(body="## B\n\nbbbbbbbb\n\n", sections=("B",)),
        PagedText(body="bbbbbbbb\n\n## C\n\nc\n", sections=("B (continued)", "C")),
    )


def test_a_line_longer_than_a_page_is_cut_between_characters_never_inside_one() -> None:
    assert [page.body for page in paged("abcdefghij", size=4)] == ["abcd", "efgh", "ij"]
    assert [page.body for page in paged("ééé", size=5)] == ["éé", "é"]
    assert all(page.sections == () for page in paged("abcdefghij", size=4))
    with pytest.raises(ValueError, match="at least 4 bytes"):
        paged(SMALL, size=3)


def test_a_heading_inside_a_fence_starts_no_section_and_the_title_follows_frontmatter() -> None:
    fenced = "# T\n\n```\n## not a section\n```\n\n## Real\n\nx\n"
    assert paged(fenced) == (PagedText(body=fenced, sections=("T", "Real")),)
    assert guide_title("---\nname: a-skill\n---\n\n# The skill\n\n## A\n") == "The skill"
    assert guide_title("## A\n\n# Late\n") == ""


def test_every_markdown_resource_but_the_index_is_a_guide_beside_the_bar_and_the_contents() -> None:
    assert set(GUIDES) >= SERVED
    markdown = {uri for uri, resource in RESOURCES.items() if resource.mime_type == "text/markdown"}
    made = {
        f"{GUIDE_PREFIX}{topic}/1"
        for topic in ("bar", "contents", "map-layers", *KIT_GUIDES, *worked_topics())
    }
    assert {guide.whole for guide in GUIDES.values()} == (markdown - {INDEX_URI}) | made


@pytest.mark.parametrize("topic", sorted(SERVED))
def test_every_guide_is_paged_within_the_size_and_read_back_whole(topic: str) -> None:
    sheets = guide_sheets(topic)
    count = len(sheets)
    assert "".join(sheet.text for sheet in sheets) == GUIDES[topic].text()
    assert [sheet.page for sheet in sheets] == list(range(1, count + 1))
    assert [sheet.address for sheet in sheets] == [f"{topic}/{number}" for number in range(1, count + 1)]
    assert [sheet.next for sheet in sheets] == [*(f"{topic}/{n}" for n in range(2, count + 1)), None]
    assert {sheet.pages for sheet in sheets} == {count}
    assert all(len(sheet.text.encode("utf-8")) <= PAGE_BYTES for sheet in sheets)
    assert sheets[0].sections[0] == sheets[0].title and all(sheet.sections for sheet in sheets)


async def test_a_page_read_as_a_resource_names_where_it_sits_then_holds_its_text() -> None:
    sheets = guide_sheets("page-checklist")
    assert len("".join(sheet.text for sheet in sheets).encode("utf-8")) >= CHECKLIST_BYTES_FLOOR
    assert len(sheets) >= 3
    uri = f"{GUIDE_PREFIX}page-checklist/1"
    (content,) = (await reply("resources/read", {"uri": uri}))["result"]["contents"]
    header, body = content["text"].split("\n\n", 1)
    assert (content["uri"], content["mimeType"], body) == (uri, "text/markdown", sheets[0].text)
    assert header.startswith(f"> The page checklist, page 1 of {len(sheets)} (page-checklist/1): ")
    assert "The page checklist; First, derive the page's own lists; The first minute" in header
    assert header.endswith("Next: page-checklist/2. Whole: kalavigyan://skills/references/page-checklist.md.")
    assert "Its last page." in sheets[-1].where()


async def test_the_guide_template_is_listed_and_a_page_that_is_not_there_is_not_found() -> None:
    templates = (await reply("resources/templates/list", {}))["result"]["resourceTemplates"]
    assert [(each["uriTemplate"], each["mimeType"]) for each in templates] == [
        ("kalavigyan://components/{kind}.schema.json", "application/schema+json"),
        ("kalavigyan://guides/{topic}/{page}", "text/markdown"),
    ]
    for uri, says in (
        (f"{GUIDE_PREFIX}page-checklist/999", "has pages 1 to"),
        (f"{GUIDE_PREFIX}nothing/1", "No guide is named nothing"),
        (f"{GUIDE_PREFIX}Page-Checklist/one", "kalavigyan://guides/contents/1"),
    ):
        refused = (await reply("resources/read", {"uri": uri}))["error"]
        assert refused["code"] == -32002 and says in refused["message"], uri


async def test_get_page_reads_any_page_by_its_address_and_nothing_else() -> None:
    read = await get_page({"guide": "page-checklist/2"})
    shown = read["structuredContent"]
    (sheet,) = shown["guide"]["pages"]
    assert (sheet["address"], sheet["page"], shown["guide"]["next"]) == (
        "page-checklist/2",
        2,
        "page-checklist/3",
    )
    assert sheet["text"] == guide_sheets("page-checklist")[1].text and "fields" not in shown
    missing = await get_page({"guide": "page-checklist/99"})
    assert missing["isError"] is True and "has pages 1 to" in missing["content"][0]["text"]
    malformed = await get_page({"guide": "the checklist"})
    assert malformed["isError"] is True and "guide" in malformed["content"][0]["text"]


def test_the_contents_lists_every_page_of_every_other_guide_once() -> None:
    listed = contents_text()
    for topic in GUIDES:
        if topic == "contents":
            continue
        for sheet in guide_sheets(topic):
            assert listed.count(f"- `{sheet.address}`: ") == 1, sheet.address
    assert "`contents/1`" not in listed and listed.startswith("# Every page of the guide\n\n")


def test_the_bar_page_counts_kutch_ajrakh_chapter_by_chapter() -> None:
    text = bar_text()
    assert text.startswith("# The bar: Kutch Ajrakh\n\n")
    assert "It holds 9 pictures and 71 figures, 14 of them interactives and 8 maps" in text
    assert "`/crafts/Kutch-Ajrakh`" in text and "subject {kind craft, slug Kutch-Ajrakh}" in text
    for row in (
        "| opening | 1 | 1 | 1 | 0 |",
        "| chem | 2 | 14 | 7 | 0 |",
        "| why | 2 | 14 | 0 | 7 |",
        "| whatif | 0 | 6 | 4 | 0 |",
        "| media | 0 | 10 | 0 | 0 |",
        "| All | 9 | 71 | 14 | 8 |",
    ):
        assert row in text, row
    assert "a mirror and never a target" in text and "playbook/1" in text and len(guide_sheets("bar")) == 1
    for topic in worked_topics():
        assert f"`{topic}/1`" in text, topic
    assert worked_topics()[:4] == ("ajrakh-answer", "ajrakh-cloth", "ajrakh-made", "ajrakh-chemistry")
