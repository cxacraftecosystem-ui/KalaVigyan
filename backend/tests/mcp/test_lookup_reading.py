from typing import Any

import pytest

from app.core.roles import RESEARCHER
from app.research.candidate_gates import quote_gate
from app.research.fetcher import FetchRefused
from app.research.knowledge_writes import ProposedQuote, ProposedSource
from app.research.quotes import quote_key
from app.services.candidate_sources import read_source
from app.services.source_lookup_sources import LookupSources
from app.services.source_lookup_text import best_window

from .lookup_fakes import (
    PAGE_LINES,
    PAGE_TEXT,
    PAGE_URL,
    PDF_URL,
    FakeFetcher,
    FakeLocator,
    FakeSession,
    FakeSnapshots,
    call,
    open_location,
    page,
    person,
    serve,
    tool_context,
)

DOI = "10.1234/ajrakh.5"
SNAPSHOT = f"https://web.archive.org/web/20250101000000/{PAGE_URL}"
PDF_TEXT = "Table 2. Dye baths\nalizarin from madder root\nheated to 70 C\nfor two hours in copper vessels\n"
LONG_LINE = "000 " + "abcdefghi " * 39 + "abcdefghi"


def reading(fetcher: FakeFetcher, **parts: Any) -> LookupSources:
    return LookupSources(fetcher=fetcher, **parts)


async def tool(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    result = await call(name, arguments, tool_context(person(RESEARCHER)))
    assert result["isError"] is False, result
    return result["structuredContent"]


async def test_read_source_returns_the_very_text_the_quotes_gate_matches(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    serve(monkeypatch, reading(FakeFetcher({PAGE_URL: page()})))
    text = await tool("read_source", {"url": PAGE_URL})
    assert [passage["text"] for passage in text["passages"]] == list(PAGE_LINES)
    assert [passage["locator"] for passage in text["passages"]] == [f"paragraph {n}" for n in range(1, 5)]
    assert (text["url"], text["readable"], text["lines"], text["nextStart"]) == (PAGE_URL, True, 4, None)
    assert (text["grade"], text["held"], text["title"]) == ("C", False, "Indigo in Ajrakh")
    proposed = ProposedSource(
        url=PAGE_URL, title="Indigo in Ajrakh", quotes=[ProposedQuote(text=PAGE_LINES[1])]
    )
    gate = await read_source(FakeSession(), FakeFetcher({PAGE_URL: page()}), proposed)
    assert gate.cited.text == page().text == PAGE_TEXT.strip()
    assert quote_key(" ".join(passage["text"] for passage in text["passages"])) == quote_key(gate.cited.text)
    for line in PAGE_LINES:
        assert quote_gate("", [gate.cited.model_copy(update={"quotes": [line]})]).passed, line


async def test_around_returns_every_passage_holding_the_words(monkeypatch: pytest.MonkeyPatch) -> None:
    serve(monkeypatch, reading(FakeFetcher({PAGE_URL: page()})))
    found = await tool("read_source", {"url": PAGE_URL, "around": "lime"})
    assert found["found"] == 2
    assert [passage["locator"] for passage in found["passages"]] == ["paragraph 2", "paragraph 3"]
    phrase = await tool("read_source", {"url": PAGE_URL, "around": "“mud resist”"})
    assert [passage["text"] for passage in phrase["passages"]] == [PAGE_LINES[3]]


async def test_a_long_text_is_read_a_page_at_a_time(monkeypatch: pytest.MonkeyPatch) -> None:
    lines = [LONG_LINE.replace("000", f"{n:03d}") for n in range(1, 31)]
    assert len(lines[0]) == 403
    serve(monkeypatch, reading(FakeFetcher({PAGE_URL: page(text="\n".join(lines))})))
    first = await tool("read_source", {"url": PAGE_URL})
    assert (len(first["passages"]), first["nextStart"], first["lines"]) == (19, 20, 30)
    second = await tool("read_source", {"url": PAGE_URL, "start": 20})
    assert second["passages"][0]["text"].startswith("020 ") and second["nextStart"] is None


async def test_a_pdf_is_located_by_line_and_a_doi_by_its_open_copy(monkeypatch: pytest.MonkeyPatch) -> None:
    fetcher = FakeFetcher({PDF_URL: page(PDF_URL, PDF_TEXT, content_type="application/pdf")})
    serve(monkeypatch, reading(fetcher, locator=FakeLocator({DOI: open_location(DOI, PDF_URL)})))
    text = await tool("read_source", {"doi": DOI, "around": "heated to 70"})
    assert (text["url"], text["doi"], text["licence"], text["openLicence"]) == (PDF_URL, DOI, "cc-by", True)
    assert text["passages"] == [
        {
            "locator": "lines 2-4",
            "start": 2,
            "text": "alizarin from madder root heated to 70 C for two hours in copper vessels",
            "cut": False,
        }
    ]
    assert fetcher.asked == [PDF_URL]


async def test_a_doi_without_an_open_copy_is_read_through_doi_org(monkeypatch: pytest.MonkeyPatch) -> None:
    resolver = f"https://doi.org/{DOI}"
    serve(monkeypatch, reading(FakeFetcher({resolver: page(resolver)}), locator=FakeLocator({})))
    text = await tool("read_source", {"doi": DOI})
    assert (text["url"], text["doi"], text["readable"]) == (resolver, DOI, True)


async def test_an_unreadable_page_says_why_and_names_its_snapshot(monkeypatch: pytest.MonkeyPatch) -> None:
    blocked = FakeFetcher({PAGE_URL: FetchRefused(PAGE_URL, "ROBOTS_DISALLOWED")})
    serve(monkeypatch, reading(blocked, snapshots=FakeSnapshots(SNAPSHOT)))
    text = await tool("read_source", {"url": PAGE_URL})
    assert (text["readable"], text["archivedUrl"], text["passages"]) == (False, SNAPSHOT, [])
    assert "ROBOTS_DISALLOWED" in text["unread"]


async def test_a_quote_the_gate_would_find_passes_with_where_it_stands(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    serve(monkeypatch, reading(FakeFetcher({PAGE_URL: page()})))
    plain = await tool(
        "check_quote", {"url": PAGE_URL, "quote": "a paste of lime and gum arabic before the second"}
    )
    assert (plain["passed"], plain["foundAt"], plain["nearest"]) == (True, ["paragraph 3"], None)
    folded = await tool(
        "check_quote", {"url": PAGE_URL, "quote": "Printers re-print the resist with a paste"}
    )
    assert folded["passed"] is True and folded["foundAt"] == ["paragraph 3"]
    typographic = await tool("check_quote", {"url": PAGE_URL, "quote": "“Mud resist” is called dabu"})
    assert typographic["passed"] is True


async def test_a_quote_the_gate_would_refuse_fails_with_the_nearest_passage(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    serve(monkeypatch, reading(FakeFetcher({PAGE_URL: page()})))
    quote = "a paste of lime and gum tragacanth before the second dyeing"
    checked = await tool("check_quote", {"url": PAGE_URL, "quote": quote, "locator": "paragraph 3"})
    assert checked["passed"] is False and checked["locator"] == "paragraph 3"
    assert checked["reasons"] == [f"quote 1 from {PAGE_URL} is not in the page as fetched"]
    assert checked["nearest"] == {
        "locator": "paragraph 3",
        "text": "a paste of lime and gum arabic before the second dyeing",
        "shared": 0.91,
    }
    short = await tool("check_quote", {"url": PAGE_URL, "quote": "lime and gum"})
    assert short["passed"] is False and "shorter than 20 characters" in short["reasons"][0]


def test_the_nearest_window_is_the_run_sharing_most_of_the_quote_s_words() -> None:
    words = ["the", "vat", "is", "kept", "warm", "and", "the", "cloth", "is", "dipped", "four", "times"]
    assert best_window(words, ["cloth", "is", "dipped", "three", "times"]) == (7, 4)
    assert best_window(words, ["madder"]) == (0, 0)
