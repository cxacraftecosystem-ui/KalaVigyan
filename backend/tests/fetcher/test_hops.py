import httpx
import pytest

from app.research.fetcher import FetchRefused, FetchRequest

from .site import PUBLIC_A, PUBLIC_B, Site, fixture, html, redirect

HOST = "crafts.example.org"
MIRROR = "mirror.example.net"
ARTICLE = f"https://{HOST}/ajrakh/resist-printing"
ARTICLE_KEY = f"{HOST}/ajrakh/resist-printing"


def site_with(dns: dict[str, list[str]], **routes: httpx.Response) -> Site:
    return Site(routes={ARTICLE_KEY: html(fixture("article.html"))} | routes, dns=dns)


async def test_robots_a_same_host_redirect_and_the_page_share_one_client() -> None:
    site = site_with({HOST: [PUBLIC_A]}, **{f"{HOST}/a": redirect("/ajrakh/resist-printing")})
    page = await site.fetcher().fetch(FetchRequest(url=f"https://{HOST}/a"))
    assert page.final_url == ARTICLE
    assert [r.url.path for r in site.requests] == ["/robots.txt", "/a", "/ajrakh/resist-printing"]
    assert site.clients_closed == 1


async def test_another_host_on_the_same_address_gets_its_own_client() -> None:
    site = site_with({HOST: [PUBLIC_A], MIRROR: [PUBLIC_A]}, **{f"{HOST}/a": redirect(f"https://{MIRROR}/c")})
    site.routes[f"{MIRROR}/c"] = html(fixture("article.html"))
    await site.fetcher().fetch(FetchRequest(url=f"https://{HOST}/a"))
    assert {r.url.host for r in site.requests} == {PUBLIC_A}
    assert site.clients_closed == 2


async def test_every_hop_resolves_again_and_passes_the_address_guard() -> None:
    site = site_with({HOST: [PUBLIC_A]})

    def rebound(request: httpx.Request) -> httpx.Response:
        site.dns[HOST] = ["10.1.2.3"]
        return redirect("/b")

    site.routes[f"{HOST}/a"] = rebound
    with pytest.raises(FetchRefused) as refused:
        await site.fetcher().fetch(FetchRequest(url=f"https://{HOST}/a"))
    assert refused.value.reason == "PRIVATE_ADDRESS"
    assert site.lookups == [HOST, HOST, HOST]
    assert f"{HOST}/b" not in site.page_requests()
    assert site.clients_closed == 1


async def test_a_mirror_on_another_address_is_reached_on_that_address() -> None:
    site = site_with({HOST: [PUBLIC_A], MIRROR: [PUBLIC_B]}, **{f"{HOST}/a": redirect(f"https://{MIRROR}/c")})
    site.routes[f"{MIRROR}/c"] = html(fixture("article.html"))
    await site.fetcher().fetch(FetchRequest(url=f"https://{HOST}/a"))
    sent = [(r.headers["host"], r.url.host) for r in site.requests if r.url.path != "/robots.txt"]
    assert sent == [(HOST, PUBLIC_A), (MIRROR, PUBLIC_B)]
    assert site.clients_closed == 2


def robots_chain(hops: int) -> dict[str, httpx.Response]:
    chain = {f"{HOST}/robots.txt": redirect("/r1")}
    chain |= {f"{HOST}/r{n}": redirect(f"/r{n + 1}") for n in range(1, hops)}
    chain[f"{HOST}/r{hops}"] = httpx.Response(
        200, text="User-agent: *\nAllow: /\n", headers={"content-type": "text/plain"}
    )
    return chain


async def test_robots_txt_is_read_through_five_redirects() -> None:
    site = site_with({HOST: [PUBLIC_A]}, **robots_chain(5))
    page = await site.fetcher().fetch(FetchRequest(url=ARTICLE))
    assert page.status == 200


async def test_a_sixth_robots_redirect_disallows_the_site() -> None:
    site = site_with({HOST: [PUBLIC_A]}, **robots_chain(6))
    with pytest.raises(FetchRefused) as refused:
        await site.fetcher().fetch(FetchRequest(url=ARTICLE))
    assert refused.value.reason == "ROBOTS_DISALLOWED"
    assert site.page_requests() == [f"{HOST}/r{n}" for n in range(1, 6)]
