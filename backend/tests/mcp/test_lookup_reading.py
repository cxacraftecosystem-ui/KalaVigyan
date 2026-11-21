import uuid
from typing import Any

import pytest

from app.core.roles import RESEARCHER
from app.research.candidate_gates import quote_gate
from app.research.fetcher import FetchRefused
from app.research.knowledge_writes import ProposedQuote, ProposedSource
from app.research.quotes import quote_key
from app.services import source_lookup_read
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


async def tool(arguments: dict[str, Any]) -> dict[str, Any]:
    result = await call("read_source", arguments, tool_context(person(RESEARCHER)))
    assert result["isError"] is False, result
    return result["structuredContent"]


async def test_read_source_returns_the_very_text_the_quotes_gate_matches(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    serve(monkeypatch, reading(FakeFetcher({PAGE_URL: page()})))
    text = (await tool({"url": PAGE_URL}))["text"]
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
    found = (await tool({"url": PAGE_URL, "around": "lime"}))["text"]
    assert found["found"] == 2
    assert [passage["locator"] for passage in found["passages"]] == ["paragraph 2", "paragraph 3"]
    phrase = (await tool({"url": PAGE_URL, "around": "“mud resist”"}))["text"]
    assert [passage["text"] for passage in phrase["passages"]] == [PAGE_LINES[3]]


async def test_a_long_text_is_read_a_page_at_a_time(monkeypatch: pytest.MonkeyPatch) -> None:
    lines = [LONG_LINE.replace("000", f"{n:03d}") for n in range(1, 31)]
    assert len(lines[0]) == 403
    serve(monkeypatch, reading(FakeFetcher({PAGE_URL: page(text="\n".join(lines))})))
    first = (await tool({"url": PAGE_URL}))["text"]
    assert (len(first["passages"]), first["nextStart"], first["lines"]) == (19, 20, 30)
    second = (await tool({"url": PAGE_URL, "start": 20}))["text"]
    assert second["passages"][0]["text"].startswith("020 ") and second["nextStart"] is None


async def test_a_pdf_is_located_by_line_and_a_doi_by_its_open_copy(monkeypatch: pytest.MonkeyPatch) -> None:
    fetcher = FakeFetcher({PDF_URL: page(PDF_URL, PDF_TEXT, content_type="application/pdf")})
    serve(monkeypatch, reading(fetcher, locator=FakeLocator({DOI: open_location(DOI, PDF_URL)})))
    text = (await tool({"doi": DOI, "around": "heated to 70"}))["text"]
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
    text = (await tool({"doi": DOI}))["text"]
    assert (text["url"], text["doi"], text["readable"]) == (resolver, DOI, True)


async def test_an_unreadable_page_says_why_and_names_its_snapshot(monkeypatch: pytest.MonkeyPatch) -> None:
    blocked = FakeFetcher({PAGE_URL: FetchRefused(PAGE_URL, "ROBOTS_DISALLOWED")})
    serve(monkeypatch, reading(blocked, snapshots=FakeSnapshots(SNAPSHOT)))
    text = (await tool({"url": PAGE_URL}))["text"]
    assert (text["readable"], text["archivedUrl"], text["passages"]) == (False, SNAPSHOT, [])
    assert "ROBOTS_DISALLOWED" in text["unread"]


async def checks(*quotes: dict[str, Any]) -> list[dict[str, Any]]:
    reading = await tool({"url": PAGE_URL, "quotes": list(quotes)})
    assert reading["text"] is None and reading["archive"] is None
    return list(reading["quotes"])


async def test_a_quote_the_gate_would_find_passes_with_where_it_stands(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    serve(monkeypatch, reading(FakeFetcher({PAGE_URL: page()})))
    plain, folded, typographic = await checks(
        {"text": "a paste of lime and gum arabic before the second"},
        {"text": "Printers re-print the resist with a paste"},
        {"text": "“Mud resist” is called dabu"},
    )
    assert (plain["passed"], plain["foundAt"], plain["nearest"]) == (True, ["paragraph 3"], None)
    assert folded["passed"] is True and folded["foundAt"] == ["paragraph 3"]
    assert typographic["passed"] is True


async def test_a_quote_the_gate_would_refuse_fails_with_the_nearest_passage(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    serve(monkeypatch, reading(FakeFetcher({PAGE_URL: page()})))
    quote = "a paste of lime and gum tragacanth before the second dyeing"
    checked, short = await checks({"text": quote, "locator": "paragraph 3"}, {"text": "lime and gum"})
    assert checked["passed"] is False and checked["locator"] == "paragraph 3"
    assert checked["reasons"] == [f"quote 1 from {PAGE_URL} is not in the page as fetched"]
    assert checked["nearest"] == {
        "locator": "paragraph 3",
        "text": "a paste of lime and gum arabic before the second dyeing",
        "shared": 0.91,
    }
    assert short["passed"] is False and "shorter than 20 characters" in short["reasons"][0]


async def test_reading_and_checking_in_one_call_use_the_text_the_signed_in_person_supplied(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    serve(monkeypatch, reading(FakeFetcher({PAGE_URL: page()})))
    readers: list[uuid.UUID | None] = []

    async def spy(session: Any, fetcher: Any, proposed: Any, *, proposer_id: uuid.UUID | None = None) -> Any:
        readers.append(proposer_id)
        return await read_source(session, fetcher, proposed)

    monkeypatch.setattr(source_lookup_read, "read_source", spy)
    both = await tool({"url": PAGE_URL, "around": "lime", "quotes": [{"text": PAGE_LINES[1]}]})
    assert both["text"]["found"] == 2 and both["quotes"][0]["passed"] is True
    assert readers == [uuid.UUID(int=41), uuid.UUID(int=41)]


async def test_a_later_step_that_fails_becomes_a_notice_and_a_first_one_the_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    serve(monkeypatch, reading(FakeFetcher({PAGE_URL: page()})))
    read = await tool({"url": PAGE_URL, "archive": True, "start": 1})
    assert read["text"]["readable"] is True and read["archive"] is None
    assert read["notices"] == [
        "The Wayback Machine is not among this server's sources just now; nothing was read."
    ]
    alone = await call("read_source", {"url": PAGE_URL, "archive": True}, tool_context(person(RESEARCHER)))
    assert alone["isError"] is True and alone["content"][0]["text"].startswith(
        "The Wayback Machine is not among"
    )
    by_doi = await call("read_source", {"doi": DOI, "archive": True}, tool_context(person(RESEARCHER)))
    assert by_doi["isError"] is True and "archive saves a page by its address" in by_doi["content"][0]["text"]


def test_the_nearest_window_is_the_run_sharing_most_of_the_quote_s_words() -> None:
    words = ["the", "vat", "is", "kept", "warm", "and", "the", "cloth", "is", "dipped", "four", "times"]
    assert best_window(words, ["cloth", "is", "dipped", "three", "times"]) == (7, 4)
    assert best_window(words, ["madder"]) == (0, 0)
