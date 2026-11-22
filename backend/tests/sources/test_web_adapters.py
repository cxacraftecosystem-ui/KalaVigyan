from dataclasses import dataclass, field

import httpx
import pytest

from app.core.errors import ExternalFailure, InvalidInput, NotConfigured
from app.research.evidence import EvidenceItem, SearchQuery, SourceAdapter
from app.research.fetcher import FetchedPage, FetchRefused, FetchRequest
from app.sources.web.brave import BraveAdapter
from app.sources.web.fallback import WebSearch
from app.sources.web.registry import WebSearchConfig, web_search
from app.sources.web.searxng import SearxngAdapter, searxng_time_range

from .recorded import RETRIEVED, Recorder, Reply, fixed_clock, source_http

SEARXNG = "127.0.0.1/search"
BRAVE = "api.search.brave.com/res/v1/web/search"
BRAVE_KEY = "test-brave-key-not-real"
ARTICLE = "https://crafts.example.org/ajrakh/resist-printing"
QUERY = SearchQuery(text="ajrakh mordant alum")


@dataclass
class PageFetcher:
    pages: dict[str, FetchedPage] = field(default_factory=dict)
    requests: list[FetchRequest] = field(default_factory=list)

    async def fetch(self, request: FetchRequest) -> FetchedPage:
        self.requests.append(request)
        page = self.pages.get(request.url)
        if page is None:
            raise FetchRefused(request.url, "ROBOTS_DISALLOWED", "test page not served")
        return page


def fetched(url: str = ARTICLE, **changes: object) -> FetchedPage:
    fields: dict[str, object] = {
        "url": url,
        "finalUrl": url,
        "status": 200,
        "contentType": "text/html",
        "bytes": 2048,
        "sha256": "b" * 64,
        "fetchedAt": RETRIEVED,
        "text": "The resist paste of lime and gum arabic keeps the dye away from the printed areas.",
        "truncated": False,
        "metadata": {
            "title": "Ajrakh resist printing",
            "authors": ["Meera Shah"],
            "published": "2024-03-18",
            "licence": "CC BY 4.0",
            "siteName": "Craft Notes",
        },
    }
    fields.update(changes)
    return FetchedPage.model_validate(fields)


def searxng(recorder: Recorder, fetcher: PageFetcher | None = None) -> SearxngAdapter:
    return SearxngAdapter(
        source_http(recorder, "searxng"),
        base_url="http://127.0.0.1:8888/",
        fetcher=fetcher or PageFetcher(),
        clock=fixed_clock(),
    )


def brave(recorder: Recorder, fetcher: PageFetcher | None = None) -> BraveAdapter:
    return BraveAdapter(
        source_http(recorder, "brave"),
        api_key=BRAVE_KEY,
        fetcher=fetcher or PageFetcher(),
        clock=fixed_clock(),
    )


async def test_searxng_hits_are_https_web_pages_without_quotes() -> None:
    recorder = Recorder({SEARXNG: Reply("searxng_search.synthetic.json")})
    hits = await searxng(recorder).search(QUERY, 10)
    assert [(h.id, h.title, h.published, h.trust, h.tier, h.source_type, h.quotes) for h in hits] == [
        (
            f"searxng:{ARTICLE}",
            "Ajrakh resist printing | Craft Notes",
            "2024-03-18",
            "C",
            "T4",
            "WEB_PAGE",
            [],
        ),
        (
            "searxng:https://old.example.in/ajrakh.html",
            "Ajrakh (insecure mirror)",
            None,
            "C",
            "T4",
            "WEB_PAGE",
            [],
        ),
        (
            "searxng:https://museum.example.org/collection/ajrakh-shawl",
            "Ajrakh shawl, Kutch",
            None,
            "C",
            "T4",
            "WEB_PAGE",
            [],
        ),
    ]
    params = recorder.requests[0].url.params
    assert (params["q"], params["format"], params["language"]) == ("ajrakh mordant alum", "json", "en")


@pytest.mark.parametrize(
    ("days", "time_range"),
    [(None, None), (1, "day"), (5, "week"), (7, "week"), (30, "month"), (200, "year"), (400, None)],
)
def test_freshness_maps_to_the_narrowest_searxng_range_that_covers_it(
    days: int | None, time_range: str | None
) -> None:
    assert searxng_time_range(days) == time_range


async def test_brave_hits_carry_the_site_name_and_the_key_stays_out_of_the_cache_key() -> None:
    recorder = Recorder({BRAVE: Reply("brave_search.synthetic.json")})
    adapter = brave(recorder)
    hits = await adapter.search(QUERY, 3)
    assert [(h.url, h.title, h.publisher, h.published, h.trust) for h in hits] == [
        (ARTICLE, "Ajrakh resist printing", "Craft Notes", "2024-03-18", "C"),
        (
            "https://textiles.example.ac.in/natural-dyes/kutch",
            "Natural dyes of Kutch",
            "Textile Archive",
            "2021-11",
            "B",
        ),
        ("https://chem.example.org/alizarin", "Alizarin lake", "Chem Notes", None, "C"),
    ]
    sent = recorder.requests[0]
    assert sent.headers["x-subscription-token"] == BRAVE_KEY
    assert (sent.url.params["count"], sent.url.params["search_lang"]) == ("3", "en")
    assert BRAVE_KEY not in repr(list(adapter.http.cache._entries))


async def test_brave_freshness_is_an_explicit_date_window() -> None:
    recorder = Recorder({BRAVE: Reply("brave_search.synthetic.json")})
    await brave(recorder).search(SearchQuery(text="ajrakh", freshness_days=30), 5)
    assert recorder.requests[0].url.params["freshness"] == "2026-10-17to2026-11-16"


async def test_brave_without_web_results_is_no_hits() -> None:
    assert await brave(Recorder({BRAVE: Reply("brave_no_web.synthetic.json")})).search(QUERY, 5) == []


def test_brave_refuses_to_build_without_a_key() -> None:
    with pytest.raises(NotConfigured) as missing:
        BraveAdapter(source_http(Recorder({}), "brave"), api_key="", fetcher=PageFetcher())
    assert missing.value.name == "BRAVE_SEARCH_API_KEY"


async def test_fetch_reads_the_page_through_the_fetcher_and_cites_the_final_url() -> None:
    moved = "https://crafts.example.org/ajrakh/resist-printing-2024"
    page = fetched(redirects=[moved], finalUrl=moved, truncated=True)
    fetcher = PageFetcher({ARTICLE: page})
    document = await searxng(Recorder({}), fetcher).fetch(f"searxng:{ARTICLE}")
    assert fetcher.requests == [FetchRequest(url=ARTICLE)]
    item = document.item
    assert (item.id, item.url, item.title, item.authors, item.licence, item.publisher, item.retrieved_at) == (
        f"searxng:{ARTICLE}",
        moved,
        "Ajrakh resist printing",
        ["Meera Shah"],
        "CC BY 4.0",
        "Craft Notes",
        RETRIEVED,
    )
    assert item.external_ids == {"sha256": "b" * 64}
    assert (document.content, document.truncated, document.text) == ("FULL_TEXT", True, page.text)


async def test_a_pdf_page_is_not_called_a_web_page() -> None:
    fetcher = PageFetcher({ARTICLE: fetched(contentType="application/pdf")})
    document = await searxng(Recorder({}), fetcher).fetch(f"searxng:{ARTICLE}")
    assert document.item.source_type == "OTHER"


async def test_fetch_refuses_an_id_that_is_not_an_https_url() -> None:
    with pytest.raises(InvalidInput):
        await searxng(Recorder({})).fetch("searxng:http://old.example.in/ajrakh.html")


class Scripted:
    def __init__(self, name: str, outcome: list[EvidenceItem] | ExternalFailure) -> None:
        self.name = name
        self.tier = "T4"
        self.outcome = outcome
        self.calls = 0
        self.fetched: list[str] = []

    async def search(self, query: SearchQuery, k: int) -> list[EvidenceItem]:
        self.calls += 1
        if isinstance(self.outcome, ExternalFailure):
            raise self.outcome
        return self.outcome[:k]

    async def fetch(self, item_id: str):
        self.fetched.append(item_id)
        raise ExternalFailure("not under test", kind="not_found")


def hit(adapter: str, url: str) -> EvidenceItem:
    return EvidenceItem(
        id=f"{adapter}:{url}",
        adapter=adapter,
        tier="T4",
        source_type="WEB_PAGE",
        url=url,
        title=url,
        retrieved_at=RETRIEVED,
        trust="C",
    )


def urls(n: int, adapter: str) -> list[EvidenceItem]:
    return [hit(adapter, f"https://site{i}.example.org/") for i in range(n)]


DOWN = ExternalFailure("searxng could not be reached", kind="unavailable", retryable=True, service="searxng")


async def test_three_searxng_hits_are_enough_and_brave_is_not_asked() -> None:
    primary, fallback = Scripted("searxng", urls(3, "searxng")), Scripted("brave", urls(5, "brave"))
    hits = await WebSearch(primary, fallback).search(QUERY, 10)
    assert ([h.adapter for h in hits], fallback.calls) == (["searxng"] * 3, 0)


async def test_fewer_than_three_hits_add_brave_hits_without_duplicate_sources() -> None:
    primary = Scripted("searxng", [hit("searxng", "https://site0.example.org/")])
    fallback = Scripted(
        "brave", [hit("brave", "https://SITE0.example.org"), hit("brave", "https://site9.example.org/")]
    )
    hits = await WebSearch(primary, fallback).search(QUERY, 10)
    assert [h.id for h in hits] == ["searxng:https://site0.example.org/", "brave:https://site9.example.org/"]


async def test_a_searxng_error_falls_back_to_brave() -> None:
    fallback = Scripted("brave", urls(2, "brave"))
    hits = await WebSearch(Scripted("searxng", DOWN), fallback).search(QUERY, 5)
    assert [h.adapter for h in hits] == ["brave", "brave"]


async def test_a_searxng_error_without_brave_is_raised_not_hidden() -> None:
    with pytest.raises(ExternalFailure) as failure:
        await WebSearch(Scripted("searxng", DOWN)).search(QUERY, 5)
    assert failure.value is DOWN


async def test_both_failing_raises_the_brave_failure_chained_to_searxng() -> None:
    brave_down = ExternalFailure("brave answered 429", kind="rate_limit", retryable=True, service="brave")
    with pytest.raises(ExternalFailure) as failure:
        await WebSearch(Scripted("searxng", DOWN), Scripted("brave", brave_down)).search(QUERY, 5)
    assert (failure.value, failure.value.__cause__) == (brave_down, DOWN)


async def test_a_brave_failure_keeps_the_few_searxng_hits() -> None:
    brave_down = ExternalFailure("brave answered 503", kind="unavailable", service="brave")
    primary = Scripted("searxng", urls(1, "searxng"))
    hits = await WebSearch(primary, Scripted("brave", brave_down)).search(QUERY, 5)
    assert [h.adapter for h in hits] == ["searxng"]


async def test_asking_for_fewer_than_three_needs_only_that_many() -> None:
    fallback = Scripted("brave", urls(2, "brave"))
    hits = await WebSearch(Scripted("searxng", urls(2, "searxng")), fallback).search(QUERY, 2)
    assert (len(hits), fallback.calls) == (2, 0)


async def test_fetch_goes_to_the_adapter_named_by_the_id() -> None:
    primary, fallback = Scripted("searxng", []), Scripted("brave", [])
    search = WebSearch(primary, fallback)
    with pytest.raises(ExternalFailure):
        await search.fetch(f"brave:{ARTICLE}")
    assert (primary.fetched, fallback.fetched) == ([], [f"brave:{ARTICLE}"])
    with pytest.raises(InvalidInput):
        await search.fetch(f"bing:{ARTICLE}")


async def test_the_registry_skips_brave_silently_without_a_key() -> None:
    client = httpx.AsyncClient(transport=httpx.MockTransport(lambda r: httpx.Response(500)))
    without = web_search(WebSearchConfig("http://127.0.0.1:8888"), client, PageFetcher())
    with_key = web_search(WebSearchConfig("http://127.0.0.1:8888", BRAVE_KEY), client, PageFetcher())
    assert [a.name for a in without.adapters] == ["searxng"]
    assert [a.name for a in with_key.adapters] == ["searxng", "brave"]
    assert isinstance(with_key, SourceAdapter)
    assert BRAVE_KEY not in repr(WebSearchConfig("http://127.0.0.1:8888", BRAVE_KEY))


async def test_an_empty_searxng_answer_with_blocked_engines_turns_to_brave() -> None:
    recorder = Recorder(
        {SEARXNG: Reply("searxng_empty.synthetic.json"), BRAVE: Reply("brave_search.synthetic.json")}
    )
    search = WebSearch(searxng(recorder), brave(recorder))
    hits = await search.search(QUERY, 5)
    assert [h.adapter for h in hits] == ["brave", "brave", "brave"]
