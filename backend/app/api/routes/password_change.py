import asyncio
import logging
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.routes.auth import (
    SAME_PASSWORD_DETAIL,
    SESSION_TOKEN_HEADER,
    THROTTLED_DETAIL,
    TWO_FACTOR_REQUIRED_HEADER,
    code_grant,
    reload_user,
    session_token,
)
from app.core.db import get_session
from app.core.deps import get_current_user, get_current_user_any_step
from app.core.rate_limit import refund_account, sign_in_attempt_by_account
from app.core.security import hash_password, verify_password
from app.core.throttle_refusal import refuse_when_throttled
from app.models import User
from app.schemas.auth import ChangePasswordRequest
from app.services import (
    audit,
    auth_nonces,
    credential_links,
    mailer,
    oidc_sign_in,
    provider_proof,
    two_factor,
)

router = APIRouter(prefix="/auth", tags=["auth"])
logger = logging.getLogger(__name__)

CONFIRM_PROVIDER_HEADER = "X-Confirm-Provider"
CURRENT_PASSWORD_WRONG_DETAIL = "Current password is incorrect"
HAS_PASSWORD_DETAIL = "This account already has a password. Change it with the current one."
SET_PASSWORD_LINK_DETAIL = "Use a set-password link to add a password to this account."
CONFIRM_FIRST_DETAIL = "To add a password, first confirm it's you by signing in with {label} again."
CONFIRM_AGAIN_DETAIL = (
    "That {label} sign-in didn't match this account or has expired. "
    "Sign in with {label} again to confirm it's you."
)
CONFIRM_UNAVAILABLE_DETAIL = (
    "{label} sign-in isn't available right now. Ask an administrator for a set-password link."
)
TWO_FACTOR_CODE_DETAIL = "Enter the code from your authenticator app."


def _confirm_refusal(provider: str, detail: str) -> HTTPException:
    label = oidc_sign_in.label_of(provider)
    return HTTPException(
        status.HTTP_400_BAD_REQUEST, detail.format(label=label), {CONFIRM_PROVIDER_HEADER: provider}
    )


def _provider_proof(payload: ChangePasswordRequest) -> provider_proof.ProviderProof:
    return provider_proof.ProviderProof(
        google_id_token=payload.googleIdToken or None,
        grant=code_grant(payload) if payload.has_oidc_code else None,
    )


@router.post("/first-password/nonce")
async def first_password_nonce(
    user: User = Depends(get_current_user), session: AsyncSession = Depends(get_session)
) -> dict[str, Any]:
    if user.passwordHash is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, HAS_PASSWORD_DETAIL)
    provider = provider_proof.account_provider(user)
    if provider is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, SET_PASSWORD_LINK_DETAIL)
    client_id = provider_proof.client_id_for(provider)
    if client_id is None:
        label = oidc_sign_in.label_of(provider)
        raise HTTPException(status.HTTP_404_NOT_FOUND, CONFIRM_UNAVAILABLE_DETAIL.format(label=label))
    nonce, expires = await auth_nonces.issue_nonce(
        session, purpose=provider_proof.NONCE_PURPOSE, user_id=user.id
    )
    return {"nonce": nonce, "expiresAt": expires.isoformat(), "provider": provider, "clientId": client_id}


async def _confirm_first_password(session: AsyncSession, user: User, payload: ChangePasswordRequest) -> str:
    expected = provider_proof.account_provider(user)
    if expected is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, SET_PASSWORD_LINK_DETAIL)
    proof = _provider_proof(payload)
    if proof.provider is None:
        raise _confirm_refusal(expected, CONFIRM_FIRST_DETAIL)
    if user.twoFactorEnabled and not payload.twoFactorCode:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, TWO_FACTOR_CODE_DETAIL, {TWO_FACTOR_REQUIRED_HEADER: "1"}
        )
    try:
        await provider_proof.require_fresh_proof(session, user, proof)
    except provider_proof.ProofRefused as exc:
        logger.info("first-password proof refused", extra={"provider": exc.provider, "reason": exc.reason})
        raise _confirm_refusal(expected, CONFIRM_AGAIN_DETAIL) from exc
    if user.twoFactorEnabled and not await two_factor.step_up(session, user, payload.twoFactorCode):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, two_factor.WRONG_CODE_DETAIL, {TWO_FACTOR_REQUIRED_HEADER: "1"}
        )
    return expected


async def _confirm_current_password(user: User, payload: ChangePasswordRequest) -> None:
    if not await asyncio.to_thread(verify_password, payload.currentPassword, user.passwordHash):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, CURRENT_PASSWORD_WRONG_DETAIL)
    if await asyncio.to_thread(verify_password, payload.newPassword, user.passwordHash):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, SAME_PASSWORD_DETAIL)


async def _store_new_password(
    session: AsyncSession, user: User, new_password: str, *, proved_by: str | None
) -> User:
    user = await reload_user(session, user.id)
    user.passwordHash = await asyncio.to_thread(hash_password, new_password)
    user.passwordSetAt = datetime.now(UTC)
    user.mustChangePassword = False
    user.passwordIssuerKnown = False
    user.tokenVersion += 1
    await credential_links.revoke_outstanding(session, user.id)
    await audit.record(
        session,
        action="auth.password_changed",
        actor=user,
        target_type="User",
        target_id=user.id,
        detail={"firstPassword": True, "provider": proved_by} if proved_by else None,
    )
    await session.commit()
    return await reload_user(session, user.id)


@router.post("/change-password")
async def change_password(
    payload: ChangePasswordRequest,
    response: Response,
    user: User = Depends(get_current_user_any_step),
    session: AsyncSession = Depends(get_session),
) -> dict[str, bool]:
    refuse_when_throttled(sign_in_attempt_by_account(str(user.id)), THROTTLED_DETAIL)
    proved_by = None
    if user.passwordHash is None:
        proved_by = await _confirm_first_password(session, user, payload)
    else:
        await _confirm_current_password(user, payload)
    refund_account(str(user.id))
    user = await _store_new_password(session, user, payload.newPassword, proved_by=proved_by)
    response.headers[SESSION_TOKEN_HEADER] = session_token(user)
    await mailer.send(mailer.password_changed_mail(user.email))
    return {"ok": True}
