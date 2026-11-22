import hashlib
import json
from datetime import UTC, datetime

import httpx
import pytest

from app.core.errors import ExternalFailure, InvalidInput
from app.research.image_intake_fetch import FINAL_URL_HEADER, PICTURE_FETCH_PATH
from app.services.upload_links_fetch import PictureFetcherClient
from app.sources.fetcher_client import FetchRecord

FETCHER = "http://127.0.0.1:8090"
LINK = "https://files.example.org/vat.png"


def client(answer: httpx.Response, seen: list[httpx.Request]) -> PictureFetcherClient:
    def handle(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return answer

    return PictureFetcherClient(FETCHER, httpx.AsyncClient(transport=httpx.MockTransport(handle)))


async def test_the_api_asks_the_fetcher_for_the_link_and_gets_its_bytes() -> None:
    seen: list[httpx.Request] = []
    served = httpx.Response(
        200, content=b"png", headers={"content-type": "image/png", FINAL_URL_HEADER: LINK}
    )
    found = await client(served, seen).fetch_picture(LINK)
    assert (found.data, found.content_type, found.final_url) == (b"png", "image/png", LINK)
    (sent,) = seen
    assert str(sent.url) == f"{FETCHER}{PICTURE_FETCH_PATH}"
    assert json.loads(sent.content) == {"url": LINK, "maxBytes": 10 * 1024 * 1024}


@pytest.mark.parametrize(
    ("answer", "says"),
    [
        (
            httpx.Response(
                403, json={"url": LINK, "reason": "PRIVATE_ADDRESS", "detail": "inside resolves to 10.0.0.7"}
            ),
            "refused: inside resolves to 10.0.0.7",
        ),
        (
            httpx.Response(502, json={"kind": "not_found", "message": "files.example.org answered 404"}),
            "answered 404",
        ),
    ],
)
async def test_a_refused_or_failed_link_is_said_to_the_giver(answer: httpx.Response, says: str) -> None:
    with pytest.raises(InvalidInput, match=says):
        await client(answer, []).fetch_picture(LINK)


ASKED = datetime(2026, 11, 22, 8, 15, tzinfo=UTC)
MOVED = "https://cdn.example.org/vat.png"


def recording(answer: httpx.Response, kept: list[FetchRecord]) -> PictureFetcherClient:
    async def record(fetch: FetchRecord) -> None:
        kept.append(fetch)

    transport = httpx.MockTransport(lambda request: answer)
    return PictureFetcherClient(
        FETCHER, httpx.AsyncClient(transport=transport), record=record, clock=lambda: ASKED
    )


async def test_a_fetched_picture_is_recorded_with_its_final_url_type_size_and_hash() -> None:
    kept: list[FetchRecord] = []
    served = httpx.Response(
        200, content=b"png", headers={"content-type": "image/png", FINAL_URL_HEADER: MOVED}
    )
    await recording(served, kept).fetch_picture(LINK)
    assert kept == [
        FetchRecord(
            url=LINK,
            fetched_at=ASKED,
            final_url=MOVED,
            status=200,
            content_type="image/png",
            bytes=3,
            sha256=hashlib.sha256(b"png").hexdigest(),
        )
    ]


async def test_a_refused_or_failed_picture_is_recorded_with_its_reason_or_status() -> None:
    kept: list[FetchRecord] = []
    refused = httpx.Response(403, json={"url": LINK, "reason": "PRIVATE_ADDRESS", "detail": "inside"})
    failed = httpx.Response(502, json={"kind": "not_found", "message": "gone", "status": 404})
    for answer in (refused, failed):
        with pytest.raises(InvalidInput):
            await recording(answer, kept).fetch_picture(LINK)
    assert kept == [
        FetchRecord(url=LINK, fetched_at=ASKED, final_url=LINK, blocked_reason="PRIVATE_ADDRESS"),
        FetchRecord(url=LINK, fetched_at=ASKED, status=404),
    ]


async def test_an_answer_off_the_contract_is_a_failure_of_the_fetcher() -> None:
    with pytest.raises(ExternalFailure):
        await client(httpx.Response(403, json={"nope": True}), []).fetch_picture(LINK)
    with pytest.raises(ExternalFailure):
        await client(httpx.Response(500), []).fetch_picture(LINK)
