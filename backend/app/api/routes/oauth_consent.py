from __future__ import annotations

import uuid
from collections.abc import Awaitable
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.oauth_hosts import configured_endpoints, endpoints_or_none
from app.api.routes.mcp import mcp_enabled
from app.core.config import get_settings
from app.core.db import get_session
from app.core.deps import get_current_user
from app.core.errors import InvalidInput
from app.models import User
from app.research.oauth_contract import (
    AuthorizationDecline,
    AuthorizationPrompt,
    AuthorizationRedirect,
    AuthorizationRequest,
    ConnectionList,
    Consent,
    TermsOfUse,
)
from app.services import oauth_connections, oauth_consent

router = APIRouter()

NO_CONNECTION = "You have no connected app with that id."


@router.get("/terms")
async def mcp_terms() -> TermsOfUse:
    return oauth_consent.terms_of_use()


@router.get("/authorize/request")
async def review_authorization(
    request: Annotated[AuthorizationRequest, Query()],
    user: User = Depends(get_current_user),
    _: None = Depends(mcp_enabled),
    session: AsyncSession = Depends(get_session),
) -> AuthorizationPrompt | AuthorizationRedirect:
    return await _answer(
        session, oauth_consent.review(session, user, request, endpoints=configured_endpoints())
    )


@router.post("/authorize/approve")
async def approve_authorization(
    consent: Consent,
    user: User = Depends(get_current_user),
    _: None = Depends(mcp_enabled),
    session: AsyncSession = Depends(get_session),
) -> AuthorizationRedirect:
    endpoints = configured_endpoints()
    return await _answer(
        session, oauth_consent.approve(session, user, consent, endpoints=endpoints, now=_now())
    )


@router.post("/authorize/deny")
async def deny_authorization(
    decline: AuthorizationDecline,
    _user: User = Depends(get_current_user),
    _: None = Depends(mcp_enabled),
    session: AsyncSession = Depends(get_session),
) -> AuthorizationRedirect:
    return await _answer(
        session, oauth_consent.decline(session, decline.request, endpoints=configured_endpoints())
    )


@router.get("/connections")
async def connected_apps(
    user: User = Depends(get_current_user), session: AsyncSession = Depends(get_session)
) -> ConnectionList:
    endpoints = endpoints_or_none() if get_settings().mcp_server_enabled else None
    return ConnectionList(
        server_url=endpoints.resource if endpoints else None,
        connections=await oauth_connections.connections(session, user, now=_now()),
    )


@router.delete("/connections/{connection_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_connection(
    connection_id: uuid.UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> Response:
    if not await oauth_connections.revoke_connection(session, user, connection_id, now=_now()):
        await session.rollback()
        raise HTTPException(status.HTTP_404_NOT_FOUND, NO_CONNECTION)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


def _now() -> datetime:
    return datetime.now(UTC)


async def _answer[T](session: AsyncSession, change: Awaitable[T]) -> T:
    try:
        result = await change
    except oauth_consent.UntrustedRequest as untrusted:
        await session.rollback()
        raise HTTPException(untrusted.status, str(untrusted)) from untrusted
    except oauth_consent.TermsChanged as changed:
        await session.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, str(changed)) from changed
    except InvalidInput as invalid:
        await session.rollback()
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(invalid)) from invalid
    await session.commit()
    return result
