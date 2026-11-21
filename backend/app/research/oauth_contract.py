from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime
from types import MappingProxyType
from typing import Any, Literal
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field

from app.core.mcp_scopes import ASK_SCOPE, CONTRIBUTE_SCOPE, MCP_SCOPES, READ_SCOPE, REVIEW_SCOPE

from .base import URL_MAX_CHARS, ContractModel
from .oauth_metadata import AUTHORIZATION_CODE, PUBLIC_CLIENT_AUTH, REFRESH_TOKEN
from .oauth_rules import (
    INVALID_CLIENT_METADATA,
    INVALID_REDIRECT_URI,
    REDIRECT_URIS_MAX,
    OAuthError,
    may_hold,
    redirect_uri_problem,
)

__all__ = [
    "CLIENT_NAME_MAX_CHARS",
    "GRANT_TYPES",
    "RESPONSE_TYPES",
    "SCOPE_TEXT",
    "AuthorizationDecline",
    "AuthorizationPrompt",
    "AuthorizationRedirect",
    "AuthorizationRequest",
    "ClientRegistration",
    "Connection",
    "ConnectionList",
    "Consent",
    "McpScope",
    "RegisteredClient",
    "ScopeChoice",
    "TermsOfUse",
    "TermsStatus",
    "TokenReply",
    "client_host",
    "registered_client",
    "scope_choices",
]

CLIENT_NAME_MAX_CHARS = 120
SOFTWARE_MAX_CHARS = 120
WIRE_MAX_CHARS = 4096
GRANT_TYPES = (AUTHORIZATION_CODE, REFRESH_TOKEN)
RESPONSE_TYPES = ("code",)

McpScope = Literal[*MCP_SCOPES]


@dataclass(frozen=True)
class ScopeText:
    title: str
    description: str
    needs: str


SCOPE_TEXT = MappingProxyType(
    {
        READ_SCOPE: ScopeText(
            "Read",
            "Read crafts, facts with their quotes and sources, sections and components, as anyone "
            "signed out sees them.",
            "",
        ),
        ASK_SCOPE: ScopeText(
            "Ask",
            "Ask questions and receive cited answers in your name.",
            "Asking needs an account that may ask.",
        ),
        CONTRIBUTE_SCOPE: ScopeText(
            "Contribute",
            "Propose facts, sources and components in your name, under the contribution terms. Each "
            "proposal passes the same checks as one made on the site.",
            "Contributing needs a Researcher account or above.",
        ),
        REVIEW_SCOPE: ScopeText(
            "Review",
            "Review proposals in your name.",
            "Reviewing needs a Professor, Admin or Master Admin account.",
        ),
    }
)


class WireModel(BaseModel):
    model_config = ConfigDict(extra="ignore", frozen=True, str_strip_whitespace=True)


class ClientRegistration(WireModel):
    redirect_uris: list[str] = Field(min_length=1, max_length=REDIRECT_URIS_MAX)
    client_name: str | None = Field(default=None, max_length=CLIENT_NAME_MAX_CHARS)
    client_uri: str | None = Field(default=None, max_length=URL_MAX_CHARS)
    grant_types: list[str] | None = Field(default=None, max_length=10)
    response_types: list[str] | None = Field(default=None, max_length=10)
    token_endpoint_auth_method: str | None = Field(default=None, max_length=60)
    software_id: str | None = Field(default=None, max_length=SOFTWARE_MAX_CHARS)
    software_version: str | None = Field(default=None, max_length=SOFTWARE_MAX_CHARS)


class RegisteredClient(BaseModel):
    client_id: str
    client_id_issued_at: int
    client_name: str
    redirect_uris: list[str]
    grant_types: list[str]
    response_types: list[str]
    token_endpoint_auth_method: str
    client_uri: str | None = None


class AuthorizationRequest(WireModel):
    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    client_id: str = Field(min_length=1, max_length=URL_MAX_CHARS)
    redirect_uri: str = Field(min_length=1, max_length=URL_MAX_CHARS)
    response_type: str | None = Field(default=None, max_length=WIRE_MAX_CHARS)
    code_challenge: str | None = Field(default=None, max_length=WIRE_MAX_CHARS)
    code_challenge_method: str | None = Field(default=None, max_length=WIRE_MAX_CHARS)
    state: str | None = Field(default=None, max_length=WIRE_MAX_CHARS)
    scope: str | None = Field(default=None, max_length=WIRE_MAX_CHARS)
    resource: str | None = Field(default=None, max_length=WIRE_MAX_CHARS)


class ScopeChoice(ContractModel):
    scope: McpScope
    title: str
    description: str
    allowed: bool
    needs: str | None


class TermsStatus(ContractModel):
    version: str
    accepted_at: datetime | None


class AuthorizationPrompt(ContractModel):
    kind: Literal["prompt"] = "prompt"
    client_name: str
    client_id_host: str | None = None
    redirect_host: str
    scopes: list[ScopeChoice]
    terms: TermsStatus


class AuthorizationRedirect(ContractModel):
    kind: Literal["redirect"] = "redirect"
    redirect_to: str


class Consent(ContractModel):
    request: AuthorizationRequest
    scopes: list[McpScope] = Field(min_length=1, max_length=len(MCP_SCOPES))
    terms_version: str = Field(min_length=1, max_length=40)


class AuthorizationDecline(ContractModel):
    request: AuthorizationRequest


class TermsOfUse(ContractModel):
    version: str
    title: str
    body: str


class Connection(ContractModel):
    id: uuid.UUID
    client_name: str
    client_host: str
    scopes: list[McpScope]
    connected_at: datetime
    last_used_at: datetime | None


class ConnectionList(ContractModel):
    server_url: str | None
    connections: list[Connection]


class TokenReply(BaseModel):
    access_token: str
    token_type: Literal["Bearer"] = "Bearer"
    expires_in: int
    refresh_token: str
    scope: str


def client_host(redirect_uri: str) -> str:
    parts = urlsplit(redirect_uri)
    if parts.scheme in ("http", "https") and parts.hostname:
        return parts.hostname
    return f"{parts.scheme}:"


def scope_choices(user: Any, asked: tuple[str, ...]) -> list[ScopeChoice]:
    choices = []
    for scope in asked:
        text = SCOPE_TEXT[scope]
        allowed = may_hold(user, scope)
        choices.append(
            ScopeChoice(
                scope=scope,
                title=text.title,
                description=text.description,
                allowed=allowed,
                needs=None if allowed else text.needs,
            )
        )
    return choices


def registered_client(registration: ClientRegistration) -> dict[str, Any]:
    uris = list(dict.fromkeys(registration.redirect_uris))
    for uri in uris:
        problem = redirect_uri_problem(uri)
        if problem is not None:
            raise OAuthError(INVALID_REDIRECT_URI, problem)
    _check_subset("grant_types", registration.grant_types, GRANT_TYPES)
    _check_subset("response_types", registration.response_types, RESPONSE_TYPES)
    if registration.token_endpoint_auth_method not in (None, PUBLIC_CLIENT_AUTH):
        raise OAuthError(
            INVALID_CLIENT_METADATA,
            "KalaVigyan registers public clients only: token_endpoint_auth_method is none, with PKCE",
        )
    if registration.client_uri is not None and not registration.client_uri.startswith("https://"):
        raise OAuthError(INVALID_CLIENT_METADATA, "client_uri is an https URL")
    return {
        "name": registration.client_name or client_host(uris[0]),
        "redirectUris": uris,
        "clientUri": registration.client_uri,
        "softwareId": registration.software_id,
        "softwareVersion": registration.software_version,
    }


def _check_subset(name: str, asked: list[str] | None, offered: tuple[str, ...]) -> None:
    unknown = sorted(set(asked or ()) - set(offered))
    if unknown:
        raise OAuthError(
            INVALID_CLIENT_METADATA, f"{name} may hold only {', '.join(offered)}, not {', '.join(unknown)}"
        )
