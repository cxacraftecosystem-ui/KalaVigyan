import json
import uuid
from typing import Any

import pytest

from app.api import mcp_page_read
from app.api.mcp_tools import ToolContext, answer
from app.core.errors import InvalidInput
from app.research.article_sections import ArticleSection
from app.research.coverage import CoverageSubject, Holdings, field_coverage
from app.research.knowledge_api import ComponentSubject, CraftSection, SubjectCoverage
from app.research.open_work import OpenTask
from app.research.page_layout import PageLayout
from app.services.craft_resolver import CraftIndexStore
from app.services.open_work_subjects import WorkSubject

SITE = "https://kalavigyan.example"
CONTEXT = ToolContext(session=None, index=CraftIndexStore(), site=SITE)  # type: ignore[arg-type]
AJRAKH = WorkSubject(uuid.UUID(int=2), "craft", "Kutch-Ajrakh", "Kutch Ajrakh", gi=True)
TEXTILES = WorkSubject(uuid.UUID(int=3), "category", "Textile-Craft-Category", "Textiles", gi=False)
BAGH = WorkSubject(uuid.UUID(int=4), "craft", "Bagh-Print", "Bagh Print", gi=True)
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
STORED = PageLayout.model_validate(
    {
        "subjectKind": "craft",
        "subjectSlug": "Bagh-Print",
        "version": 2,
        "entries": [{"ref": "bagh-print/pictures/i02", "chapter": "glance", "order": 1, "role": "HERO"}],
    }
)
OVERVIEW = ArticleSection(
    subject_kind="category",
    subject_slug="Textile-Craft-Category",
    field="OVERVIEW",
    version=2,
    status="PUBLISHED",
    sentences=[{"text": "Cloth is printed and dyed across India.", "claimIds": [str(uuid.UUID(int=7))]}],
)
KACHCHH = ComponentSubject(kind="PLACE", key="lgd:449", name="Kachchh")
TASK = OpenTask(
    key="THIN_FIELD:craft:Kutch-Ajrakh:HISTORY",
    kind="THIN_FIELD",
    priority="HIGH",
    subject=None,
    field="HISTORY",
    needed="More cited facts about its history.",
    acceptance="Three facts, each with a verbatim quote.",
    count=1,
)


async def call(arguments: dict[str, Any]) -> dict[str, Any]:
    request = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {"name": "get_page", "arguments": arguments},
    }
    reply = await answer(request, CONTEXT)
    assert reply is not None and "result" in reply, reply
    return reply["result"]


async def subject_of(session: Any, kind: str, slug: str) -> WorkSubject:
    found = {(each.kind, each.slug): each for each in (AJRAKH, TEXTILES, BAGH)}.get((kind, slug))
    if found is None:
        raise InvalidInput(
            f"No {kind} has the slug {slug}; find_crafts gives the slugs of crafts and families."
        )
    return found


async def keys_of(session: Any, subject: WorkSubject) -> list[ComponentSubject]:
    if subject.kind == "category":
        return []
    return [ComponentSubject(kind="CRAFT", key=subject.slug, name=subject.name), KACHCHH]


class Reads:
    def __init__(self) -> None:
        self.seen: list[tuple[str, str, str]] = []

    async def coverage(self, session: Any, kind: str, slug: str, *, site: str) -> SubjectCoverage:
        self.seen.append(("coverage", kind, slug))
        return SubjectCoverage(coverage=COVERAGE, open_work=[TASK], page_url=f"{site}/crafts/{slug}")

    async def sections(self, session: Any, slug: str, *, site: str) -> CraftSection:
        self.seen.append(("sections", "craft", slug))
        return CraftSection.model_validate(
            {
                "craft": {"slug": slug, "name": "Kutch Ajrakh", "path": f"/crafts/{slug}"},
                "field": None,
                "section": None,
                "openWork": [TASK.model_dump()],
                "pageUrl": f"{site}/crafts/{slug}",
            }
        )

    async def category_sections(
        self, session: Any, subject: WorkSubject, field: str | None, *, site: str
    ) -> CraftSection:
        self.seen.append(("sections", subject.kind, subject.slug))
        page = subject.task_subject(site)
        return CraftSection(
            subject=page, field=field, section=None, sections=[OVERVIEW], page_url=page.page_url
        )

    async def layout(self, session: Any, subject: WorkSubject) -> PageLayout | None:
        self.seen.append(("layout", subject.kind, subject.slug))
        return STORED if subject is BAGH else None


@pytest.fixture
def asked(monkeypatch: pytest.MonkeyPatch) -> list[tuple[str, str, str]]:
    reads = Reads()
    monkeypatch.setattr(mcp_page_read, "subject_by_key", subject_of)
    monkeypatch.setattr(mcp_page_read, "page_keys", keys_of)
    monkeypatch.setattr(mcp_page_read.coverage_reads, "read_subject_coverage", reads.coverage)
    monkeypatch.setattr(mcp_page_read.knowledge_api, "craft_sections", reads.sections)
    monkeypatch.setattr(mcp_page_read.category_knowledge, "category_sections", reads.category_sections)
    monkeypatch.setattr(mcp_page_read, "layout_of", reads.layout)
    return reads.seen


async def test_get_page_is_a_read_tool_with_three_parts_and_a_compact_output_schema() -> None:
    reply = await answer({"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}}, CONTEXT)
    assert reply is not None
    (listed,) = [tool for tool in reply["result"]["tools"] if tool["name"] == "get_page"]
    assert listed["annotations"]["readOnlyHint"] is True
    assert set(listed["inputSchema"]["properties"]) == {"subject", "parts", "field"}
    output = listed["outputSchema"]["properties"]
    assert {"coverage", "sections", "layout", "openWork", "pageUrl", "attribution"} <= set(output)
    assert output["coverage"] == {"type": ["null", "object"]} and output["openWork"] == {"type": "array"}
    for name in ("get_coverage", "get_section", "get_layout", "list_fields"):
        assert name not in {tool["name"] for tool in reply["result"]["tools"]}


async def test_parts_need_a_page() -> None:
    result = await call({"parts": ["coverage"]})
    assert result["isError"] is True and "name the page as subject" in result["content"][0]["text"]


async def test_a_craft_page_is_read_whole_with_its_open_work_once(asked: list[tuple[str, str, str]]) -> None:
    result = await call({"subject": {"kind": "craft", "slug": "Kutch-Ajrakh"}})
    shown = result["structuredContent"]
    assert asked == [
        ("coverage", "craft", "Kutch-Ajrakh"),
        ("sections", "craft", "Kutch-Ajrakh"),
        ("layout", "craft", "Kutch-Ajrakh"),
    ]
    assert shown["parts"] == ["coverage", "sections", "layout"]
    assert shown["coverage"]["covered"] == ["CHEMISTRY"] and len(shown["coverage"]["missing"]) == 15
    chemistry = next(count for count in shown["coverage"]["fields"] if count["field"] == "CHEMISTRY")
    assert (chemistry["claims"], chemistry["sources"], chemistry["standing"]) == (3, 2, "COVERED")
    assert [task["key"] for task in shown["openWork"]] == [TASK.key]
    assert (shown["layout"], shown["pageUrl"]) == (None, f"{SITE}/crafts/Kutch-Ajrakh")
    assert json.loads(result["content"][0]["text"]) == shown


async def test_one_part_is_read_alone_and_a_layout_comes_with_its_page(
    asked: list[tuple[str, str, str]],
) -> None:
    shown = (await call({"subject": {"kind": "craft", "slug": "Bagh-Print"}, "parts": ["layout"]}))[
        "structuredContent"
    ]
    assert asked == [("layout", "craft", "Bagh-Print")]
    assert shown["layout"]["version"] == 2 and "coverage" not in shown
    assert shown["layout"]["entries"][0] == {
        "ref": "bagh-print/pictures/i02",
        "chapter": "glance",
        "order": 1,
        "role": "HERO",
        "crop": None,
        "size": None,
        "caption": None,
    }
    assert shown["pageUrl"] == f"{SITE}/crafts/Bagh-Print"


async def test_a_category_page_is_read_whole_with_the_sections_it_draws(
    asked: list[tuple[str, str, str]],
) -> None:
    category = {"kind": "category", "slug": "Textile-Craft-Category"}
    shown = (await call({"subject": category}))["structuredContent"]
    assert shown["parts"] == ["coverage", "sections", "layout"]
    assert ("sections", "category", "Textile-Craft-Category") in asked
    (section,) = shown["sections"]
    assert (section["subjectKind"], section["subjectSlug"], section["field"]) == (
        "category",
        "Textile-Craft-Category",
        "OVERVIEW",
    )
    assert section["sentences"][0]["claimIds"] == [str(uuid.UUID(int=7))]
    assert shown["pageUrl"] == f"{SITE}/categories/Textile-Craft-Category" and "keys" not in shown
    alone = (await call({"subject": category, "parts": ["sections"]}))["structuredContent"]
    assert alone["parts"] == ["sections"] and len(alone["sections"]) == 1


async def test_a_craft_page_gives_the_keys_a_component_proposal_names(
    asked: list[tuple[str, str, str]],
) -> None:
    shown = (await call({"subject": {"kind": "craft", "slug": "Bagh-Print"}, "parts": ["layout"]}))[
        "structuredContent"
    ]
    assert shown["keys"] == [
        {"kind": "CRAFT", "key": "Bagh-Print", "name": "Bagh Print"},
        {"kind": "PLACE", "key": "lgd:449", "name": "Kachchh"},
    ]


async def test_an_unknown_slug_or_kind_is_a_tool_error_the_model_can_correct(
    asked: list[tuple[str, str, str]],
) -> None:
    unknown = await call({"subject": {"kind": "family", "slug": "No-Such-Family"}})
    assert unknown["isError"] is True and "find_crafts" in unknown["content"][0]["text"]
    wrong = await call({"subject": {"kind": "planet", "slug": "Bagh-Print"}})
    assert wrong["isError"] is True
