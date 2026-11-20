import hashlib
import hmac
import threading
import time
from collections import OrderedDict, deque
from collections.abc import Mapping
from ipaddress import ip_address
from types import MappingProxyType
from typing import Any

from starlette.requests import HTTPConnection

from app.core.config import get_settings
from app.core.roles import ADMIN, has_rank

_MAX_KEYS = 50_000
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
PROPOSAL_WINDOW_SECONDS = 3600
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


class SlidingWindow:
    def __init__(self) -> None:
        self._hits: OrderedDict[str, deque[float]] = OrderedDict()
        self._lock = threading.Lock()

    def attempt(
        self, key: str, limit: int, window_seconds: float, now: float | None = None
    ) -> tuple[bool, float]:
        moment = time.monotonic() if now is None else now
        with self._lock:
            hits = self._hits.get(key)
            if hits is None:
                hits = deque()
                self._hits[key] = hits
            self._hits.move_to_end(key)
            while hits and hits[0] <= moment - window_seconds:
                hits.popleft()
            if len(hits) >= limit:
                return False, max(0.0, hits[0] + window_seconds - moment)
            hits.append(moment)
            while len(self._hits) > _MAX_KEYS:
                self._hits.popitem(last=False)
            return True, 0.0

    def take(
        self, key: str, wanted: int, limit: int, window_seconds: float, now: float | None = None
    ) -> tuple[int, float]:
        moment = time.monotonic() if now is None else now
        with self._lock:
            hits = self._hits.setdefault(key, deque())
            self._hits.move_to_end(key)
            while hits and hits[0] <= moment - window_seconds:
                hits.popleft()
            granted = max(0, min(wanted, limit - len(hits)))
            hits.extend([moment] * granted)
            while len(self._hits) > _MAX_KEYS:
                self._hits.popitem(last=False)
            if granted == wanted or not hits:
                return granted, 0.0
            return granted, max(0.0, hits[0] + window_seconds - moment)

    def refund(self, key: str) -> None:
        with self._lock:
            hits = self._hits.get(key)
            if hits:
                hits.pop()

    def clear(self) -> None:
        with self._lock:
            self._hits.clear()


_windows = SlidingWindow()

WEB_PROXY_SECRET_HEADER = "x-web-proxy-secret"
VIEWER_ADDRESS_HEADER = "x-viewer-address"


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
    key = get_settings().jwt_secret.encode("utf-8")
    return hmac.new(key, f"ip:{address}".encode(), hashlib.sha256).hexdigest()[:32]


def sign_in_attempt_by_ip(connection: HTTPConnection) -> tuple[bool, float]:
    settings = get_settings()
    return _windows.attempt(
        f"ip:{client_ip(connection)}", settings.sign_in_attempts_per_ip, settings.sign_in_window_seconds
    )


def sign_in_attempt_by_account(account_key: str) -> tuple[bool, float]:
    settings = get_settings()
    return _windows.attempt(
        f"acct:{account_key}", settings.sign_in_attempts_per_account, settings.sign_in_window_seconds
    )


def refund_account(account_key: str) -> None:
    _windows.refund(f"acct:{account_key}")


def refund_ip(connection: HTTPConnection) -> None:
    _windows.refund(f"ip:{client_ip(connection)}")


def forgot_password_attempt(connection: HTTPConnection) -> tuple[bool, float]:
    return _windows.attempt(f"forgot:{client_ip(connection)}", 5, 3600)


def code_attempt(user_id: str) -> tuple[bool, float]:
    return _windows.attempt(f"code:{user_id}", 10, 900)


def refund_code(user_id: str) -> None:
    _windows.refund(f"code:{user_id}")


def ask_attempt(user_id: str) -> tuple[bool, float]:
    return _windows.attempt(f"ask:{user_id}", 30, 600)


def term_attempt(user_id: str) -> tuple[bool, float]:
    return _windows.attempt(f"term:{user_id}", 60, 600)


def listen_attempt(user_id: str) -> tuple[bool, float]:
    return _windows.attempt(f"listen:{user_id}", 30, 600)


def film_score_attempt(user_id: str) -> tuple[bool, float]:
    return _windows.attempt(f"film-score:{user_id}", 10, 600)


def voice_session_attempt(user_id: str) -> tuple[bool, float]:
    return _windows.attempt(f"voice:{user_id}", 10, 600)


def voice_turn_attempt(user_id: str) -> tuple[bool, float]:
    return _windows.attempt(f"voice-turn:{user_id}", 40, 600)


def voice_speech_attempt(user_id: str) -> tuple[bool, float]:
    return _windows.attempt(f"voice-speech:{user_id}", 60, 600)


def mcp_connection_attempt(connection_key: str) -> tuple[bool, float]:
    return _windows.attempt(
        f"mcp-connection:{connection_key}", MCP_CALLS_PER_CONNECTION_WINDOW, MCP_CONNECTION_WINDOW_SECONDS
    )


def client_registration_attempt(connection: HTTPConnection) -> tuple[bool, float]:
    return _windows.attempt(
        f"oauth-register:{client_ip(connection)}",
        CLIENT_REGISTRATIONS_PER_WINDOW,
        CLIENT_REGISTRATION_WINDOW_SECONDS,
    )


def proposal_attempt(kind: str, user: Any) -> tuple[bool, float]:
    if has_rank(user, ADMIN):
        return True, 0.0
    return _windows.attempt(f"propose-{kind}:{user.id}", PROPOSAL_LIMITS[kind], PROPOSAL_WINDOW_SECONDS)


def proposal_slots(kind: str, user: Any, wanted: int, *, limit: int | None = None) -> tuple[int, float]:
    if has_rank(user, ADMIN):
        return wanted, 0.0
    allowed = PROPOSAL_LIMITS[kind] if limit is None else limit
    return _windows.take(f"propose-{kind}:{user.id}", wanted, allowed, PROPOSAL_WINDOW_SECONDS)


def public_read_attempt(connection: HTTPConnection) -> tuple[bool, float]:
    return _reading_attempt(
        connection,
        prefix="public-read",
        per_address=PUBLIC_READS_PER_WINDOW,
        server_key=SERVER_READ_KEY,
        per_server=SERVER_READS_PER_WINDOW,
    )


def public_asset_attempt(connection: HTTPConnection) -> tuple[bool, float]:
    return _reading_attempt(
        connection,
        prefix="public-asset",
        per_address=PUBLIC_ASSET_READS_PER_WINDOW,
        server_key=SERVER_ASSET_READ_KEY,
        per_server=SERVER_ASSET_READS_PER_WINDOW,
    )


def _reading_attempt(
    connection: HTTPConnection, *, prefix: str, per_address: int, server_key: str, per_server: int
) -> tuple[bool, float]:
    if is_web_server_read(connection):
        return _windows.attempt(server_key, per_server, PUBLIC_READ_WINDOW_SECONDS)
    return _windows.attempt(f"{prefix}:{client_ip(connection)}", per_address, PUBLIC_READ_WINDOW_SECONDS)


def retry_after_value(wait_seconds: float) -> str:
    return str(max(1, int(wait_seconds + 0.999)))


def reset_all() -> None:
    _windows.clear()
