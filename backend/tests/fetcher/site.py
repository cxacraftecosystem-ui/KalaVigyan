from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

import httpx

from app.fetcher.extract import Extracted
from app.fetcher.parsing import ParseJob, extract_document
from app.fetcher.robots import RobotsPolicy
from app.fetcher.sandbox import SandboxFetcher
from app.fetcher.transport import PinnedHttp

FIXTURES = Path(__file__).parent / "fixtures"
FETCHED = datetime(2026, 11, 16, 10, 0, tzinfo=UTC)
PUBLIC_A = "93.184.215.14"
PUBLIC_B = "151.101.1.69"

Handler = Callable[[httpx.Request], httpx.Response | Awaitable[httpx.Response]]


def fixture(name: str) -> bytes:
    return (FIXTURES / name).read_bytes()


def html(body: bytes | str, status: int = 200, **headers: str) -> httpx.Response:
    content = body.encode() if isinstance(body, str) else body
    return httpx.Response(
        status, content=content, headers={"content-type": "text/html; charset=utf-8"} | headers
    )


def redirect(location: str, status: int = 302) -> httpx.Response:
    return httpx.Response(status, headers={"location": location})


class InlineParser:
    async def parse(self, job: ParseJob) -> Extracted:
        return extract_document(job)


class SiteTransport(httpx.MockTransport):
    def __init__(self, site: Site) -> None:
        super().__init__(site.handle)
        self.site = site

    async def aclose(self) -> None:
        self.site.clients_closed += 1


@dataclass
class Site:
    routes: dict[str, httpx.Response | Handler] = field(default_factory=dict)
    dns: dict[str, list[str]] = field(default_factory=dict)
    requests: list[httpx.Request] = field(default_factory=list)
    lookups: list[str] = field(default_factory=list)
    clients_closed: int = 0

    async def resolve(self, host: str, port: int) -> list[str]:
        self.lookups.append(host)
        if host not in self.dns:
            raise OSError(f"no such host {host}")
        return self.dns[host]

    async def handle(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        key = f"{request.headers['host']}{request.url.raw_path.decode()}"
        route = self.routes.get(key)
        if route is None:
            if key.endswith("/robots.txt"):
                return httpx.Response(404)
            raise AssertionError(f"no route for {key}")
        if isinstance(route, httpx.Response):
            return route
        answer = route(request)
        return answer if isinstance(answer, httpx.Response) else await answer

    def pinned(self) -> PinnedHttp:
        return PinnedHttp(resolve=self.resolve, transport=SiteTransport(self))

    def fetcher(self, *, clock: Callable[[], float] | None = None) -> SandboxFetcher:
        robots = RobotsPolicy(clock=clock) if clock else RobotsPolicy()
        return SandboxFetcher(self.pinned(), robots, InlineParser(), clock=lambda: FETCHED)

    def page_requests(self) -> list[str]:
        return [
            f"{r.headers['host']}{r.url.raw_path.decode()}"
            for r in self.requests
            if not r.url.path.endswith("/robots.txt")
        ]
