from __future__ import annotations

from datetime import datetime, timedelta
from functools import lru_cache
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.models import McpTermsAcceptance, OAuthCode, User
from app.research.oauth_authorization import (
    checked_authorization,
    code_redirect,
    declined_redirect,
    error_redirect,
    granted_scopes,
)
from app.research.oauth_contract import (
    AuthorizationPrompt,
    AuthorizationRedirect,
    AuthorizationRequest,
    Consent,
    TermsOfUse,
    TermsStatus,
    client_host,
    scope_choices,
)
from app.research.oauth_metadata import OAuthEndpoints
from app.research.oauth_rules import (
    CODE_PREFIX,
    CODE_SECONDS,
    INVALID_CLIENT,
    INVALID_REQUEST,
    MCP_TERMS_VERSION,
    OAuthError,
    redirect_uri_matches,
)
from app.services.credential_links import token_hash

from .oauth_clients import AskingClient, asking_client, stored_client_id
from .oauth_tokens import new_secret

__all__ = [
    "TermsChanged",
    "UntrustedRequest",
    "approve",
    "decline",
    "review",
    "terms_accepted_at",
    "terms_of_use",
]

TERMS_PATH = Path(__file__).resolve().parents[1] / "data" / "mcp_terms_of_use.md"
TERMS_TITLE = "MCP terms of use"
UNKNOWN_CLIENT = (
    "This app is not registered with KalaVigyan. Remove the server from the app and add it again."
)
FOREIGN_RETURN = (
    "This app asked to return to an address it did not register or publish, so the sign-in stops here."
)
TERMS_CHANGED = "The terms of use changed while this page was open. Read them again and accept them."


class UntrustedRequest(AppError):
    def __init__(self, message: str, *, error: str = INVALID_CLIENT, status: int = 400) -> None:
        super().__init__(message)
        self.error = error
        self.status = status


class TermsChanged(AppError):
    pass


@lru_cache
def _terms_text() -> str:
    return TERMS_PATH.read_text(encoding="utf-8")


def terms_of_use() -> TermsOfUse:
    return TermsOfUse(version=MCP_TERMS_VERSION, title=TERMS_TITLE, body=_terms_text())


async def terms_accepted_at(session: AsyncSession, user: User) -> datetime | None:
    found = await session.execute(
        select(McpTermsAcceptance.acceptedAt).where(
            McpTermsAcceptance.userId == user.id, McpTermsAcceptance.termsVersion == MCP_TERMS_VERSION
        )
    )
    return found.scalar_one_or_none()


async def review(
    session: AsyncSession, user: User, request: AuthorizationRequest, *, endpoints: OAuthEndpoints
) -> AuthorizationPrompt | AuthorizationRedirect:
    client = await _trusted_client(session, request)
    try:
        checked = checked_authorization(request, resource=endpoints.resource)
    except OAuthError as refused:
        return AuthorizationRedirect(redirect_to=error_redirect(request, refused, issuer=endpoints.issuer))
    return AuthorizationPrompt(
        client_name=client.name,
        client_id_host=client.client_id_host,
        redirect_host=client_host(request.redirect_uri),
        scopes=scope_choices(user, checked.scopes),
        terms=TermsStatus(version=MCP_TERMS_VERSION, accepted_at=await terms_accepted_at(session, user)),
    )


async def approve(
    session: AsyncSession, user: User, consent: Consent, *, endpoints: OAuthEndpoints, now: datetime
) -> AuthorizationRedirect:
    request = consent.request
    client = await _trusted_client(session, request)
    try:
        checked = checked_authorization(request, resource=endpoints.resource)
    except OAuthError as refused:
        return AuthorizationRedirect(redirect_to=error_redirect(request, refused, issuer=endpoints.issuer))
    scopes = granted_scopes(user, checked.scopes, consent.scopes)
    await _accept_terms(session, user, consent.terms_version, now=now)
    client_id = await stored_client_id(session, client, now=now)
    code = new_secret(CODE_PREFIX)
    session.add(
        OAuthCode(
            codeHash=token_hash(code),
            clientId=client_id,
            userId=user.id,
            redirectUri=request.redirect_uri,
            codeChallenge=checked.challenge,
            scopes=list(scopes),
            resource=checked.resource,
            expiresAt=now + timedelta(seconds=CODE_SECONDS),
            createdAt=now,
        )
    )
    await session.flush()
    return AuthorizationRedirect(redirect_to=code_redirect(request, code, issuer=endpoints.issuer))


async def decline(
    session: AsyncSession, request: AuthorizationRequest, *, endpoints: OAuthEndpoints
) -> AuthorizationRedirect:
    await _trusted_client(session, request)
    return AuthorizationRedirect(redirect_to=declined_redirect(request, issuer=endpoints.issuer))


async def _trusted_client(session: AsyncSession, request: AuthorizationRequest) -> AskingClient:
    try:
        client = await asking_client(session, request.client_id)
    except OAuthError as refused:
        raise UntrustedRequest(refused.description, error=refused.error, status=refused.status) from refused
    if client is None:
        raise UntrustedRequest(UNKNOWN_CLIENT)
    if not any(redirect_uri_matches(uri, request.redirect_uri) for uri in client.redirect_uris):
        raise UntrustedRequest(FOREIGN_RETURN, error=INVALID_REQUEST)
    return client


async def _accept_terms(session: AsyncSession, user: User, version: str, *, now: datetime) -> None:
    if version != MCP_TERMS_VERSION:
        raise TermsChanged(TERMS_CHANGED)
    await session.execute(
        insert(McpTermsAcceptance)
        .values(userId=user.id, termsVersion=version, acceptedAt=now)
        .on_conflict_do_nothing(index_elements=["userId", "termsVersion"])
    )
