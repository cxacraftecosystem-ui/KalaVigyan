import asyncio
import hashlib
import ssl

import httpx
import pytest

from app.core.errors import ExternalFailure
from app.research.fetcher import FetchRefused, FetchRequest

from .pdf_fixture import pdf_with_pages
from .site import FETCHED, PUBLIC_A, PUBLIC_B, Site, fixture, html, redirect

ARTICLE = "https://crafts.example.org/ajrakh/resist-printing"
HOST = "crafts.example.org"
ARTICLE_KEY = f"{HOST}/ajrakh/resist-printing"


def article_site(**routes: httpx.Response) -> Site:
    return Site(
        routes={ARTICLE_KEY: html(fixture("article.html"))} | routes,
        dns={HOST: [PUBLIC_A], "mirror.example.net": [PUBLIC_B], "intranet.example.org": ["10.1.2.3"]},
    )


async def test_the_page_is_fetched_from_the_vetted_address_with_tls_for_the_named_host() -> None:
    site = article_site()
    page = await site.fetcher().fetch(FetchRequest(url=ARTICLE))
    sent = next(r for r in site.requests if r.url.path == "/ajrakh/resist-printing")
    assert sent.url.host == PUBLIC_A
    assert sent.headers["host"] == HOST
    assert sent.extensions["sni_hostname"] == HOST
    body = fixture("article.html")
    assert (page.status, page.content_type, page.bytes, page.sha256) == (
        200,
        "text/html",
        len(body),
        hashlib.sha256(body).hexdigest(),
    )
    assert (page.url, page.final_url, page.redirects, page.fetched_at) == (ARTICLE, ARTICLE, [], FETCHED)


async def test_scripts_styles_and_hidden_text_never_reach_the_page_text() -> None:
    page = await article_site().fetcher().fetch(FetchRequest(url=ARTICLE))
    assert "alum is printed where red is wanted." in page.text
    assert "Indigo vats are fermented separately with jaggery and lime for about ten days." in page.text
    for planted in (
        "ignore previous instructions",
        "injected by script",
        "safe to drink",
        "999 degree",
        "decorative line",
        "Enable scripts",
        "color: #333",
    ):
        assert planted not in page.text


async def test_redirects_are_followed_up_to_three_and_recorded() -> None:
    site = article_site(
        **{
            f"{HOST}/a": redirect("/b"),
            f"{HOST}/b": redirect("https://mirror.example.net/c", 301),
            "mirror.example.net/c": redirect(ARTICLE, 308),
        }
    )
    page = await site.fetcher().fetch(FetchRequest(url=f"https://{HOST}/a"))
    assert page.redirects == [f"https://{HOST}/b", "https://mirror.example.net/c", ARTICLE]
    assert page.final_url == ARTICLE


async def test_a_fourth_redirect_is_refused() -> None:
    site = article_site(**{f"{HOST}/r{i}": redirect(f"/r{i + 1}") for i in range(4)})
    with pytest.raises(FetchRefused) as refused:
        await site.fetcher().fetch(FetchRequest(url=f"https://{HOST}/r0"))
    assert refused.value.reason == "TOO_MANY_REDIRECTS"
    assert f"{HOST}/r4" not in site.page_requests()


async def test_a_redirect_to_a_private_address_is_refused_before_any_request_to_it() -> None:
    site = article_site(**{f"{HOST}/go": redirect("https://intranet.example.org/admin")})
    with pytest.raises(FetchRefused) as refused:
        await site.fetcher().fetch(FetchRequest(url=f"https://{HOST}/go"))
    assert refused.value.reason == "PRIVATE_ADDRESS"
    assert all(r.headers["host"] != "intranet.example.org" for r in site.requests)


async def test_a_redirect_to_plain_http_is_refused() -> None:
    site = article_site(**{f"{HOST}/go": redirect(f"http://{HOST}/ajrakh/resist-printing", 301)})
    with pytest.raises(FetchRefused) as refused:
        await site.fetcher().fetch(FetchRequest(url=f"https://{HOST}/go"))
    assert refused.value.reason == "NOT_HTTPS"


async def test_a_redirect_to_the_metadata_address_is_refused() -> None:
    site = article_site(**{f"{HOST}/go": redirect("https://169.254.169.254/latest/meta-data/")})
    with pytest.raises(FetchRefused) as refused:
        await site.fetcher().fetch(FetchRequest(url=f"https://{HOST}/go"))
    assert refused.value.reason == "PRIVATE_ADDRESS"


async def test_robots_disallow_stops_the_fetch_before_the_page_is_requested() -> None:
    site = article_site(
        **{
            f"{HOST}/robots.txt": httpx.Response(
                200,
                text="User-agent: KalaVigyan\nDisallow: /ajrakh/\n",
                headers={"content-type": "text/plain"},
            )
        }
    )
    with pytest.raises(FetchRefused) as refused:
        await site.fetcher().fetch(FetchRequest(url=ARTICLE))
    assert refused.value.reason == "ROBOTS_DISALLOWED"
    assert site.page_requests() == []


async def test_robots_that_cannot_be_read_because_the_server_fails_disallow_everything() -> None:
    site = article_site(**{f"{HOST}/robots.txt": httpx.Response(503)})
    with pytest.raises(FetchRefused) as refused:
        await site.fetcher().fetch(FetchRequest(url=ARTICLE))
    assert refused.value.reason == "ROBOTS_DISALLOWED"


async def test_robots_are_read_once_per_host_while_fresh() -> None:
    site = article_site()
    fetcher = site.fetcher()
    await fetcher.fetch(FetchRequest(url=ARTICLE))
    await fetcher.fetch(FetchRequest(url=ARTICLE))
    assert [r.url.path for r in site.requests].count("/robots.txt") == 1


async def test_a_declared_length_over_the_cap_is_refused_unread() -> None:
    site = article_site()
    with pytest.raises(FetchRefused) as refused:
        await site.fetcher().fetch(FetchRequest(url=ARTICLE, max_bytes=1024))
    assert refused.value.reason == "TOO_LARGE"


async def test_a_streamed_body_over_the_cap_is_cut_off() -> None:
    async def endless():
        for _ in range(64):
            yield b"<p>" + b"x" * 1000 + b"</p>"

    site = article_site(
        **{ARTICLE_KEY: httpx.Response(200, headers={"content-type": "text/html"}, content=endless())}
    )
    with pytest.raises(FetchRefused) as refused:
        await site.fetcher().fetch(FetchRequest(url=ARTICLE, max_bytes=10_000))
    assert refused.value.reason == "TOO_LARGE"


async def test_content_types_other_than_html_pdf_and_text_are_refused() -> None:
    site = article_site(
        **{ARTICLE_KEY: httpx.Response(200, content=b"\x89PNG", headers={"content-type": "image/png"})}
    )
    with pytest.raises(FetchRefused) as refused:
        await site.fetcher().fetch(FetchRequest(url=ARTICLE))
    assert refused.value.reason == "CONTENT_TYPE"


async def test_a_slow_server_hits_the_time_limit() -> None:
    async def slow(request: httpx.Request) -> httpx.Response:
        await asyncio.sleep(2)
        return html("<p>late</p>")

    site = article_site()
    site.routes[ARTICLE_KEY] = slow
    with pytest.raises(FetchRefused) as refused:
        await site.fetcher().fetch(FetchRequest(url=ARTICLE, timeout_seconds=0.05))
    assert refused.value.reason == "TIME_LIMIT"


async def test_a_certificate_for_another_host_is_a_tls_mismatch() -> None:
    def wrong_certificate(request: httpx.Request) -> httpx.Response:
        try:
            raise ssl.SSLCertVerificationError(1, "certificate verify failed: Hostname mismatch")
        except ssl.SSLError as error:
            raise httpx.ConnectError("handshake failed") from error

    site = article_site()
    site.routes[ARTICLE_KEY] = wrong_certificate
    site.routes[f"{HOST}/robots.txt"] = httpx.Response(404)
    with pytest.raises(FetchRefused) as refused:
        await site.fetcher().fetch(FetchRequest(url=ARTICLE))
    assert refused.value.reason == "TLS_MISMATCH"


async def test_an_unreachable_address_moves_on_to_the_next_vetted_one() -> None:
    def first_address_down(request: httpx.Request) -> httpx.Response:
        if request.url.host == PUBLIC_A:
            raise httpx.ConnectError("connection refused")
        return html(fixture("article.html"))

    site = Site(routes={ARTICLE_KEY: first_address_down}, dns={HOST: [PUBLIC_A, PUBLIC_B]})
    page = await site.fetcher().fetch(FetchRequest(url=ARTICLE))
    assert page.status == 200
    assert [r.url.host for r in site.requests if r.url.path == "/ajrakh/resist-printing"] == [
        PUBLIC_A,
        PUBLIC_B,
    ]


@pytest.mark.parametrize(
    ("status", "kind", "retryable"), [(404, "not_found", False), (503, "unavailable", True)]
)
async def test_what_the_remote_side_answers_is_an_external_failure(
    status: int, kind: str, retryable: bool
) -> None:
    site = article_site(**{ARTICLE_KEY: html("gone", status=status)})
    with pytest.raises(ExternalFailure) as failure:
        await site.fetcher().fetch(FetchRequest(url=ARTICLE))
    assert (failure.value.kind, failure.value.retryable, failure.value.status) == (kind, retryable, status)


async def test_a_pdf_is_read_through_the_light_extractor() -> None:
    body = pdf_with_pages(["Alum fixes the red dye on cotton."], title="Mordants")
    site = article_site(
        **{
            f"{HOST}/notes.pdf": httpx.Response(
                200, content=body, headers={"content-type": "application/pdf"}
            )
        }
    )
    page = await site.fetcher().fetch(FetchRequest(url=f"https://{HOST}/notes.pdf"))
    assert (page.content_type, page.text, page.metadata.title) == (
        "application/pdf",
        "Alum fixes the red dye on cotton.",
        "Mordants",
    )


@pytest.mark.parametrize("served_as", ["application/octet-stream", "binary/octet-stream"])
async def test_a_pdf_served_as_an_octet_stream_is_read_as_a_pdf(served_as: str) -> None:
    body = pdf_with_pages(["Alum fixes the red dye on cotton."])
    site = article_site(
        **{f"{HOST}/files/notes.pdf": httpx.Response(200, content=body, headers={"content-type": served_as})}
    )
    page = await site.fetcher().fetch(FetchRequest(url=f"https://{HOST}/files/notes.pdf"))
    assert (page.content_type, page.text) == ("application/pdf", "Alum fixes the red dye on cotton.")
