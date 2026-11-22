from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any

import pytest
from starlette.datastructures import Headers

from app.core import rate_limit
from app.core.rate_limit import (
    PUBLIC_READS_PER_WINDOW,
    SERVER_READS_PER_WINDOW,
    VIEWER_ADDRESS_HEADER,
    WEB_PROXY_SECRET_HEADER,
    public_read_attempt,
)

SECRET = "proxy-secret"
SIGNING_KEY = "test-only-signing-key"
WEB_SERVER = "198.51.100.20"
VISITOR = "203.0.113.9"
MOMENT = datetime(2026, 11, 22, 10, 5, tzinfo=UTC)


@pytest.fixture
def proxy_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = SimpleNamespace(web_proxy_secret=SECRET, forwarded_client_hops=1, jwt_secret=SIGNING_KEY)
    monkeypatch.setattr(rate_limit, "get_settings", lambda: settings)


def request(address: str, headers: dict[str, str] | None = None) -> Any:
    return SimpleNamespace(client=SimpleNamespace(host=address), headers=Headers(headers or {}))


def server_read(secret: str = SECRET) -> Any:
    return request(WEB_SERVER, {WEB_PROXY_SECRET_HEADER: secret})


def proxied_read(viewer: str) -> Any:
    return request(WEB_SERVER, {WEB_PROXY_SECRET_HEADER: SECRET, VIEWER_ADDRESS_HEADER: viewer})


async def read(connection: Any) -> bool:
    return (await public_read_attempt(connection, now=MOMENT))[0]


async def used_up(connection: Any, reads: int) -> bool:
    answered = [await read(connection) for _ in range(reads)]
    return answered == [True] * reads and not await read(connection)


@pytest.mark.usefixtures("proxy_secret")
async def test_the_web_servers_own_reads_have_their_own_larger_allowance() -> None:
    assert await used_up(request(WEB_SERVER), PUBLIC_READS_PER_WINDOW)
    assert SERVER_READS_PER_WINDOW >= 10 * PUBLIC_READS_PER_WINDOW
    assert await used_up(server_read(), SERVER_READS_PER_WINDOW)
    assert await read(proxied_read(VISITOR)) is True


@pytest.mark.usefixtures("proxy_secret")
async def test_a_wrong_secret_counts_against_the_address_it_came_from() -> None:
    assert await used_up(server_read("not-the-secret"), PUBLIC_READS_PER_WINDOW)
    assert await read(request(WEB_SERVER)) is False
    assert await read(server_read()) is True


@pytest.mark.usefixtures("proxy_secret")
async def test_a_browser_read_through_the_proxy_never_counts_as_the_servers_own() -> None:
    assert await used_up(proxied_read(VISITOR), PUBLIC_READS_PER_WINDOW)
    assert await read(request(VISITOR)) is False
    assert await used_up(proxied_read("unknown"), PUBLIC_READS_PER_WINDOW)
    assert await read(request(WEB_SERVER)) is False
    assert await read(server_read()) is True


async def test_without_a_configured_secret_no_read_is_the_servers_own(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = SimpleNamespace(web_proxy_secret=None, forwarded_client_hops=1, jwt_secret=SIGNING_KEY)
    monkeypatch.setattr(rate_limit, "get_settings", lambda: settings)
    assert await used_up(server_read(), PUBLIC_READS_PER_WINDOW)
    assert await read(request(WEB_SERVER)) is False
