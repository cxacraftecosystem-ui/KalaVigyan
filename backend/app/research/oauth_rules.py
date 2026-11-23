from __future__ import annotations

import base64
import hashlib
import hmac
import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta
from ipaddress import ip_address
from typing import Any
from urllib.parse import SplitResult, urlencode, urlsplit, urlunsplit

from app.core.errors import AppError
from app.core.mcp_scopes import ASK_SCOPE, CONTRIBUTE_SCOPE, MCP_SCOPES, READ_SCOPE, REVIEW_SCOPE
from app.core.roles import Capability, can

__all__ = [
    "ACCESS_DENIED",
    "ACCESS_TOKEN_PREFIX",
    "ACCESS_TOKEN_SECONDS",
    "CODE_PREFIX",
    "CODE_SECONDS",
    "INVALID_CLIENT",
    "INVALID_CLIENT_METADATA",
    "INVALID_GRANT",
    "INVALID_REDIRECT_URI",
    "INVALID_REQUEST",
    "INVALID_SCOPE",
    "INVALID_TARGET",
    "MCP_TERMS_VERSION",
    "PKCE_METHOD",
    "REDIRECT_URIS_MAX",
    "REFRESH_TOKEN_PREFIX",
    "REFRESH_TOKEN_SECONDS",
    "REVIEW_ACCESS_TOKEN_SECONDS",
    "REVIEW_GRANT_SECONDS",
    "REVIEW_SIGN_IN_SECONDS",
    "SCOPE_MAX_CHARS",
    "SECRET_MAX_CHARS",
    "STATE_MAX_CHARS",
    "TEMPORARILY_UNAVAILABLE",
    "UNSUPPORTED_GRANT_TYPE",
    "UNSUPPORTED_RESPONSE_TYPE",
    "Grantor",
    "OAuthError",
    "access_token_seconds",
    "challenge_is_valid",
    "held_scopes",
    "is_loopback_host",
    "joined_scopes",
    "live_scopes",
    "may_hold",
    "ordered_scopes",
    "pkce_matches",
    "redirect_uri_matches",
    "redirect_uri_problem",
    "redirect_with",
    "requested_scopes",
    "s256_challenge",
    "verifier_is_valid",
]

PKCE_METHOD = "S256"
VERIFIER_PATTERN = re.compile(r"[A-Za-z0-9\-._~]{43,128}")
CHALLENGE_PATTERN = re.compile(r"[A-Za-z0-9_-]{43}")
ACCESS_TOKEN_PREFIX = "kvmcp_at_"
REFRESH_TOKEN_PREFIX = "kvmcp_rt_"
CODE_PREFIX = "kvmcp_ac_"
SECRET_MAX_CHARS = 200
ACCESS_TOKEN_SECONDS = 60 * 60
REFRESH_TOKEN_SECONDS = 30 * 24 * 60 * 60
CODE_SECONDS = 5 * 60
MCP_TERMS_VERSION = "2026-11-19"
STATE_MAX_CHARS = 1024
SCOPE_MAX_CHARS = 200
REDIRECT_URI_MAX_CHARS = 2048
REDIRECT_URIS_MAX = 10
REVIEW_SIGN_IN_SECONDS = 15 * 60
REVIEW_ACCESS_TOKEN_SECONDS = 15 * 60
REVIEW_GRANT_SECONDS = 8 * 60 * 60
CLOCK_SKEW = timedelta(minutes=1)
LOOPBACK_NAMES = frozenset({"localhost"})
REFUSED_SCHEMES = frozenset({"javascript", "data", "file", "vbscript", "about", "blob", "filesystem", "ftp"})

INVALID_REQUEST = "invalid_request"
INVALID_CLIENT = "invalid_client"
INVALID_GRANT = "invalid_grant"
INVALID_SCOPE = "invalid_scope"
INVALID_TARGET = "invalid_target"
ACCESS_DENIED = "access_denied"
UNSUPPORTED_GRANT_TYPE = "unsupported_grant_type"
UNSUPPORTED_RESPONSE_TYPE = "unsupported_response_type"
INVALID_REDIRECT_URI = "invalid_redirect_uri"
INVALID_CLIENT_METADATA = "invalid_client_metadata"
TEMPORARILY_UNAVAILABLE = "temporarily_unavailable"


class OAuthError(AppError):
    def __init__(self, error: str, description: str, *, status: int = 400) -> None:
        super().__init__(description)
        self.error = error
        self.description = description
        self.status = status


def s256_challenge(verifier: str) -> str:
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")


def verifier_is_valid(verifier: str) -> bool:
    return VERIFIER_PATTERN.fullmatch(verifier) is not None


def challenge_is_valid(challenge: str) -> bool:
    return CHALLENGE_PATTERN.fullmatch(challenge) is not None


def pkce_matches(verifier: str, challenge: str) -> bool:
    if not verifier_is_valid(verifier) or not challenge_is_valid(challenge):
        return False
    return hmac.compare_digest(s256_challenge(verifier), challenge)


def is_loopback_host(host: str | None) -> bool:
    if not host:
        return False
    if host.lower() in LOOPBACK_NAMES:
        return True
    try:
        return ip_address(host).is_loopback
    except ValueError:
        return False


def redirect_uri_problem(uri: str) -> str | None:
    if not uri or len(uri) > REDIRECT_URI_MAX_CHARS or any(ch.isspace() for ch in uri):
        return f"a redirect URI is a URL of at most {REDIRECT_URI_MAX_CHARS} characters without spaces"
    parts = _split(uri)
    if parts is None or not parts.scheme:
        return "a redirect URI is an absolute URL"
    if "#" in uri:
        return "a redirect URI has no fragment"
    if parts.username is not None or parts.password is not None:
        return "a redirect URI carries no user name or password"
    scheme = parts.scheme.lower()
    if scheme in REFUSED_SCHEMES:
        return f"a redirect URI may not use the {scheme} scheme"
    if scheme == "https":
        return None if parts.hostname else "an https redirect URI names its host"
    if scheme == "http":
        if is_loopback_host(parts.hostname):
            return None
        return "an http redirect URI must be on the same device (127.0.0.1, [::1] or localhost); use https"
    return None if (parts.netloc or parts.path) else "a redirect URI names where to return"


def redirect_uri_matches(registered: str, presented: str) -> bool:
    if registered == presented:
        return True
    left, right = _split(registered), _split(presented)
    if left is None or right is None or left.scheme != "http" or not is_loopback_host(left.hostname):
        return False
    if right.username is not None or not _port_is_valid(right):
        return False
    return _without_port(left) == _without_port(right)


def redirect_with(uri: str, params: Mapping[str, str | None]) -> str:
    parts = urlsplit(uri)
    added = urlencode([(key, value) for key, value in params.items() if value is not None])
    query = f"{parts.query}&{added}" if parts.query else added
    return urlunsplit((parts.scheme, parts.netloc, parts.path, query, parts.fragment))


ACCEPTED_UNNAMED_SCOPES = frozenset({"offline_access"})


def requested_scopes(scope: str | None) -> tuple[str, ...]:
    if scope is not None and len(scope) > SCOPE_MAX_CHARS:
        raise OAuthError(INVALID_SCOPE, f"scope is at most {SCOPE_MAX_CHARS} characters")
    asked = {READ_SCOPE}
    for name in (scope or "").split(" "):
        if not name or name in ACCEPTED_UNNAMED_SCOPES:
            continue
        if name not in MCP_SCOPES:
            raise OAuthError(
                INVALID_SCOPE, f"KalaVigyan has no scope {name}; the scopes are {joined_scopes(MCP_SCOPES)}"
            )
        asked.add(name)
    return ordered_scopes(asked)


def may_hold(user_or_role: Any, scope: str) -> bool:
    if scope == READ_SCOPE:
        return True
    if scope == ASK_SCOPE:
        return can(user_or_role, Capability.ASK_STANDARD)
    if scope == CONTRIBUTE_SCOPE:
        return can(user_or_role, Capability.PROPOSE_KNOWLEDGE)
    if scope == REVIEW_SCOPE:
        return can(user_or_role, Capability.REVIEW_CONTRIBUTIONS) and _two_step_on(user_or_role)
    return False


@dataclass(frozen=True)
class Grantor:
    user: Any
    signed_in_at: datetime | None
    now: datetime

    def may_grant(self, scope: str) -> bool:
        if not may_hold(self.user, scope):
            return False
        return scope != REVIEW_SCOPE or self.signed_in_recently

    @property
    def signed_in_recently(self) -> bool:
        if self.signed_in_at is None:
            return False
        earliest = self.now - timedelta(seconds=REVIEW_SIGN_IN_SECONDS)
        return earliest <= self.signed_in_at <= self.now + CLOCK_SKEW


def live_scopes(scopes: Iterable[str], *, granted_at: datetime, now: datetime) -> tuple[str, ...]:
    held = set(scopes)
    if now >= granted_at + timedelta(seconds=REVIEW_GRANT_SECONDS):
        held.discard(REVIEW_SCOPE)
    return ordered_scopes(held)


def access_token_seconds(scopes: Iterable[str]) -> int:
    return REVIEW_ACCESS_TOKEN_SECONDS if REVIEW_SCOPE in set(scopes) else ACCESS_TOKEN_SECONDS


def held_scopes(user_or_role: Any, scopes: Iterable[str]) -> tuple[str, ...]:
    return ordered_scopes({scope for scope in scopes if may_hold(user_or_role, scope)})


def joined_scopes(scopes: Iterable[str]) -> str:
    return " ".join(scopes)


def ordered_scopes(scopes: Iterable[str]) -> tuple[str, ...]:
    present = set(scopes)
    return tuple(scope for scope in MCP_SCOPES if scope in present)


def _two_step_on(user_or_role: Any) -> bool:
    return getattr(user_or_role, "twoFactorEnabled", False) is True


def _without_port(parts: SplitResult) -> tuple[str, str | None, str, str, str]:
    return (parts.scheme, parts.hostname, parts.path, parts.query, parts.fragment)


def _port_is_valid(parts: SplitResult) -> bool:
    try:
        port = parts.port
    except ValueError:
        return False
    return port is None or port > 0


def _split(uri: str) -> SplitResult | None:
    try:
        return urlsplit(uri)
    except ValueError:
        return None
