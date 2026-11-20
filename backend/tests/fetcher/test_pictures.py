import httpx
import pytest
from fastapi import FastAPI

from app.fetcher.pictures import PictureFetch, add_picture_route
from app.research.fetcher import FetchRefused
from app.research.image_intake_fetch import FINAL_URL_HEADER, PICTURE_FETCH_PATH, PictureFetchRequest

from ..pictures import picture
from .site import PUBLIC_A, Site, html, redirect

HOST = "files.example.org"
PICTURE_URL = f"https://{HOST}/made/vat.png"
PICTURE_KEY = f"{HOST}/made/vat.png"


def picture_site(**routes: httpx.Response) -> Site:
    body = picture(seed=31)
    served = httpx.Response(200, content=body, headers={"content-type": "application/octet-stream"})
    return Site(
        routes={PICTURE_KEY: served} | routes,
        dns={HOST: [PUBLIC_A], "inside.example.org": ["10.0.0.7"]},
    )


async def test_a_picture_link_is_fetched_from_the_vetted_address_and_its_type_read_from_its_bytes() -> None:
    site = picture_site()
    found = await PictureFetch(site.pinned()).fetch(PictureFetchRequest(url=PICTURE_URL))
    assert (found.final_url, found.mime, found.data) == (PICTURE_URL, "image/png", picture(seed=31))
    (sent,) = site.requests
    assert (sent.url.host, sent.headers["host"], sent.extensions["sni_hostname"]) == (PUBLIC_A, HOST, HOST)
    assert sent.headers["accept"].startswith("image/avif")


async def test_a_redirect_is_followed_and_the_last_address_named() -> None:
    moved = f"https://{HOST}/old/vat.png"
    site = picture_site(**{f"{HOST}/old/vat.png": redirect(PICTURE_URL)})
    found = await PictureFetch(site.pinned()).fetch(PictureFetchRequest(url=moved))
    assert found.final_url == PICTURE_URL


async def test_a_page_that_is_not_a_picture_and_a_private_address_are_refused() -> None:
    site = picture_site(**{PICTURE_KEY: html("<html><body>Not a picture</body></html>")})
    with pytest.raises(FetchRefused) as refused:
        await PictureFetch(site.pinned()).fetch(PictureFetchRequest(url=PICTURE_URL))
    assert refused.value.reason == "CONTENT_TYPE" and "text/html" in refused.value.detail
    with pytest.raises(FetchRefused) as inside:
        await PictureFetch(site.pinned()).fetch(PictureFetchRequest(url="https://inside.example.org/a.png"))
    assert inside.value.reason == "PRIVATE_ADDRESS"


async def test_a_picture_over_the_cap_is_refused_while_it_streams() -> None:
    site = picture_site()
    with pytest.raises(FetchRefused) as refused:
        await PictureFetch(site.pinned()).fetch(PictureFetchRequest(url=PICTURE_URL, max_bytes=1000))
    assert refused.value.reason == "TOO_LARGE"


async def test_the_route_answers_with_the_bytes_or_the_refusal() -> None:
    site = picture_site()
    app = FastAPI()
    add_picture_route(app, PictureFetch(site.pinned()))
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://fetcher") as client:
        fetched = await client.post(PICTURE_FETCH_PATH, json={"url": PICTURE_URL})
        refused = await client.post(PICTURE_FETCH_PATH, json={"url": "https://inside.example.org/a.png"})
    assert fetched.status_code == 200 and fetched.content == picture(seed=31)
    assert (fetched.headers["content-type"], fetched.headers[FINAL_URL_HEADER]) == ("image/png", PICTURE_URL)
    assert refused.status_code == 403 and refused.json()["reason"] == "PRIVATE_ADDRESS"
