import pytest

from app.research.evidence import SearchQuery
from app.research.fetcher import FetchedPage
from app.sources.web.page import page_item, readable_url
from app.sources.web.searxng import SearxngAdapter

from .recorded import RETRIEVED, Recorder, Reply, fixed_clock, source_http

SEARXNG = "127.0.0.1/search"
SITE = "https://crafts.example.org/"
GI_RECORD = "https://search.ipindia.gov.in/GIRPublic/Application/Details/646"


class NoFetcher:
    async def fetch(self, request: object) -> FetchedPage:
        raise AssertionError("a search reads no page")


@pytest.mark.parametrize(
    ("given", "readable"),
    [
        ("http://old.example.in", "https://old.example.in/"),
        ("http://old.example.in:80/bagh?x=1", "https://old.example.in/bagh?x=1"),
        ("http://old.example.in:8080/sanganer", None),
        ("http://old.example.in:99999/a", None),
        ("http://weaver@old.example.in/a", None),
        ("ftp://old.example.in/a", None),
        ("https://crafts.example.org/a?utm_source=mail&id=7", "https://crafts.example.org/a?id=7"),
        ("https://crafts.example.org/a?id=7", "https://crafts.example.org/a?id=7"),
        (None, None),
    ],
)
def test_a_hit_is_read_over_https_without_its_tracking_tags(given: str | None, readable: str | None) -> None:
    assert readable_url(given) == readable


async def test_plain_http_hits_are_upgraded_and_only_ids_still_too_long_are_left_out() -> None:
    adapter = SearxngAdapter(
        source_http(Recorder({SEARXNG: Reply("searxng_hit_urls.synthetic.json")}), "searxng"),
        base_url="http://127.0.0.1:8888",
        fetcher=NoFetcher(),
        clock=fixed_clock(),
    )
    hits = await adapter.search(SearchQuery(text="ajrakh"), 10)
    assert [(hit.id, hit.trust) for hit in hits] == [
        ("searxng:https://old.example.in/ajrakh.html", "C"),
        ("searxng:https://old.example.in/bagh?x=1", "C"),
        ("searxng:https://crafts.example.org/ajrakh?id=7", "C"),
        (f"searxng:{SITE}{'b' * 400}", "C"),
        ("searxng:https://www.incredibleindia.gov.in/en/gujarat/ajrakh", "B"),
        (f"searxng:{GI_RECORD}", "A"),
    ]


def fetched(url: str, final_url: str) -> FetchedPage:
    return FetchedPage.model_validate(
        {
            "url": url,
            "finalUrl": final_url,
            "redirects": [final_url] if final_url != url else [],
            "status": 200,
            "contentType": "text/html",
            "bytes": 100,
            "sha256": "c" * 64,
            "fetchedAt": RETRIEVED,
            "text": "Kutch Ajrakh is registered as a geographical indication.",
            "truncated": False,
            "metadata": {},
        }
    )


@pytest.mark.parametrize(
    ("asked", "landed", "trust"),
    [
        (f"{SITE}gi", GI_RECORD, "A"),
        (GI_RECORD, f"{SITE}moved", "C"),
        ("https://textiles.example.ac.in/kutch", "https://textiles.example.ac.in/kutch", "B"),
    ],
)
def test_a_read_page_takes_the_trust_of_the_host_it_was_read_from(
    asked: str, landed: str, trust: str
) -> None:
    item = page_item("searxng", asked, fetched(asked, landed))
    assert (item.id, item.url, item.trust) == (f"searxng:{asked}", landed, trust)
