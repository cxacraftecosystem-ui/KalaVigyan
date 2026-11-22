from __future__ import annotations

import ssl
from dataclasses import dataclass, field
from typing import Protocol

import httpx

from app.core.errors import RETRYABLE_KINDS, ExternalFailure, failure_kind
from app.core.retry_after import parse_headers
from app.research.fetcher import FetchRefused

from .addresses import IpAddress, Resolver, public_addresses, system_resolver
from .targets import Target

__all__ = [
    "FETCHER_USER_AGENT",
    "REDIRECT_STATUSES",
    "Hop",
    "HopGetter",
    "PinnedHttp",
    "PinnedSession",
    "remote_failure",
]

FETCHER_USER_AGENT = "KalaVigyan-Fetcher/1 (+https://kalavigyan.vercel.app)"
REDIRECT_STATUSES = frozenset({301, 302, 303, 307, 308})
SERVICE = "fetcher"
CAUSE_DEPTH = 8


@dataclass(frozen=True)
class Hop:
    target: Target
    status: int
    content_type: str = ""
    charset: str | None = None
    location: str | None = None
    retry_after: float | None = None
    body: bytes = b""
    cache_control: str | None = None

    @property
    def is_redirect(self) -> bool:
        return self.status in REDIRECT_STATUSES

    @property
    def is_success(self) -> bool:
        return 200 <= self.status < 300


class _Unreachable(Exception):
    pass


class HopGetter(Protocol):
    async def get(self, target: Target, *, max_bytes: int, timeout: float, accept: str) -> Hop: ...


@dataclass
class PinnedHttp:
    resolve: Resolver = system_resolver
    ssl_context: ssl.SSLContext = field(default_factory=httpx.create_ssl_context)
    transport: httpx.AsyncBaseTransport | None = None

    def session(self) -> PinnedSession:
        return PinnedSession(self)

    async def get(self, target: Target, *, max_bytes: int, timeout: float, accept: str) -> Hop:
        async with self.session() as session:
            return await session.get(target, max_bytes=max_bytes, timeout=timeout, accept=accept)

    def client(self) -> httpx.AsyncClient:
        if self.transport is not None:
            return httpx.AsyncClient(transport=self.transport, follow_redirects=False, trust_env=False)
        return httpx.AsyncClient(verify=self.ssl_context, follow_redirects=False, trust_env=False)


@dataclass
class PinnedSession:
    http: PinnedHttp
    _clients: dict[tuple[str, IpAddress], httpx.AsyncClient] = field(default_factory=dict)

    async def __aenter__(self) -> PinnedSession:
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        clients, self._clients = list(self._clients.values()), {}
        for client in clients:
            await client.aclose()

    async def get(self, target: Target, *, max_bytes: int, timeout: float, accept: str) -> Hop:
        addresses = await public_addresses(
            target.host, target.port, resolve=self.http.resolve, url=target.url
        )
        for address in addresses:
            try:
                return await self._get_from(
                    address, target, max_bytes=max_bytes, timeout=timeout, accept=accept
                )
            except _Unreachable:
                continue
        raise ExternalFailure(
            f"{target.host} could not be reached", kind="unavailable", retryable=True, service=SERVICE
        )

    async def _get_from(
        self, address: IpAddress, target: Target, *, max_bytes: int, timeout: float, accept: str
    ) -> Hop:
        client = self._client_for(target.host, address)
        request = client.build_request(
            "GET",
            f"https://{_netloc(address)}{target.path}",
            headers={
                "Host": target.host,
                "User-Agent": FETCHER_USER_AGENT,
                "Accept": accept,
                "Accept-Encoding": "identity",
            },
            extensions={"sni_hostname": target.host},
            timeout=timeout,
        )
        response = await _send(client, request, target)
        try:
            return await _read(response, target, max_bytes)
        finally:
            await response.aclose()

    def _client_for(self, host: str, address: IpAddress) -> httpx.AsyncClient:
        client = self._clients.get((host, address))
        if client is None:
            client = self._clients[(host, address)] = self.http.client()
        return client


def remote_failure(hop: Hop) -> ExternalFailure:
    kind = failure_kind(hop.status)
    return ExternalFailure(
        f"{hop.target.host} answered {hop.status}",
        kind=kind,
        retryable=kind in RETRYABLE_KINDS,
        status=hop.status,
        retry_after=hop.retry_after,
        service=SERVICE,
    )


async def _send(client: httpx.AsyncClient, request: httpx.Request, target: Target) -> httpx.Response:
    try:
        return await client.send(request, stream=True)
    except httpx.TimeoutException:
        raise FetchRefused(target.url, "TIME_LIMIT", f"{target.host} did not answer in time") from None
    except httpx.ConnectError as error:
        verify = _certificate_error(error)
        if verify is not None:
            raise FetchRefused(target.url, "TLS_MISMATCH", verify) from None
        raise _Unreachable from None
    except httpx.HTTPError:
        raise ExternalFailure(
            f"{target.host} broke the connection", kind="unavailable", retryable=True, service=SERVICE
        ) from None


async def _read(response: httpx.Response, target: Target, max_bytes: int) -> Hop:
    status = response.status_code
    if status in REDIRECT_STATUSES:
        return Hop(target, status, location=response.headers.get("location"))
    if not 200 <= status < 300:
        return Hop(target, status, retry_after=parse_headers(response.headers))
    declared = response.headers.get("content-length", "")
    if declared.isdigit() and int(declared) > max_bytes:
        raise FetchRefused(target.url, "TOO_LARGE", f"declares {declared} bytes; the cap is {max_bytes}")
    body = bytearray()
    try:
        async for chunk in response.aiter_bytes():
            body.extend(chunk)
            if len(body) > max_bytes:
                raise FetchRefused(target.url, "TOO_LARGE", f"sent more than {max_bytes} bytes")
    except httpx.TimeoutException:
        raise FetchRefused(target.url, "TIME_LIMIT", f"{target.host} stopped sending") from None
    except httpx.HTTPError:
        raise ExternalFailure(
            f"{target.host} broke the connection", kind="unavailable", retryable=True, service=SERVICE
        ) from None
    content_type, charset = _media_type(response.headers.get("content-type", ""))
    cache_control = response.headers.get("cache-control")
    return Hop(
        target,
        status,
        content_type=content_type,
        charset=charset,
        body=bytes(body),
        cache_control=cache_control,
    )


def _media_type(header: str) -> tuple[str, str | None]:
    media, _, params = header.partition(";")
    charset = None
    for param in params.split(";"):
        name, _, value = param.partition("=")
        if name.strip().lower() == "charset" and value.strip():
            charset = value.strip().strip('"').lower()
    return media.strip().lower(), charset


def _certificate_error(error: BaseException) -> str | None:
    seen: BaseException | None = error
    for _ in range(CAUSE_DEPTH):
        if seen is None:
            return None
        if isinstance(seen, ssl.SSLCertVerificationError):
            return getattr(seen, "verify_message", None) or "the certificate does not verify"
        seen = seen.__cause__ or seen.__context__
    return None


def _netloc(address: IpAddress) -> str:
    return f"[{address}]" if address.version == 6 else str(address)
