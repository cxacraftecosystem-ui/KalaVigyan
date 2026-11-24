import hashlib
import tracemalloc
import zlib

import httpx
import pytest

from app.fetcher.content_codings import Inflater, content_codings
from app.research.fetcher import FetchRefused, FetchRequest

from .site import PUBLIC_A, Site, fixture

HOST = "crafts.example.org"
ARTICLE = f"https://{HOST}/ajrakh/resist-printing"
ARTICLE_KEY = f"{HOST}/ajrakh/resist-printing"
GZIP_BITS = 31
ZLIB_BITS = 15
RAW_DEFLATE_BITS = -15
BOMB_BYTES = 32 * 1024 * 1024
CAP = 10_000
PEAK_BOUND = 2 * 1024 * 1024
PASSAGE = b"Ajrakh cloth is printed with a resist of lime and gum, then dyed in indigo. " * 50


def compressed(data: bytes, bits: int) -> bytes:
    packer = zlib.compressobj(9, zlib.DEFLATED, bits)
    return packer.compress(data) + packer.flush()


def coded(body: bytes, coding: str) -> httpx.Response:
    async def streamed():
        yield body

    headers = {"content-type": "text/html; charset=utf-8", "content-encoding": coding}
    return httpx.Response(200, headers=headers, content=streamed())


def site_serving(response: httpx.Response) -> Site:
    return Site(routes={ARTICLE_KEY: response}, dns={HOST: [PUBLIC_A]})


def test_identity_and_empty_codings_are_no_coding_at_all() -> None:
    assert content_codings(["identity", " ", "GZIP "]) == ("gzip",)
    assert content_codings([]) == ()


@pytest.mark.parametrize(
    ("coding", "bits"),
    [("gzip", GZIP_BITS), ("x-gzip", GZIP_BITS), ("deflate", ZLIB_BITS), ("deflate", RAW_DEFLATE_BITS)],
)
def test_a_coded_body_within_the_cap_inflates_whole(coding: str, bits: int) -> None:
    assert Inflater(coding, limit=len(PASSAGE)).inflate(compressed(PASSAGE, bits)) == PASSAGE


def test_an_inflated_body_stops_one_byte_past_the_cap() -> None:
    bomb = compressed(bytes(BOMB_BYTES), GZIP_BITS)
    inflater = Inflater("gzip", limit=CAP)
    assert len(inflater.inflate(bomb)) == CAP + 1


async def test_a_gzip_page_is_read_as_the_page_it_codes() -> None:
    body = fixture("article.html")
    site = site_serving(coded(compressed(body, GZIP_BITS), "gzip"))
    page = await site.fetcher().fetch(FetchRequest(url=ARTICLE))
    assert (page.bytes, page.sha256) == (len(body), hashlib.sha256(body).hexdigest())
    assert "alum is printed where red is wanted." in page.text


async def test_a_gzip_bomb_is_refused_without_inflating_past_the_cap() -> None:
    site = site_serving(coded(compressed(bytes(BOMB_BYTES), GZIP_BITS), "gzip"))
    tracemalloc.start()
    try:
        with pytest.raises(FetchRefused) as refused:
            await site.fetcher().fetch(FetchRequest(url=ARTICLE, max_bytes=CAP))
        peak = tracemalloc.get_traced_memory()[1]
    finally:
        tracemalloc.stop()
    assert refused.value.reason == "TOO_LARGE"
    assert peak < PEAK_BOUND


@pytest.mark.parametrize("coding", ["br", "zstd", "compress", "gzip, gzip"])
async def test_a_coding_the_fetcher_does_not_inflate_is_refused_unread(coding: str) -> None:
    site = site_serving(coded(PASSAGE, coding))
    with pytest.raises(FetchRefused) as refused:
        await site.fetcher().fetch(FetchRequest(url=ARTICLE))
    assert refused.value.reason == "CONTENT_TYPE"
