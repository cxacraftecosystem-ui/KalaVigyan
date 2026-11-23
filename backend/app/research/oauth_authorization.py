from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from app.core.errors import InvalidInput
from app.core.mcp_scopes import READ_SCOPE

from .oauth_contract import AuthorizationRequest
from .oauth_rules import (
    ACCESS_DENIED,
    INVALID_REQUEST,
    INVALID_TARGET,
    PKCE_METHOD,
    STATE_MAX_CHARS,
    UNSUPPORTED_RESPONSE_TYPE,
    Grantor,
    OAuthError,
    challenge_is_valid,
    held_scopes,
    redirect_with,
    requested_scopes,
)

__all__ = [
    "CODE_RESPONSE",
    "CheckedAuthorization",
    "checked_authorization",
    "code_redirect",
    "declined_redirect",
    "error_redirect",
    "granted_scopes",
    "same_resource",
]

CODE_RESPONSE = "code"
DECLINED = "The person declined to connect this app to KalaVigyan."


@dataclass(frozen=True)
class CheckedAuthorization:
    scopes: tuple[str, ...]
    challenge: str
    resource: str


def same_resource(asked: str | None, resource: str) -> bool:
    return asked is None or asked.rstrip("/") == resource.rstrip("/")


def checked_authorization(request: AuthorizationRequest, *, resource: str) -> CheckedAuthorization:
    if request.response_type != CODE_RESPONSE:
        raise OAuthError(UNSUPPORTED_RESPONSE_TYPE, "KalaVigyan answers response_type=code only")
    if request.code_challenge_method != PKCE_METHOD or request.code_challenge is None:
        raise OAuthError(
            INVALID_REQUEST, "PKCE is required: send code_challenge with code_challenge_method=S256"
        )
    if not challenge_is_valid(request.code_challenge):
        raise OAuthError(
            INVALID_REQUEST, "code_challenge is the 43-character base64url SHA-256 of the verifier"
        )
    if request.state is not None and len(request.state) > STATE_MAX_CHARS:
        raise OAuthError(INVALID_REQUEST, f"state is at most {STATE_MAX_CHARS} characters")
    if not same_resource(request.resource, resource):
        raise OAuthError(INVALID_TARGET, f"this server signs agents in for {resource} only")
    return CheckedAuthorization(
        scopes=requested_scopes(request.scope), challenge=request.code_challenge, resource=resource
    )


def granted_scopes(grantor: Grantor, asked: Iterable[str], chosen: Iterable[str]) -> tuple[str, ...]:
    chosen = set(chosen)
    unasked = sorted(chosen - set(asked))
    if unasked:
        raise InvalidInput(f"The app did not ask for {', '.join(unasked)}.")
    refused = sorted(scope for scope in chosen if not grantor.may_grant(scope))
    if refused:
        raise InvalidInput(f"Your account may not give {', '.join(refused)} now.")
    return held_scopes(grantor.user, chosen | {READ_SCOPE})


def code_redirect(request: AuthorizationRequest, code: str, *, issuer: str) -> str:
    return redirect_with(request.redirect_uri, {"code": code, "state": request.state, "iss": issuer})


def error_redirect(request: AuthorizationRequest, refused: OAuthError, *, issuer: str) -> str:
    return redirect_with(
        request.redirect_uri,
        {
            "error": refused.error,
            "error_description": refused.description,
            "state": request.state,
            "iss": issuer,
        },
    )


def declined_redirect(request: AuthorizationRequest, *, issuer: str) -> str:
    return error_redirect(request, OAuthError(ACCESS_DENIED, DECLINED), issuer=issuer)
