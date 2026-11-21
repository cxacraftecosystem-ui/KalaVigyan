from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.core.mcp_scopes import MCP_SCOPES

from .oauth_rules import PKCE_METHOD

__all__ = [
    "AUTHORIZATION_CODE",
    "PUBLIC_CLIENT_AUTH",
    "REFRESH_TOKEN",
    "RESOURCE_NAME",
    "OAuthEndpoints",
    "authorization_server_metadata",
    "bearer_challenge",
    "protected_resource_metadata",
]

RESOURCE_NAME = "KalaVigyan"
AUTHORIZATION_CODE = "authorization_code"
REFRESH_TOKEN = "refresh_token"
PUBLIC_CLIENT_AUTH = "none"


@dataclass(frozen=True)
class OAuthEndpoints:
    issuer: str
    resource: str
    resource_metadata: str
    authorization: str
    token: str
    registration: str
    revocation: str


def protected_resource_metadata(endpoints: OAuthEndpoints) -> dict[str, Any]:
    return {
        "resource": endpoints.resource,
        "authorization_servers": [endpoints.issuer],
        "scopes_supported": list(MCP_SCOPES),
        "bearer_methods_supported": ["header"],
        "resource_name": RESOURCE_NAME,
    }


def authorization_server_metadata(endpoints: OAuthEndpoints) -> dict[str, Any]:
    return {
        "issuer": endpoints.issuer,
        "authorization_endpoint": endpoints.authorization,
        "token_endpoint": endpoints.token,
        "registration_endpoint": endpoints.registration,
        "revocation_endpoint": endpoints.revocation,
        "scopes_supported": list(MCP_SCOPES),
        "response_types_supported": ["code"],
        "response_modes_supported": ["query"],
        "grant_types_supported": [AUTHORIZATION_CODE, REFRESH_TOKEN],
        "token_endpoint_auth_methods_supported": [PUBLIC_CLIENT_AUTH],
        "revocation_endpoint_auth_methods_supported": [PUBLIC_CLIENT_AUTH],
        "code_challenge_methods_supported": [PKCE_METHOD],
        "authorization_response_iss_parameter_supported": True,
        "client_id_metadata_document_supported": True,
    }


def bearer_challenge(
    endpoints: OAuthEndpoints,
    *,
    error: str | None = None,
    description: str | None = None,
    scope: str | None = None,
) -> str:
    named = (("error", error), ("error_description", description), ("scope", scope))
    parts = [f'{name}="{value}"' for name, value in named if value]
    parts.append(f'resource_metadata="{endpoints.resource_metadata}"')
    return "Bearer " + ", ".join(parts)
