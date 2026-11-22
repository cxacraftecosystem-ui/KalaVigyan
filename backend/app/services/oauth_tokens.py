from __future__ import annotations

import secrets
import uuid
from collections.abc import Mapping
from datetime import datetime, timedelta

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import token_matches_user
from app.core.security import TOKEN_VERSION_CLAIM
from app.models import OAuthClient, OAuthCode, OAuthGrant, OAuthToken, User
from app.research.oauth_authorization import same_resource
from app.research.oauth_client_documents import named_client_id
from app.research.oauth_contract import TokenReply
from app.research.oauth_metadata import AUTHORIZATION_CODE, REFRESH_TOKEN
from app.research.oauth_rules import (
    ACCESS_TOKEN_PREFIX,
    ACCESS_TOKEN_SECONDS,
    CODE_PREFIX,
    INVALID_CLIENT,
    INVALID_GRANT,
    INVALID_REQUEST,
    INVALID_SCOPE,
    INVALID_TARGET,
    REFRESH_TOKEN_PREFIX,
    REFRESH_TOKEN_SECONDS,
    SECRET_MAX_CHARS,
    UNSUPPORTED_GRANT_TYPE,
    OAuthError,
    joined_scopes,
    pkce_matches,
    requested_scopes,
)
from app.services.credential_links import token_hash

from .oauth_clients import find_client

__all__ = [
    "ACCESS",
    "REFRESH",
    "grant_matches_user",
    "grant_tokens",
    "new_secret",
    "revoke_grant",
    "revoke_token",
    "sessions_live_since",
    "stored_secret",
]

ACCESS = "ACCESS"
REFRESH = "REFRESH"
UNKNOWN_CODE = "The code is unknown, expired or spent; start the sign-in again."
UNKNOWN_REFRESH = "The refresh token is unknown, expired or revoked; sign in again."
REUSED = "This was already used once, so the connection it made is revoked; sign in again."


def new_secret(prefix: str) -> str:
    return prefix + secrets.token_urlsafe(32)


def stored_secret(raw: str | None, prefix: str) -> str | None:
    if not raw or not raw.startswith(prefix) or len(raw) > SECRET_MAX_CHARS:
        return None
    return token_hash(raw)


def grant_matches_user(grant: OAuthGrant, user: User | None) -> bool:
    claims = {TOKEN_VERSION_CLAIM: grant.userTokenVersion, "iat": grant.createdAt.timestamp()}
    return user is not None and token_matches_user(claims, user)


def sessions_live_since(user: User | None, moment: datetime) -> bool:
    if user is None:
        return False
    return token_matches_user(
        {TOKEN_VERSION_CLAIM: int(user.tokenVersion or 0), "iat": moment.timestamp()}, user
    )


async def grant_tokens(
    session: AsyncSession, fields: Mapping[str, str], *, resource: str, now: datetime
) -> TokenReply:
    if fields.get("client_secret"):
        raise OAuthError(INVALID_CLIENT, "KalaVigyan clients are public and hold no secret", status=401)
    client = await find_client(session, named_client_id(fields))
    if client is None:
        raise OAuthError(INVALID_CLIENT, "client_id is not registered; register the client again", status=401)
    if not same_resource(fields.get("resource"), resource):
        raise OAuthError(INVALID_TARGET, f"tokens are issued for {resource} only")
    kind = fields.get("grant_type")
    if kind == AUTHORIZATION_CODE:
        return await _exchange_code(session, client, fields, now=now)
    if kind == REFRESH_TOKEN:
        return await _refresh(session, client, fields, now=now)
    if kind is None:
        raise OAuthError(INVALID_REQUEST, "grant_type is missing")
    raise OAuthError(UNSUPPORTED_GRANT_TYPE, "grant_type is authorization_code or refresh_token")


async def revoke_token(session: AsyncSession, fields: Mapping[str, str], *, now: datetime) -> None:
    client = await find_client(session, named_client_id(fields))
    if client is None:
        raise OAuthError(INVALID_CLIENT, "client_id is not registered", status=401)
    raw = _required(fields, "token")
    if len(raw) > SECRET_MAX_CHARS:
        return
    found = (
        await session.execute(
            select(OAuthToken, OAuthGrant)
            .join(OAuthGrant, OAuthGrant.id == OAuthToken.grantId)
            .where(OAuthToken.tokenHash == token_hash(raw))
        )
    ).one_or_none()
    if found is None or found[1].clientId != client.id:
        return
    token, grant = found
    if token.kind == REFRESH:
        await revoke_grant(session, grant.id, now=now)
    elif token.revokedAt is None:
        token.revokedAt = now


async def revoke_grant(session: AsyncSession, grant_id: uuid.UUID, *, now: datetime) -> None:
    await session.execute(
        update(OAuthGrant)
        .where(OAuthGrant.id == grant_id, OAuthGrant.revokedAt.is_(None))
        .values(revokedAt=now)
    )
    await session.execute(
        update(OAuthToken)
        .where(OAuthToken.grantId == grant_id, OAuthToken.revokedAt.is_(None))
        .values(revokedAt=now)
    )


async def _exchange_code(
    session: AsyncSession, client: OAuthClient, fields: Mapping[str, str], *, now: datetime
) -> TokenReply:
    code = await _code(session, _required(fields, "code"), client)
    if code.usedAt is not None:
        if code.grantId is not None:
            await revoke_grant(session, code.grantId, now=now)
        raise OAuthError(INVALID_GRANT, REUSED)
    if code.expiresAt <= now or code.redirectUri != _required(fields, "redirect_uri"):
        raise OAuthError(INVALID_GRANT, UNKNOWN_CODE)
    if not pkce_matches(_required(fields, "code_verifier"), code.codeChallenge):
        raise OAuthError(INVALID_GRANT, "code_verifier does not match the code_challenge")
    if not await _claim(session, OAuthCode, code.id, now):
        raise OAuthError(INVALID_GRANT, UNKNOWN_CODE)
    user = await session.get(User, code.userId)
    if user is None or not sessions_live_since(user, code.createdAt):
        raise OAuthError(INVALID_GRANT, UNKNOWN_CODE)
    grant = await _new_grant(session, code, user, now=now)
    code.grantId = grant.id
    return await _issue(session, grant, tuple(code.scopes), now=now)


async def _refresh(
    session: AsyncSession, client: OAuthClient, fields: Mapping[str, str], *, now: datetime
) -> TokenReply:
    token, grant = await _refresh_token(session, _required(fields, "refresh_token"), client)
    if token.usedAt is not None:
        await revoke_grant(session, grant.id, now=now)
        raise OAuthError(INVALID_GRANT, REUSED)
    if token.revokedAt is not None or grant.revokedAt is not None or token.expiresAt <= now:
        raise OAuthError(INVALID_GRANT, UNKNOWN_REFRESH)
    if not grant_matches_user(grant, await session.get(User, grant.userId)):
        await revoke_grant(session, grant.id, now=now)
        raise OAuthError(INVALID_GRANT, UNKNOWN_REFRESH)
    scopes = _narrowed(fields.get("scope"), tuple(grant.scopes))
    if not await _claim(session, OAuthToken, token.id, now):
        raise OAuthError(INVALID_GRANT, UNKNOWN_REFRESH)
    grant.expiresAt = now + timedelta(seconds=REFRESH_TOKEN_SECONDS)
    return await _issue(session, grant, scopes, now=now)


async def _code(session: AsyncSession, raw: str, client: OAuthClient) -> OAuthCode:
    digest = stored_secret(raw, CODE_PREFIX)
    code = None
    if digest is not None:
        code = (
            await session.execute(select(OAuthCode).where(OAuthCode.codeHash == digest))
        ).scalar_one_or_none()
    if code is None or code.clientId != client.id:
        raise OAuthError(INVALID_GRANT, UNKNOWN_CODE)
    return code


async def _refresh_token(
    session: AsyncSession, raw: str, client: OAuthClient
) -> tuple[OAuthToken, OAuthGrant]:
    digest = stored_secret(raw, REFRESH_TOKEN_PREFIX)
    found = None
    if digest is not None:
        found = (
            await session.execute(
                select(OAuthToken, OAuthGrant)
                .join(OAuthGrant, OAuthGrant.id == OAuthToken.grantId)
                .where(OAuthToken.tokenHash == digest, OAuthToken.kind == REFRESH)
            )
        ).one_or_none()
    if found is None or found[1].clientId != client.id:
        raise OAuthError(INVALID_GRANT, UNKNOWN_REFRESH)
    return found[0], found[1]


async def _claim(
    session: AsyncSession, table: type[OAuthCode] | type[OAuthToken], key: uuid.UUID, now: datetime
) -> bool:
    claimed = await session.execute(
        update(table).where(table.id == key, table.usedAt.is_(None)).values(usedAt=now).returning(table.id)
    )
    return claimed.scalar_one_or_none() is not None


async def _new_grant(session: AsyncSession, code: OAuthCode, user: User, *, now: datetime) -> OAuthGrant:
    earlier = await session.execute(
        select(OAuthGrant.id).where(
            OAuthGrant.clientId == code.clientId, OAuthGrant.userId == user.id, OAuthGrant.revokedAt.is_(None)
        )
    )
    for grant_id in earlier.scalars().all():
        await revoke_grant(session, grant_id, now=now)
    grant = OAuthGrant(
        clientId=code.clientId,
        userId=user.id,
        scopes=list(code.scopes),
        resource=code.resource,
        userTokenVersion=int(user.tokenVersion or 0),
        createdAt=now,
        expiresAt=now + timedelta(seconds=REFRESH_TOKEN_SECONDS),
    )
    session.add(grant)
    await session.flush()
    return grant


async def _issue(
    session: AsyncSession, grant: OAuthGrant, scopes: tuple[str, ...], *, now: datetime
) -> TokenReply:
    access = new_secret(ACCESS_TOKEN_PREFIX)
    refresh = new_secret(REFRESH_TOKEN_PREFIX)
    session.add_all(
        [
            _token_row(grant, ACCESS, access, scopes, now + timedelta(seconds=ACCESS_TOKEN_SECONDS)),
            _token_row(grant, REFRESH, refresh, tuple(grant.scopes), grant.expiresAt),
        ]
    )
    await session.flush()
    return TokenReply(
        access_token=access,
        expires_in=ACCESS_TOKEN_SECONDS,
        refresh_token=refresh,
        scope=joined_scopes(scopes),
    )


def _token_row(
    grant: OAuthGrant, kind: str, raw: str, scopes: tuple[str, ...], expires: datetime
) -> OAuthToken:
    return OAuthToken(
        grantId=grant.id, kind=kind, tokenHash=token_hash(raw), scopes=list(scopes), expiresAt=expires
    )


def _narrowed(asked: str | None, granted: tuple[str, ...]) -> tuple[str, ...]:
    if not asked:
        return granted
    scopes = requested_scopes(asked)
    wider = sorted(set(scopes) - set(granted))
    if wider:
        raise OAuthError(INVALID_SCOPE, f"this connection was not given {', '.join(wider)}")
    return scopes


def _required(fields: Mapping[str, str], name: str) -> str:
    value = fields.get(name)
    if not value:
        raise OAuthError(INVALID_REQUEST, f"{name} is missing")
    return value
