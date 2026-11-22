from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Request, status
from fastapi.responses import JSONResponse, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.oauth_hosts import OAUTH_ROUTE, REGISTER_ROUTE, REVOKE_ROUTE, TOKEN_ROUTE, configured_endpoints
from app.api.oauth_wire import NO_STORE, form_fields, oauth_error_response, registration_from
from app.api.routes.mcp import mcp_enabled
from app.api.routes.oauth_consent import router as consent_router
from app.core.db import get_session
from app.core.rate_limit import client_registration_attempt
from app.core.throttle_refusal import refuse_when_throttled
from app.research.oauth_rules import OAuthError
from app.services import oauth_clients, oauth_tokens

router = APIRouter(prefix=OAUTH_ROUTE, tags=["oauth"])

REGISTRATIONS_SPENT = "Many clients were registered from this address in the last hour. Try again later."


@router.post(REGISTER_ROUTE, dependencies=[Depends(mcp_enabled)])
async def register_client(request: Request, session: AsyncSession = Depends(get_session)) -> Response:
    refuse_when_throttled(client_registration_attempt(request), REGISTRATIONS_SPENT)
    try:
        registration = await registration_from(request)
        registered = await oauth_clients.register_client(session, registration, now=_now())
    except OAuthError as refused:
        return oauth_error_response(refused)
    await session.commit()
    return JSONResponse(
        registered.model_dump(exclude_none=True), status_code=status.HTTP_201_CREATED, headers=NO_STORE
    )


@router.post(TOKEN_ROUTE, dependencies=[Depends(mcp_enabled)])
async def issue_tokens(request: Request, session: AsyncSession = Depends(get_session)) -> Response:
    endpoints = configured_endpoints()
    try:
        fields = await form_fields(request)
        reply = await oauth_tokens.grant_tokens(session, fields, resource=endpoints.resource, now=_now())
    except OAuthError as refused:
        await session.commit()
        return oauth_error_response(refused)
    await session.commit()
    return JSONResponse(reply.model_dump(), headers=NO_STORE)


@router.post(REVOKE_ROUTE, dependencies=[Depends(mcp_enabled)])
async def revoke_token(request: Request, session: AsyncSession = Depends(get_session)) -> Response:
    try:
        fields = await form_fields(request)
        await oauth_tokens.revoke_token(session, fields, now=_now())
    except OAuthError as refused:
        await session.rollback()
        return oauth_error_response(refused)
    await session.commit()
    return Response(status_code=status.HTTP_200_OK, headers=NO_STORE)


def _now() -> datetime:
    return datetime.now(UTC)


router.include_router(consent_router)
