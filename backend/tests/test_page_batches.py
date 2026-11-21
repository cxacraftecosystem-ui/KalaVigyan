import json
import re
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import httpx
import pytest

from app.research.page_revalidation import PageOwners
from app.services.page_revalidation import (
    MISSES_BEFORE_GIVING_UP,
    REVALIDATE_TARGETS_MAX,
    owner_batches,
    refresh_in_batches,
)

REPO = Path(__file__).resolve().parents[2]
WEB = "https://kalavigyan.example"
SETTINGS: Any = SimpleNamespace(web_revalidate_secret="batch-test-secret", public_web_url=WEB)


def crafts(count: int, prefix: str = "Craft") -> tuple[str, ...]:
    return tuple(f"{prefix}-{number:02d}" for number in range(count))


def test_the_web_takes_as_many_pages_and_tags_in_one_request_as_the_api_sends() -> None:
    source = (REPO / "frontend" / "lib" / "server" / "revalidation.ts").read_text(encoding="utf-8")
    found = re.search(r"export const TARGETS_MAX = (\d+);", source)
    assert found is not None and int(found.group(1)) == REVALIDATE_TARGETS_MAX == 40


def test_ten_crafts_fill_one_request_and_an_eleventh_starts_another() -> None:
    assert owner_batches(PageOwners(crafts=crafts(10))) == [PageOwners(crafts=crafts(10))]
    assert owner_batches(PageOwners(crafts=crafts(11))) == [
        PageOwners(crafts=crafts(10)),
        PageOwners(crafts=("Craft-10",)),
    ]


def test_categories_follow_the_crafts_into_the_room_left() -> None:
    batches = owner_batches(PageOwners(crafts=crafts(9), categories=("a-cat", "b-cat")))
    assert batches == [
        PageOwners(crafts=crafts(9), categories=("a-cat",)),
        PageOwners(categories=("b-cat",)),
    ]
    assert owner_batches(PageOwners()) == []


def test_a_page_too_big_for_one_request_is_refused() -> None:
    with pytest.raises(ValueError, match="more than one request takes"):
        owner_batches(PageOwners(crafts=("Kutch-Ajrakh",)), most=3)


async def test_every_batch_is_sent_and_a_refused_one_is_reported_unrefreshed() -> None:
    sent: list[dict[str, Any]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        sent.append(body)
        return httpx.Response(500 if "/crafts/Craft-10" in body["paths"] else 200)

    owners = PageOwners(crafts=crafts(21), categories=("textiles",))
    done = await refresh_in_batches(owners, settings=SETTINGS, transport=httpx.MockTransport(handler))
    assert [len(body["paths"]) for body in sent] == [20, 20, 4]
    assert (done.batches, done.tried) == (3, 3)
    assert done.unrefreshed == PageOwners(crafts=crafts(20)[10:])
    assert done.refreshed == PageOwners(crafts=(*crafts(10), "Craft-20"), categories=("textiles",))


async def test_an_unreachable_web_is_given_up_after_three_misses() -> None:
    tried: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        tried.append(request)
        raise httpx.ConnectError("no route", request=request)

    owners = PageOwners(crafts=crafts(60))
    done = await refresh_in_batches(owners, settings=SETTINGS, transport=httpx.MockTransport(handler))
    assert MISSES_BEFORE_GIVING_UP == 3
    assert (done.batches, done.tried, len(tried)) == (6, 3, 3)
    assert done.unrefreshed == owners and done.refreshed == PageOwners()
