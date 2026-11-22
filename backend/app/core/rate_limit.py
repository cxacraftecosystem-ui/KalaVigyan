import hashlib
import hmac
from collections.abc import Mapping
from datetime import datetime
from ipaddress import ip_address
from types import MappingProxyType
from typing import Any

from starlette.requests import HTTPConnection

from app.core.allowances import Taken, give_back, take, take_sliding
from app.core.config import get_settings
from app.core.roles import ADMIN, has_rank

CAMPUS_PAGE_VIEWS_PER_WINDOW = 30
COUNTED_READS_PER_PAGE_VIEW = 30
PUBLIC_READS_PER_WINDOW = CAMPUS_PAGE_VIEWS_PER_WINDOW * COUNTED_READS_PER_PAGE_VIEW
PUBLIC_READ_WINDOW_SECONDS = 600
SERVER_READS_PER_WINDOW = 9000
SERVER_READ_KEY = "public-read:web-server"
ASSET_READS_PER_COUNTED_READ = 10
PUBLIC_ASSET_READS_PER_WINDOW = PUBLIC_READS_PER_WINDOW * ASSET_READS_PER_COUNTED_READ
SERVER_ASSET_READS_PER_WINDOW = SERVER_READS_PER_WINDOW * ASSET_READS_PER_COUNTED_READ
SERVER_ASSET_READ_KEY = "public-asset:web-server"
MCP_CALLS_PER_CONNECTION_WINDOW = 1200
MCP_CONNECTION_WINDOW_SECONDS = 600
CLIENT_REGISTRATIONS_PER_WINDOW = 20
CLIENT_REGISTRATION_WINDOW_SECONDS = 3600
CODE_ATTEMPTS_PER_WINDOW = 10
CODE_WINDOW_SECONDS = 900
DIGEST_CHARS = 32
FACT_PROPOSALS = "facts"
COMPONENT_PROPOSALS = "components"
LAYOUT_PROPOSALS = "layouts"
IMAGE_UPLOADS = "pictures"
STRUCTURE_PROPOSALS = "structure"
PAGE_PROPOSALS = "pages"
PAGE_PREVIEWS = "previews"
FACT_PROPOSALS_PER_WINDOW = 30
COMPONENT_PROPOSALS_PER_WINDOW = 10
LAYOUT_PROPOSALS_PER_WINDOW = 10
IMAGE_UPLOADS_PER_WINDOW = 20
STRUCTURE_PROPOSALS_PER_WINDOW = 20
PAGE_PROPOSALS_PER_WINDOW = 10
PAGE_PREVIEWS_PER_WINDOW = 30
PROPOSAL_LIMITS: Mapping[str, int] = MappingProxyType(
    {
        FACT_PROPOSALS: FACT_PROPOSALS_PER_WINDOW,
        COMPONENT_PROPOSALS: COMPONENT_PROPOSALS_PER_WINDOW,
        LAYOUT_PROPOSALS: LAYOUT_PROPOSALS_PER_WINDOW,
        IMAGE_UPLOADS: IMAGE_UPLOADS_PER_WINDOW,
        STRUCTURE_PROPOSALS: STRUCTURE_PROPOSALS_PER_WINDOW,
        PAGE_PROPOSALS: PAGE_PROPOSALS_PER_WINDOW,
        PAGE_PREVIEWS: PAGE_PREVIEWS_PER_WINDOW,
    }
)
SOURCE_SEARCHES = "source searches"
SOURCE_READS = "source reads"
PAID_SEARCHES = "paid searches"
SOURCE_ARCHIVES = "source archives"
LOOKUP_TIERS = ("NEW", "ESTABLISHED", "PROVEN")
ANONYMOUS_HOLDER = "anonymous"
LOOKUP_LIMITS: Mapping[str, Mapping[str, int]] = MappingProxyType(
    {
        SOURCE_SEARCHES: MappingProxyType({"NEW": 30, "ESTABLISHED": 60, "PROVEN": 120}),
        SOURCE_READS: MappingProxyType({"NEW": 120, "ESTABLISHED": 240, "PROVEN": 480}),
        PAID_SEARCHES: MappingProxyType({"NEW": 5, "ESTABLISHED": 15, "PROVEN": 30}),
        SOURCE_ARCHIVES: MappingProxyType({"NEW": 5, "ESTABLISHED": 10, "PROVEN": 20}),
    }
)
ANONYMOUS_LOOKUP_LIMITS: Mapping[str, int] = MappingProxyType({SOURCE_SEARCHES: 120, SOURCE_READS: 600})

WEB_PROXY_SECRET_HEADER = "x-web-proxy-secret"
VIEWER_ADDRESS_HEADER = "x-viewer-address"

Attempt = tuple[bool, float]


def sent_by_web_server(connection: HTTPConnection) -> bool:
    secret = (get_settings().web_proxy_secret or "").strip()
    sent = connection.headers.get(WEB_PROXY_SECRET_HEADER)
    if not secret or sent is None:
        return False
    return hmac.compare_digest(sent.strip().encode("utf-8"), secret.encode("utf-8"))


def trusted_viewer_address(connection: HTTPConnection) -> str | None:
    viewer = connection.headers.get(VIEWER_ADDRESS_HEADER)
    if viewer is None or not sent_by_web_server(connection):
        return None
    try:
        return str(ip_address(viewer.strip()))
    except ValueError:
        return None


def is_web_server_read(connection: HTTPConnection) -> bool:
    return connection.headers.get(VIEWER_ADDRESS_HEADER) is None and sent_by_web_server(connection)


def client_ip(connection: HTTPConnection) -> str:
    viewer = trusted_viewer_address(connection)
    if viewer:
        return viewer
    direct = connection.client.host if connection.client else ""
    try:
        trusted = ip_address(direct).is_loopback if direct else False
    except ValueError:
        trusted = False
    if trusted:
        forwarded = connection.headers.get("x-forwarded-for", "")
        hops = [hop.strip() for hop in forwarded.split(",") if hop.strip()]
        depth = get_settings().forwarded_client_hops
        if hops:
            return hops[-depth] if len(hops) >= depth else hops[0]
        real = connection.headers.get("x-real-ip", "").strip()
        if real:
            return real
    return direct or "unknown"


def ip_hash(address: str) -> str:
    return _keyed_digest("ip", address)


async def sign_in_attempt_by_ip(connection: HTTPConnection, *, now: datetime | None = None) -> Attempt:
    settings = get_settings()
    key = f"ip:{client_ip(connection)}"
    return await _attempt(key, settings.sign_in_attempts_per_ip, settings.sign_in_window_seconds, now=now)


async def sign_in_attempt_by_account(account_key: str, *, now: datetime | None = None) -> Attempt:
    settings = get_settings()
    key = f"acct:{account_key}"
    return await _attempt(
        key, settings.sign_in_attempts_per_account, settings.sign_in_window_seconds, now=now
    )


async def refund_account(account_key: str, *, now: datetime | None = None) -> None:
    await _refund(f"acct:{account_key}", get_settings().sign_in_window_seconds, now=now)


async def refund_ip(connection: HTTPConnection, *, now: datetime | None = None) -> None:
    await _refund(f"ip:{client_ip(connection)}", get_settings().sign_in_window_seconds, now=now)


async def forgot_password_attempt(connection: HTTPConnection, *, now: datetime | None = None) -> Attempt:
    return await _attempt(f"forgot:{client_ip(connection)}", 5, 3600, now=now)


async def code_attempt(user_id: str, *, now: datetime | None = None) -> Attempt:
    return await _attempt(f"code:{user_id}", CODE_ATTEMPTS_PER_WINDOW, CODE_WINDOW_SECONDS, now=now)


async def refund_code(user_id: str, *, now: datetime | None = None) -> None:
    await _refund(f"code:{user_id}", CODE_WINDOW_SECONDS, now=now)


async def ask_attempt(user_id: str, *, now: datetime | None = None) -> Attempt:
    return await _attempt(f"ask:{user_id}", 30, 600, now=now)


async def term_attempt(user_id: str, *, now: datetime | None = None) -> Attempt:
    return await _attempt(f"term:{user_id}", 60, 600, now=now)


async def listen_attempt(user_id: str, *, now: datetime | None = None) -> Attempt:
    return await _attempt(f"listen:{user_id}", 30, 600, now=now)


async def film_score_attempt(user_id: str, *, now: datetime | None = None) -> Attempt:
    return await _attempt(f"film-score:{user_id}", 10, 600, now=now)


async def voice_session_attempt(user_id: str, *, now: datetime | None = None) -> Attempt:
    return await _attempt(f"voice:{user_id}", 10, 600, now=now)


async def voice_turn_attempt(user_id: str, *, now: datetime | None = None) -> Attempt:
    return await _attempt(f"voice-turn:{user_id}", 40, 600, now=now)


async def voice_speech_attempt(user_id: str, *, now: datetime | None = None) -> Attempt:
    return await _attempt(f"voice-speech:{user_id}", 60, 600, now=now)


async def mcp_connection_attempt(connection_key: str, *, now: datetime | None = None) -> Attempt:
    return await _attempt(
        f"mcp-connection:{connection_key}",
        MCP_CALLS_PER_CONNECTION_WINDOW,
        MCP_CONNECTION_WINDOW_SECONDS,
        now=now,
    )


async def client_registration_attempt(connection: HTTPConnection, *, now: datetime | None = None) -> Attempt:
    return await _attempt(
        f"oauth-register:{client_ip(connection)}",
        CLIENT_REGISTRATIONS_PER_WINDOW,
        CLIENT_REGISTRATION_WINDOW_SECONDS,
        now=now,
    )


async def proposal_attempt(kind: str, user: Any, *, now: datetime | None = None) -> Taken:
    return await proposal_slots(kind, user, 1, now=now)


async def proposal_slots(
    kind: str, user: Any, wanted: int, *, limit: int | None = None, now: datetime | None = None
) -> Taken:
    if has_rank(user, ADMIN):
        return Taken(granted=wanted)
    allowed = PROPOSAL_LIMITS[kind] if limit is None else limit
    return await take(str(user.id), kind, wanted, allowed, now=now)


async def lookup_attempt(kind: str, holder: str, limit: int, *, now: datetime | None = None) -> Taken:
    return await take(holder, kind, 1, limit, now=now)


async def public_read_attempt(connection: HTTPConnection, *, now: datetime | None = None) -> Attempt:
    if is_web_server_read(connection):
        return await _attempt(SERVER_READ_KEY, SERVER_READS_PER_WINDOW, PUBLIC_READ_WINDOW_SECONDS, now=now)
    key = f"public-read:{client_ip(connection)}"
    return await _attempt(key, PUBLIC_READS_PER_WINDOW, PUBLIC_READ_WINDOW_SECONDS, now=now)


async def public_asset_attempt(connection: HTTPConnection, *, now: datetime | None = None) -> Attempt:
    if is_web_server_read(connection):
        limit = SERVER_ASSET_READS_PER_WINDOW
        return await _attempt(SERVER_ASSET_READ_KEY, limit, PUBLIC_READ_WINDOW_SECONDS, now=now)
    key = f"public-asset:{client_ip(connection)}"
    return await _attempt(key, PUBLIC_ASSET_READS_PER_WINDOW, PUBLIC_READ_WINDOW_SECONDS, now=now)


def retry_after_value(wait_seconds: float) -> str:
    return str(max(1, int(wait_seconds + 0.999)))


async def _attempt(key: str, limit: int, seconds: int, *, now: datetime | None) -> Attempt:
    kind, holder = _bucket_names(key)
    taken = await take_sliding(holder, kind, limit, seconds=seconds, now=now)
    return taken.granted > 0, taken.wait_seconds


async def _refund(key: str, seconds: int, *, now: datetime | None) -> None:
    kind, holder = _bucket_names(key)
    await give_back(holder, kind, seconds=seconds, now=now)


def _bucket_names(key: str) -> tuple[str, str]:
    kind, _, subject = key.partition(":")
    return kind, _keyed_digest("limit", subject)


def _keyed_digest(label: str, value: str) -> str:
    key = get_settings().jwt_secret.encode("utf-8")
    digest = hmac.new(key, f"{label}:{value}".encode(), hashlib.sha256).hexdigest()
    return digest[:DIGEST_CHARS]
