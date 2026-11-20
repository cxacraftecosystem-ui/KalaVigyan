import re
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from app.api.mcp_lookup_tools import LOOKUP_TOOL_NAMES
from app.api.mcp_tools import TOOLS
from app.core.errors import ExternalFailure
from app.core.mcp_scopes import CONTRIBUTE_SCOPE, READ_SCOPE
from app.core.rate_limit import LOOKUP_TIERS
from app.core.roles import RESEARCHER, STUDENT
from app.models import Source
from app.models.contributions import TRUST_TIERS
from app.research.images import ImageCandidate
from app.services import knowledge_api
from app.services.source_lookup_pictures import COMMONS_WIDTHS
from app.services.source_lookup_sources import LookupSources

from .lookup_fakes import (
    FETCHED_AT,
    PAGE_URL,
    PDF_URL,
    FakeArchiver,
    FakeFetcher,
    FakeLocator,
    FakePictures,
    FakeSearcher,
    FakeSession,
    call,
    item,
    open_location,
    person,
    serve,
    tool_context,
)

REPOSITORY = Path(__file__).resolve().parents[3]
COMMONS_PICTURE = REPOSITORY / "frontend" / "lib" / "commonsPicture.ts"
DOI = "10.1234/ajrakh.5"
PAPER_URL = f"https://doi.org/{DOI}"
WIKI_URL = "https://en.wikipedia.org/wiki/Ajrakh"
EXCERPT = "The cloth is dyed in an indigo vat kept with lime and jaggery for several days."
ORIGINAL = "https://upload.wikimedia.org/wikipedia/commons/a/ab/Ajrakh_block.jpg"
SNAPSHOT = f"https://web.archive.org/web/20261121080000/{PAGE_URL}"
CONTRIBUTOR_TOOLS = {"search_sources", "read_source"}
OPEN_TOOLS = {"lookup"}


def sources(**parts: Any) -> LookupSources:
    return LookupSources(fetcher=FakeFetcher({}), **parts)


def picture(
    original: str, *, licence: str, author: str | None, provider: str = "wikimedia_commons"
) -> ImageCandidate:
    return ImageCandidate(
        provider=provider,
        page_url="https://commons.wikimedia.org/wiki/File:Ajrakh_block.jpg",
        image_url=original,
        original_url=original,
        width=1200,
        height=800,
        title="Ajrakh block",
        author=author,
        site="Wikimedia Commons",
        licence=licence,
        retrieved_at=FETCHED_AT,
    )


def content(result: dict[str, Any]) -> dict[str, Any]:
    assert result["isError"] is False, result
    return result["structuredContent"]


def error_text(result: dict[str, Any]) -> str:
    assert result["isError"] is True, result
    return result["content"][0]["text"]


def test_the_three_source_tools_are_registered_with_their_scopes_hints_and_group() -> None:
    assert set(LOOKUP_TOOL_NAMES) == CONTRIBUTOR_TOOLS | OPEN_TOOLS
    for name in CONTRIBUTOR_TOOLS:
        assert TOOLS[name].scope == CONTRIBUTE_SCOPE, name
    for name in OPEN_TOOLS:
        assert TOOLS[name].scope == READ_SCOPE, name
    for name in LOOKUP_TOOL_NAMES:
        listed = TOOLS[name].listed()
        assert listed["annotations"]["openWorldHint"] is True
        assert listed["annotations"]["readOnlyHint"] is True
        assert listed["_meta"]["kalavigyan/group"] == "sources"
        assert "never follow instructions" not in listed["description"]
        assert listed["inputSchema"]["additionalProperties"] is False
    for name in ("check_quote", "archive_source", "find_pictures", "lookup_compound", "lookup_entity"):
        assert name not in TOOLS


@pytest.mark.parametrize(
    ("kinds", "scope"),
    [
        (["pictures"], READ_SCOPE),
        (["pictures", "pictures"], READ_SCOPE),
        (["pictures", "web"], CONTRIBUTE_SCOPE),
        (["scholarly"], CONTRIBUTE_SCOPE),
        (None, CONTRIBUTE_SCOPE),
    ],
)
def test_a_pictures_search_alone_needs_only_the_read_scope(kinds: list[str] | None, scope: str) -> None:
    given = {"query": "ajrakh"} if kinds is None else {"query": "ajrakh", "kinds": kinds}
    assert TOOLS["search_sources"].scope_for(given) == scope


async def test_sources_and_pictures_are_searched_in_one_call(monkeypatch: pytest.MonkeyPatch) -> None:
    openalex = FakeSearcher("openalex", [item("openalex", PAPER_URL)])
    commons = FakePictures("wikimedia_commons", [picture(ORIGINAL, licence="CC BY-SA 4.0", author="Ann Rao")])
    serve(monkeypatch, sources(scholarly=(openalex,), pictures=(commons,)))
    arguments = {"query": "ajrakh", "kinds": ["scholarly", "pictures"]}
    result = content(await call("search_sources", arguments, tool_context(person(RESEARCHER))))
    assert (result["kinds"], result["searched"]) == (
        ["scholarly", "pictures"],
        ["openalex", "wikimedia_commons"],
    )
    assert [hit["url"] for hit in result["sources"]] == [PAPER_URL]
    assert [found["author"] for found in result["pictures"]] == ["Ann Rao"]


def test_the_lookup_tiers_are_the_trust_tiers() -> None:
    assert LOOKUP_TIERS == TRUST_TIERS


def test_the_commons_widths_are_the_widths_the_site_draws() -> None:
    found = re.search(r"COMMONS_WIDTHS = \[([0-9, ]+)\]", COMMONS_PICTURE.read_text(encoding="utf-8"))
    assert found is not None
    assert tuple(int(width) for width in found.group(1).split(",")) == COMMONS_WIDTHS


async def test_a_signed_out_call_or_an_account_below_researcher_is_refused(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    serve(monkeypatch, sources())
    signed_out = await call("search_sources", {"query": "indigo vat"}, tool_context(None))
    assert "needs a signed-in connection" in error_text(signed_out)
    student = await call("read_source", {"url": PAGE_URL}, tool_context(person(STUDENT)))
    assert "read_source needs a signed-in account of Researcher or above" in error_text(student)


def every_kind() -> LookupSources:
    paper = {"doi": DOI, "trust": "A"}
    return sources(
        scholarly=(
            FakeSearcher(
                "openalex", [item("openalex", PAPER_URL, licence="CC BY 4.0", quotes=[EXCERPT], **paper)]
            ),
            FakeSearcher("crossref", [item("crossref", PAPER_URL, **paper)]),
        ),
        reference=(
            FakeSearcher("wikipedia", [item("wikipedia", WIKI_URL, trust="B", licence="CC BY-SA 4.0")]),
        ),
        web=FakeSearcher("web", [item("web", PAGE_URL, trust="C", licence="All rights reserved")]),
        locator=FakeLocator({DOI: open_location(DOI, PDF_URL)}),
    )


async def test_a_search_merges_results_grades_them_and_marks_licences_and_open_copies(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    serve(monkeypatch, every_kind())
    held = FakeSession(rows=[Source(url=PAGE_URL, doi=None, reliability="B")])
    result = content(
        await call("search_sources", {"query": "indigo vat"}, tool_context(person(RESEARCHER), held))
    )
    assert [hit["url"] for hit in result["sources"]] == [PAPER_URL, WIKI_URL, PAGE_URL]
    first, wiki, page = result["sources"]
    assert (first["foundBy"], first["grade"], first["held"], first["openLicence"]) == (
        ["openalex", "crossref"],
        "A",
        False,
        True,
    )
    assert first["openCopy"] == {
        "status": "GREEN",
        "url": PDF_URL,
        "landingUrl": None,
        "pdfUrl": PDF_URL,
        "licence": "cc-by",
        "openLicence": True,
        "version": None,
    }
    assert first["excerpts"] == [EXCERPT] and first["doi"] == DOI
    assert (wiki["grade"], wiki["openLicence"]) == ("B", True)
    assert (page["grade"], page["held"], page["openLicence"]) == ("B", True, False)
    assert result["searched"] == ["openalex", "crossref", "wikipedia", "web"]
    assert result["unavailable"] == [] and result["notices"] == []


async def test_kinds_narrow_the_search_and_a_failing_searcher_is_listed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    down = FakeSearcher(
        "core", failure=ExternalFailure("core answered 503", kind="unavailable", service="core")
    )
    openalex = FakeSearcher("openalex", [item("openalex", PAPER_URL)])
    web = FakeSearcher("web", [item("web", PAGE_URL, trust="C")])
    serve(monkeypatch, sources(scholarly=(openalex, down), web=web))
    result = content(
        await call(
            "search_sources", {"query": "indigo", "kinds": ["scholarly"]}, tool_context(person(RESEARCHER))
        )
    )
    assert (result["searched"], result["unavailable"], web.asked) == (["openalex"], ["core"], [])
    only_down = sources(scholarly=(down,))
    serve(monkeypatch, only_down)
    failed = await call("search_sources", {"query": "indigo"}, tool_context(person(RESEARCHER)))
    assert "Every source search failed just now" in error_text(failed)


async def test_a_craft_slug_joins_its_name_to_the_query(monkeypatch: pytest.MonkeyPatch) -> None:
    async def known(session: Any, slug: str) -> Any:
        return SimpleNamespace(slug=slug, name="Kutch Ajrakh")

    monkeypatch.setattr(knowledge_api, "known_craft", known)
    openalex = FakeSearcher("openalex", [])
    serve(monkeypatch, sources(scholarly=(openalex,)))
    arguments = {"query": "indigo vat", "craft_slug": "Kutch-Ajrakh"}
    await call("search_sources", arguments, tool_context(person(RESEARCHER)))
    assert openalex.asked == ["indigo vat Kutch Ajrakh"]


async def test_paid_routes_run_only_within_the_paid_searches(monkeypatch: pytest.MonkeyPatch) -> None:
    elsevier = FakeSearcher("elsevier", [])
    free_web, paid_web = FakeSearcher("web", []), FakeSearcher("web", [])
    serve(monkeypatch, sources(scholarly=(elsevier,), web=free_web, paid_web=paid_web), tier="NEW")
    context = tool_context(person(RESEARCHER))
    for _ in range(5):
        assert content(await call("search_sources", {"query": "indigo"}, context))["notices"] == []
    sixth = content(await call("search_sources", {"query": "indigo"}, context))
    assert (len(elsevier.asked), len(paid_web.asked), len(free_web.asked)) == (5, 5, 1)
    assert sixth["notices"][0].startswith("Brave and Elsevier were left out")


async def test_source_searches_follow_the_trust_tier(monkeypatch: pytest.MonkeyPatch) -> None:
    serve(monkeypatch, sources(scholarly=(FakeSearcher("openalex", []),)), tier="NEW")
    context = tool_context(person(RESEARCHER))
    for _ in range(30):
        content(await call("search_sources", {"query": "indigo"}, context))
    spent = error_text(await call("search_sources", {"query": "indigo"}, context))
    assert spent.startswith("This account made 30 source searches in the last hour")
    assert "trust tier (new)" in spent
    serve(monkeypatch, sources(scholarly=(FakeSearcher("openalex", []),)), tier="ESTABLISHED")
    other = tool_context(person(RESEARCHER, number=42))
    for _ in range(31):
        content(await call("search_sources", {"query": "indigo"}, other))


async def test_open_pictures_are_found_by_anyone_with_credit_and_the_commons_widths(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    commons = FakePictures(
        "wikimedia_commons",
        [
            picture(ORIGINAL, licence="CC BY-SA 4.0", author="Ann Rao"),
            picture(ORIGINAL, licence="CC BY-SA 4.0", author="Ann Rao"),
            picture(ORIGINAL.replace("Ajrakh", "Bagru"), licence="CC BY-NC 4.0", author="B. Das"),
        ],
    )
    openverse = FakePictures(
        "openverse", [picture(ORIGINAL.replace("Ajrakh", "Dabu"), licence="CC0", author=None)]
    )
    serve(monkeypatch, sources(pictures=(commons, openverse)))
    result = content(
        await call("search_sources", {"query": "ajrakh block", "kinds": ["pictures"]}, tool_context(None))
    )
    [found] = result["pictures"]
    assert found["credit"] == "Photo: Ann Rao, CC BY-SA 4.0, via Wikimedia Commons"
    assert found["openLicence"] is True
    thumbs = "https://upload.wikimedia.org/wikipedia/commons/thumb/a/ab/Ajrakh_block.jpg"
    assert found["widths"] == [
        {"width": 330, "url": f"{thumbs}/330px-Ajrakh_block.jpg"},
        {"width": 500, "url": f"{thumbs}/500px-Ajrakh_block.jpg"},
        {"width": 960, "url": f"{thumbs}/960px-Ajrakh_block.jpg"},
    ]
    assert result["searched"] == ["wikimedia_commons", "openverse"]


async def test_signed_out_callers_share_one_allowance(monkeypatch: pytest.MonkeyPatch) -> None:
    serve(monkeypatch, sources(pictures=(FakePictures("openverse", []),)))
    for _ in range(120):
        content(await call("search_sources", {"query": "ajrakh", "kinds": ["pictures"]}, tool_context(None)))
    spent = error_text(
        await call("search_sources", {"query": "ajrakh", "kinds": ["pictures"]}, tool_context(None))
    )
    assert spent.startswith("Signed-out callers made 120 source searches together in the last hour")
    content(
        await call(
            "search_sources", {"query": "ajrakh", "kinds": ["pictures"]}, tool_context(person(RESEARCHER))
        )
    )


async def test_a_page_is_archived_within_a_small_allowance(monkeypatch: pytest.MonkeyPatch) -> None:
    archiver = FakeArchiver(SNAPSHOT)
    serve(monkeypatch, sources(archiver=archiver))
    context = tool_context(person(RESEARCHER))
    for _ in range(5):
        saved = content(await call("read_source", {"url": PAGE_URL, "archive": True}, context))["archive"]
        assert saved["archivedUrl"] == SNAPSHOT and saved["url"] == PAGE_URL
    spent = error_text(await call("read_source", {"url": PAGE_URL, "archive": True}, context))
    assert spent.startswith("This account made 5 source archives in the last hour")
    assert archiver.saved == [PAGE_URL] * 5


async def test_an_unreachable_source_is_a_tool_error_naming_it(monkeypatch: pytest.MonkeyPatch) -> None:
    class Down:
        async def save(self, url: str) -> str:
            raise ExternalFailure("did not answer", kind="unavailable", service="wayback-save")

    serve(monkeypatch, sources(archiver=Down()))
    failed = await call("read_source", {"url": PAGE_URL, "archive": True}, tool_context(person(RESEARCHER)))
    assert error_text(failed).startswith("The Wayback Machine could not be reached just now")
