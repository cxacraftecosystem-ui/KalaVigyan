import json
from types import SimpleNamespace
from typing import Any

import httpx

from app.research.page_revalidation import (
    REVALIDATE_SECRET_HEADER,
    PageOwners,
    category_targets,
    craft_targets,
    revalidation_request,
)
from app.services.page_revalidation import merged_owners, refresh_pages

WEB = "https://kalavigyan.example/"
SECRET = "revalidate-test-secret"


def settings(secret: str | None = SECRET) -> Any:
    return SimpleNamespace(web_revalidate_secret=secret, public_web_url=WEB)


def test_a_craft_and_a_category_each_name_their_page_their_document_and_their_tags() -> None:
    assert craft_targets("Kutch-Ajrakh") == (
        ["/crafts/Kutch-Ajrakh", "/crafts/Kutch-Ajrakh/monograph"],
        ["craft-page:Kutch-Ajrakh", "monograph-document:craft:Kutch-Ajrakh"],
    )
    assert category_targets("textiles") == (
        ["/categories/textiles", "/categories/textiles/monograph"],
        ["monograph-document:category:textiles"],
    )


def test_a_request_names_each_page_once_crafts_first() -> None:
    asked = revalidation_request(
        PageOwners(crafts=("Bagh-Print", "Ajrakh", "Ajrakh"), categories=("textiles",))
    )
    assert asked.paths == [
        "/crafts/Ajrakh",
        "/crafts/Ajrakh/monograph",
        "/crafts/Bagh-Print",
        "/crafts/Bagh-Print/monograph",
        "/categories/textiles",
        "/categories/textiles/monograph",
    ]
    assert asked.tags == [
        "craft-page:Ajrakh",
        "monograph-document:craft:Ajrakh",
        "craft-page:Bagh-Print",
        "monograph-document:craft:Bagh-Print",
        "monograph-document:category:textiles",
    ]


def test_owners_merge_without_repeating_a_page() -> None:
    merged = merged_owners(PageOwners(crafts=("B", "A")), PageOwners(crafts=("A",), categories=("t",)))
    assert merged == PageOwners(crafts=("A", "B"), categories=("t",))
    assert PageOwners().empty and not merged.empty


async def test_the_web_app_is_asked_to_refresh_with_the_shared_secret() -> None:
    sent: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        sent.append(request)
        return httpx.Response(200, json={"revalidated": True})

    refreshed = await refresh_pages(
        PageOwners(crafts=("Ajrakh",)), settings=settings(), transport=httpx.MockTransport(handler)
    )
    (request,) = sent
    assert refreshed is True
    assert (request.method, str(request.url)) == ("POST", "https://kalavigyan.example/api/revalidate")
    assert request.headers[REVALIDATE_SECRET_HEADER] == SECRET
    assert json.loads(request.content) == {
        "paths": ["/crafts/Ajrakh", "/crafts/Ajrakh/monograph"],
        "tags": ["craft-page:Ajrakh", "monograph-document:craft:Ajrakh"],
    }


async def test_without_a_secret_or_a_page_nothing_is_sent() -> None:
    sent: list[httpx.Request] = []
    transport = httpx.MockTransport(lambda request: sent.append(request) or httpx.Response(200))
    assert (
        await refresh_pages(PageOwners(crafts=("Ajrakh",)), settings=settings(None), transport=transport)
        is False
    )
    assert await refresh_pages(PageOwners(), settings=settings(), transport=transport) is False
    assert sent == []


async def test_a_refusal_or_an_unreachable_web_app_leaves_the_change_in_place() -> None:
    refused = httpx.MockTransport(lambda request: httpx.Response(401))
    assert (
        await refresh_pages(PageOwners(crafts=("Ajrakh",)), settings=settings(), transport=refused) is False
    )

    def unreachable(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("no route", request=request)

    down = httpx.MockTransport(unreachable)
    assert (
        await refresh_pages(PageOwners(categories=("textiles",)), settings=settings(), transport=down)
        is False
    )


async def test_many_crafts_are_refreshed_in_requests_the_web_accepts() -> None:
    sent: list[dict[str, Any]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        sent.append(body)
        if len(body["paths"]) + len(body["tags"]) > 40:
            return httpx.Response(422)
        return httpx.Response(200, json={"revalidated": True})

    slugs = tuple(f"Photo-Craft-{number:02d}" for number in range(23))
    refreshed = await refresh_pages(
        PageOwners(crafts=slugs), settings=settings(), transport=httpx.MockTransport(handler)
    )
    assert refreshed is True
    assert [len(body["paths"]) // 2 for body in sent] == [10, 10, 3]
    pages = [path for body in sent for path in body["paths"] if not path.endswith("/monograph")]
    assert pages == [f"/crafts/{slug}" for slug in slugs]


async def test_one_refused_batch_leaves_the_refresh_unfinished() -> None:
    answers = iter([200, 422])
    transport = httpx.MockTransport(lambda request: httpx.Response(next(answers)))
    slugs = tuple(f"Photo-Craft-{number:02d}" for number in range(12))
    assert await refresh_pages(PageOwners(crafts=slugs), settings=settings(), transport=transport) is False
