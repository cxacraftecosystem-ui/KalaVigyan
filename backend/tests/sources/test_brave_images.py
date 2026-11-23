from __future__ import annotations

from datetime import UTC, datetime

import pytest

from app.core.errors import ExternalFailure
from app.research.images import ImageCandidate, ImageQuery
from app.sources.images.web_images import WebImages, with_web_image_fallback
from app.sources.web.brave import BraveAdapter

from .recorded import RETRIEVED, Recorder, Reply, fixed_clock, source_http
from .test_web_adapters import PageFetcher

BRAVE_IMAGES = "api.search.brave.com/res/v1/images/search"
BRAVE_KEY = "test-brave-key-not-real"
QUERY = ImageQuery(text="ajrakh block printing")
DOWN = ExternalFailure("searxng could not be reached", kind="unavailable", retryable=True, service="searxng")


def brave(recorder: Recorder) -> BraveAdapter:
    return BraveAdapter(
        source_http(recorder, "brave"), api_key=BRAVE_KEY, fetcher=PageFetcher(), clock=fixed_clock()
    )


async def test_brave_image_results_are_link_cards_whose_picture_the_page_site_serves() -> None:
    recorder = Recorder({BRAVE_IMAGES: Reply("brave_images.synthetic.json")})
    cards = await brave(recorder).images(QUERY, 5)
    assert [(c.page_url, c.image_url, c.width, c.height, c.title, c.site, c.provider) for c in cards] == [
        (
            "https://www.dsource.in/resource/ajrakh/making",
            "https://www.dsource.in/sites/default/files/ajrakh-1.jpg",
            1200,
            800,
            "Ajrakh printing at Dhamadka",
            "dsource.in",
            "brave",
        ),
        (
            "https://www.vam.ac.uk/articles/ajrakh",
            "https://media.vam.ac.uk/media/thira/ajrakh.jpg",
            None,
            None,
            "Ajrakh: cloth resist-printed and dyed",
            "vam.ac.uk",
            "brave",
        ),
    ]
    assert all("imgs.search.brave.com" not in card.image_url for card in cards)
    assert {card.retrieved_at for card in cards} == {RETRIEVED}
    sent = recorder.requests[0]
    assert sent.headers["x-subscription-token"] == BRAVE_KEY
    assert (sent.url.params["q"], sent.url.params["count"], sent.url.params["safesearch"]) == (
        "ajrakh block printing",
        "5",
        "strict",
    )


def card(provider: str, n: int) -> ImageCandidate:
    image = f"https://site{n}.example.org/{provider}-{n}.jpg"
    return ImageCandidate(
        provider=provider,
        page_url=f"https://site{n}.example.org/page",
        image_url=image,
        original_url=image,
        title=f"Picture {n}",
        site=f"site{n}.example.org",
        retrieved_at=datetime(2026, 11, 23, tzinfo=UTC),
    )


class Scripted:
    def __init__(self, name: str, outcome: list[ImageCandidate] | ExternalFailure) -> None:
        self.name = name
        self.outcome = outcome
        self.calls = 0

    async def images(self, query: ImageQuery, k: int) -> list[ImageCandidate]:
        self.calls += 1
        if isinstance(self.outcome, ExternalFailure):
            raise self.outcome
        return self.outcome[:k]


async def test_two_searxng_cards_are_enough_and_brave_is_not_asked() -> None:
    fallback = Scripted("brave", [card("brave", 9)])
    cards = await WebImages(Scripted("searxng", [card("searxng", 1), card("searxng", 2)]), fallback).images(
        QUERY, 10
    )
    assert ([c.provider for c in cards], fallback.calls) == (["searxng", "searxng"], 0)


async def test_one_searxng_card_adds_brave_cards_without_the_same_picture_twice() -> None:
    primary = Scripted("searxng", [card("searxng", 1)])
    same_picture = card("searxng", 1).model_copy(update={"provider": "brave"})
    fallback = Scripted("brave", [same_picture, card("brave", 3)])
    cards = await WebImages(primary, fallback).images(QUERY, 10)
    assert [(c.provider, c.image_url) for c in cards] == [
        ("searxng", "https://site1.example.org/searxng-1.jpg"),
        ("brave", "https://site3.example.org/brave-3.jpg"),
    ]


async def test_a_searxng_failure_asks_brave_and_both_failing_raises_brave_chained() -> None:
    cards = await WebImages(Scripted("searxng", DOWN), Scripted("brave", [card("brave", 4)])).images(
        QUERY, 10
    )
    assert [c.provider for c in cards] == ["brave"]
    brave_down = ExternalFailure("brave answered 429", kind="rate_limit", retryable=True, service="brave")
    with pytest.raises(ExternalFailure) as failure:
        await WebImages(Scripted("searxng", DOWN), Scripted("brave", brave_down)).images(QUERY, 10)
    assert (failure.value, failure.value.__cause__) == (brave_down, DOWN)


async def test_a_brave_failure_keeps_the_one_searxng_card() -> None:
    brave_down = ExternalFailure("brave answered 503", kind="unavailable", service="brave")
    cards = await WebImages(Scripted("searxng", [card("searxng", 1)]), Scripted("brave", brave_down)).images(
        QUERY, 10
    )
    assert [c.provider for c in cards] == ["searxng"]


def test_the_fallback_wraps_the_searxng_source_only_and_keeps_its_name() -> None:
    commons, searxng = Scripted("wikimedia_commons", []), Scripted("searxng", [])
    wrapped = with_web_image_fallback(
        (commons, searxng), primary_name="searxng", fallback=Scripted("brave", [])
    )
    assert [source.name for source in wrapped] == ["wikimedia_commons", "searxng"]
    assert wrapped[0] is commons and isinstance(wrapped[1], WebImages)
    assert with_web_image_fallback((commons, searxng), primary_name="searxng", fallback=None) == (
        commons,
        searxng,
    )
