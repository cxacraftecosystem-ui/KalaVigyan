import asyncio
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth_session import TWO_FACTOR_REQUIRED_HEADER, open_session, reload_user
from app.api.routes.auth_signup import router as signup_router
from app.api.routes.password_links import router as password_links_router
from app.api.sign_in import (
    GOOGLE_FAILED_DETAIL,
    GOOGLE_UNAVAILABLE_DETAIL,
    PROVIDER_UNAVAILABLE_DETAIL,
    login_with_google,
    login_with_oidc,
    login_with_password,
    refuse_when_ip_throttled,
)
from app.core.config import get_settings
from app.core.db import get_session
from app.core.deps import get_current_user, get_current_user_any_step, is_break_glass_master
from app.core.rate_limit import client_ip, ip_hash, refund_ip
from app.core.security import verify_password
from app.core.throttle_refusal import too_many_requests
from app.models import ConsentRecord, User
from app.schemas.auth import ConsentRequest, GoogleLinkRequest, LoginRequest, OidcNonceRequest
from app.services import (
    access_roster,
    audit,
    auth_nonces,
    google_auth,
    mailer,
    oidc_sign_in,
    reader_profiles,
    turnstile,
    two_factor,
)
from app.services.users import serialize_user

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/google/nonce")
async def google_nonce(request: Request, session: AsyncSession = Depends(get_session)) -> dict[str, Any]:
    if not google_auth.google_enabled():
        raise HTTPException(status.HTTP_404_NOT_FOUND, GOOGLE_UNAVAILABLE_DETAIL)
    await refuse_when_ip_throttled(request)
    await refund_ip(request)
    nonce, expires = await auth_nonces.issue_nonce(
        session, purpose="GOOGLE_SIGN_IN", ip_hash=ip_hash(client_ip(request))
    )
    return {"nonce": nonce, "expiresAt": expires.isoformat(), "clientId": get_settings().google_client_id}


@router.post("/oidc/nonce")
async def oidc_nonce(
    payload: OidcNonceRequest, request: Request, session: AsyncSession = Depends(get_session)
) -> dict[str, Any]:
    client_id = oidc_sign_in.client_id_if_enabled(payload.provider)
    if client_id is None:
        label = oidc_sign_in.label_of(payload.provider)
        raise HTTPException(status.HTTP_404_NOT_FOUND, PROVIDER_UNAVAILABLE_DETAIL.format(label=label))
    await refuse_when_ip_throttled(request)
    await refund_ip(request)
    nonce, expires = await auth_nonces.issue_nonce(
        session, purpose=oidc_sign_in.NONCE_PURPOSE, ip_hash=ip_hash(client_ip(request))
    )
    return {"nonce": nonce, "expiresAt": expires.isoformat(), "clientId": client_id}


@router.get("/config")
async def auth_config() -> dict[str, Any]:
    microsoft_client_id = oidc_sign_in.client_id_if_enabled(oidc_sign_in.MICROSOFT)
    yahoo_client_id = oidc_sign_in.client_id_if_enabled(oidc_sign_in.YAHOO)
    return {
        "googleEnabled": google_auth.google_enabled(),
        "googleClientId": get_settings().google_client_id if google_auth.google_enabled() else None,
        "microsoftEnabled": microsoft_client_id is not None,
        "microsoftClientId": microsoft_client_id,
        "yahooEnabled": yahoo_client_id is not None,
        "yahooClientId": yahoo_client_id,
        "turnstileRequired": turnstile.turnstile_enabled(),
        "turnstileSiteKey": turnstile.site_key(),
        "mailAvailable": mailer.mail_configured(),
        "signUpOpen": mailer.mail_configured() and not turnstile.required_but_missing(),
    }


@router.post("/login")
async def login(
    payload: LoginRequest, request: Request, session: AsyncSession = Depends(get_session)
) -> dict[str, Any]:
    if payload.googleIdToken:
        user, access = await login_with_google(session, payload.googleIdToken)
    elif payload.has_oidc_code:
        user, access = await login_with_oidc(session, payload, request)
    else:
        user, access = await login_with_password(session, payload, request)
    await session.commit()
    if user.twoFactorEnabled:
        if two_factor.fully_locked(user):
            raise too_many_requests(two_factor.TOO_MANY_ATTEMPTS_DETAIL)
        return {
            "two_factor_required": True,
            "challenge_token": await two_factor.issue_challenge(session, user),
        }
    return await open_session(session, user, access)


@router.post("/logout")
async def logout() -> dict[str, bool]:
    return {"ok": True}


@router.get("/me")
async def me(
    user: User = Depends(get_current_user_any_step), session: AsyncSession = Depends(get_session)
) -> dict[str, Any]:
    row = await access_roster.access_row(session, user.email)
    access = "ACTIVE" if is_break_glass_master(user) else (access_roster.status_of(row) or "ACTIVE")
    body = serialize_user(user, access_status=access)
    body["profileRequired"] = await reader_profiles.profile_required(session, user)
    body["guardianConsentRequired"] = await reader_profiles.guardian_consent_required(session, user)
    return body


@router.post("/consent")
async def record_consent(
    payload: ConsentRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    now = datetime.now(UTC)
    session.add(
        ConsentRecord(userId=user.id, kind=payload.kind, noticeVersion=payload.noticeVersion, acceptedAt=now)
    )
    await session.commit()
    return {"kind": payload.kind, "noticeVersion": payload.noticeVersion, "acceptedAt": now.isoformat()}


@router.post("/google/link-nonce")
async def google_link_nonce(
    user: User = Depends(get_current_user), session: AsyncSession = Depends(get_session)
) -> dict[str, Any]:
    if not google_auth.google_enabled():
        raise HTTPException(status.HTTP_404_NOT_FOUND, GOOGLE_UNAVAILABLE_DETAIL)
    nonce, expires = await auth_nonces.issue_nonce(session, purpose="GOOGLE_LINK", user_id=user.id)
    return {"nonce": nonce, "expiresAt": expires.isoformat(), "clientId": get_settings().google_client_id}


@router.post("/google/link")
async def google_link(
    payload: GoogleLinkRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    fresh = False
    if payload.twoFactorCode and user.twoFactorEnabled:
        fresh = await two_factor.step_up(session, user, payload.twoFactorCode)
    elif payload.password and user.passwordHash:
        fresh = await asyncio.to_thread(verify_password, payload.password, user.passwordHash)
    if not fresh:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            "Confirm it's you with your password or a code first.",
            {TWO_FACTOR_REQUIRED_HEADER: "1"} if user.twoFactorEnabled else None,
        )
    try:
        claims = await google_auth.verify_with_nonce(
            session, payload.googleIdToken, purpose="GOOGLE_LINK", user_id=user.id
        )
    except google_auth.GoogleSignInRefused as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, GOOGLE_FAILED_DETAIL) from exc
    if str(claims["email"]).strip().lower() != user.email.strip().lower():
        raise HTTPException(status.HTTP_409_CONFLICT, "That Google account uses a different email address.")
    user.avatarUrl = claims.get("picture") or user.avatarUrl
    user.emailVerifiedAt = user.emailVerifiedAt or datetime.now(UTC)
    await audit.record(
        session, action="auth.google_linked", actor=user, target_type="User", target_id=user.id
    )
    await session.commit()
    return serialize_user(await reload_user(session, user.id))


router.include_router(signup_router)
router.include_router(password_links_router)
