from __future__ import annotations

import base64
import binascii
import json
import uuid
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlsplit

from pydantic import Field, ValidationError

from .base import URL_MAX_CHARS, ContractModel, HttpsUrl
from .oauth_contract import CLIENT_NAME_MAX_CHARS, WireModel
from .oauth_metadata import PUBLIC_CLIENT_AUTH
from .oauth_rules import INVALID_CLIENT, REDIRECT_URIS_MAX, OAuthError, redirect_uri_problem

__all__ = [
    "CACHE_CEILING_SECONDS",
    "CACHE_DEFAULT_SECONDS",
    "CACHE_FLOOR_SECONDS",
    "CLIENT_DOCUMENT_ACCEPT",
    "CLIENT_DOCUMENT_CACHE_HEADER",
    "CLIENT_DOCUMENT_FETCH_PATH",
    "CLIENT_DOCUMENT_MAX_BYTES",
    "CLIENT_DOCUMENT_TIMEOUT_SECONDS",
    "JWT_BEARER_ASSERTION",
    "ClientDocumentRequest",
    "MetadataClient",
    "cache_seconds",
    "client_id_problem",
    "is_client_id_url",
    "is_metadata_client_key",
    "metadata_client",
    "metadata_client_key",
    "named_client_id",
]

CLIENT_DOCUMENT_FETCH_PATH = "/fetch-client-document"
CLIENT_DOCUMENT_CACHE_HEADER = "X-Client-Document-Cache-Control"
CLIENT_DOCUMENT_ACCEPT = "application/json"
CLIENT_DOCUMENT_MAX_BYTES = 5 * 1024
CLIENT_DOCUMENT_TIMEOUT_SECONDS = 5.0
CACHE_FLOOR_SECONDS = 60
CACHE_DEFAULT_SECONDS = 10 * 60
CACHE_CEILING_SECONDS = 24 * 60 * 60
HTTPS_PORT = 443
METADATA_KEY_VERSION = 5
SECRET_FIELDS = ("client_secret", "client_secret_expires_at")
JWT_BEARER_ASSERTION = "urn:ietf:params:oauth:client-assertion-type:jwt-bearer"
JWT_PARTS = 3
ASSERTION_MAX_CHARS = 8 * 1024
UNCACHED = frozenset({"no-store", "no-cache"})


class ClientDocumentRequest(ContractModel):
    url: HttpsUrl


class ClientDocument(WireModel):
    client_name: str = Field(min_length=1, max_length=CLIENT_NAME_MAX_CHARS)
    redirect_uris: list[str] = Field(min_length=1, max_length=REDIRECT_URIS_MAX)
    token_endpoint_auth_method: str | None = Field(default=None, max_length=60)
    token_endpoint_auth_methods_supported: list[str] | None = Field(default=None, max_length=10)


@dataclass(frozen=True)
class MetadataClient:
    client_id: str
    name: str
    redirect_uris: tuple[str, ...]

    @property
    def key(self) -> uuid.UUID:
        return metadata_client_key(self.client_id)

    @property
    def host(self) -> str:
        return urlsplit(self.client_id).hostname or self.client_id


def is_client_id_url(client_id: str) -> bool:
    return "://" in client_id


def metadata_client_key(client_id: str) -> uuid.UUID:
    return uuid.uuid5(uuid.NAMESPACE_URL, client_id)


def is_metadata_client_key(key: uuid.UUID) -> bool:
    return key.version == METADATA_KEY_VERSION


def client_id_problem(client_id: str) -> str | None:
    if len(client_id) > URL_MAX_CHARS or any(ch.isspace() for ch in client_id):
        return f"a client_id URL is at most {URL_MAX_CHARS} characters without spaces"
    try:
        parts = urlsplit(client_id)
        port = parts.port
    except ValueError:
        return "the client_id is not a URL KalaVigyan can read"
    if parts.scheme != "https" or not parts.hostname:
        return "a client_id URL is an https address with a host"
    if parts.username is not None or parts.password is not None or "#" in client_id:
        return "a client_id URL carries no user name, password or fragment"
    if port not in (None, HTTPS_PORT):
        return f"a client_id URL is read on port {HTTPS_PORT} only"
    segments = parts.path.split("/")
    if parts.path in ("", "/") or any(segment in (".", "..") for segment in segments):
        return "a client_id URL names its document by a path with no . or .. segments"
    return None


def named_client_id(fields: Mapping[str, str]) -> str | None:
    if fields.get("client_id"):
        return fields["client_id"]
    if fields.get("client_assertion_type") != JWT_BEARER_ASSERTION:
        return None
    claims = _unverified_claims(fields.get("client_assertion") or "")
    subject = claims.get("sub")
    return subject if isinstance(subject, str) and subject and subject == claims.get("iss") else None


def metadata_client(client_id: str, body: bytes) -> MetadataClient:
    raw = _document_object(body)
    if raw.get("client_id") != client_id:
        raise _refused("names another client_id; it must be exactly the address it is served from")
    if any(name in raw for name in SECRET_FIELDS):
        raise _refused("holds a client secret, which a public client never has")
    try:
        document = ClientDocument.model_validate(raw)
    except ValidationError as unfit:
        raise _refused(f"has fields that do not fit: {_wrong_fields(unfit)}") from unfit
    _check_public(document)
    uris = tuple(dict.fromkeys(document.redirect_uris))
    for uri in uris:
        problem = redirect_uri_problem(uri)
        if problem is not None:
            raise _refused(f"lists a redirect URI KalaVigyan will not use: {problem}")
    return MetadataClient(client_id=client_id, name=document.client_name, redirect_uris=uris)


def cache_seconds(cache_control: str | None) -> int:
    directives = _directives(cache_control or "")
    if UNCACHED & directives.keys():
        return CACHE_FLOOR_SECONDS
    max_age = directives.get("max-age", "")
    if not max_age.isdigit():
        return CACHE_DEFAULT_SECONDS
    return min(max(int(max_age), CACHE_FLOOR_SECONDS), CACHE_CEILING_SECONDS)


def _document_object(body: bytes) -> dict[str, Any]:
    try:
        parsed = json.loads(body)
    except ValueError:
        raise _refused("is not JSON") from None
    if not isinstance(parsed, dict):
        raise _refused("is not a JSON object")
    return parsed


def _check_public(document: ClientDocument) -> None:
    if PUBLIC_CLIENT_AUTH not in _sign_in_methods(document):
        raise _refused(
            "cannot sign in as a public client; KalaVigyan signs in public clients only, with PKCE"
        )


def _sign_in_methods(document: ClientDocument) -> tuple[str, ...]:
    if document.token_endpoint_auth_methods_supported is not None:
        return tuple(document.token_endpoint_auth_methods_supported)
    return (document.token_endpoint_auth_method or PUBLIC_CLIENT_AUTH,)


def _unverified_claims(assertion: str) -> dict[str, Any]:
    parts = assertion.split(".")
    if len(parts) != JWT_PARTS or len(assertion) > ASSERTION_MAX_CHARS:
        return {}
    try:
        payload = base64.urlsafe_b64decode(parts[1] + "=" * (-len(parts[1]) % 4))
        claims = json.loads(payload)
    except ValueError, binascii.Error:
        return {}
    return claims if isinstance(claims, dict) else {}


def _directives(header: str) -> dict[str, str]:
    found: dict[str, str] = {}
    for part in header.split(","):
        name, _, value = part.partition("=")
        if name.strip():
            found[name.strip().lower()] = value.strip().strip('"')
    return found


def _wrong_fields(refused: ValidationError) -> str:
    return ", ".join(sorted({str(problem["loc"][0]) for problem in refused.errors() if problem["loc"]}))


def _refused(why: str) -> OAuthError:
    return OAuthError(INVALID_CLIENT, f"The client's metadata document {why}.")
