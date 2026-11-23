import asyncio
import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from fastapi import HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth_session import (
    ACCESS_SUSPENDED_DETAIL,
    SIGN_IN_HINT_HEADER,
    THROTTLED_DETAIL,
    access_headers,
    adopt_admitted_role,
    assert_access_admits,
    code_grant,
    find_user,
    reload_user,
    role_for_email,
)
from app.core.config import get_settings
from app.core.deps import is_break_glass_master
from app.core.rate_limit import refund_account, refund_ip, sign_in_attempt_by_account, sign_in_attempt_by_ip
from app.core.roles import MASTER_ADMIN, role_value
from app.core.security import verify_password_or_decoy
from app.core.throttle_refusal import refuse_when_throttled
from app.models import User
from app.schemas.auth import LoginRequest
from app.services import (
    access_roster,
    audit,
    credential_links,
    google_auth,
    oidc_sign_in,
    reader_profiles,
    two_factor,
)
from app.services.object_store import media_bucket

__all__ = [
    "GOOGLE_FAILED_DETAIL",
    "GOOGLE_PROVIDER",
    "GOOGLE_UNAVAILABLE_DETAIL",
    "PROVIDER_UNAVAILABLE_DETAIL",
    "VerifiedMailbox",
    "login_with_google",
    "login_with_oidc",
    "login_with_password",
    "refuse_when_ip_throttled",
    "sign_in_verified_mailbox",
]

logger = logging.getLogger(__name__)

INVALID_CREDENTIALS_DETAIL = "Invalid email or password"
PASSWORD_NOT_SET_HINT = "PASSWORD_NOT_SET"
PASSWORD_NOT_SET_DETAIL = (
    "This account has no password yet. Sign in with {label}, or ask for a set-password link."
)
EMAIL_UNVERIFIED_HINT = "EMAIL_UNVERIFIED"
EMAIL_UNVERIFIED_DETAIL = (
    "Confirm your email address first: open the link we sent, or ask for a new one with Forgot password."
)
PROVIDER_UNAVAILABLE_DETAIL = (
    "{label} sign-in isn't available right now. Sign in with your email and password."
)
PROVIDER_FAILED_DETAIL = "{label} sign-in didn't work. Try again."
PROVIDER_UNVERIFIED_DETAIL = "This {label} account's email address isn't verified."
GOOGLE_PROVIDER = "GOOGLE"
GOOGLE_UNAVAILABLE_DETAIL = PROVIDER_UNAVAILABLE_DETAIL.format(label="Google")
GOOGLE_FAILED_DETAIL = PROVIDER_FAILED_DETAIL.format(label="Google")
GOOGLE_UNVERIFIED_DETAIL = PROVIDER_UNVERIFIED_DETAIL.format(label="Google")


@dataclass(frozen=True)
class VerifiedMailbox:
    email: str
    display_name: str | None
    avatar_url: str | None
    provider: str


async def sign_in_verified_mailbox(session: AsyncSession, mailbox: VerifiedMailbox) -> tuple[User, Any]:
    role = role_for_email(mailbox.email)
    access = await assert_access_admits(session, mailbox.email, is_master=role == MASTER_ADMIN)
    name = _account_name(mailbox, role, access)
    existing = await find_user(session, mailbox.email)
    if existing is not None:
        updated = await _update_verified_account(
            session, existing, mailbox, name=name, role=role, access=access
        )
        return updated, access
    admitted_role = access_roster.role_of(access) if access is not None else None
    created = User(
        email=mailbox.email,
        name=name,
        avatarUrl=mailbox.avatar_url,
        authProvider=mailbox.provider,
        role=MASTER_ADMIN if role == MASTER_ADMIN else (admitted_role or role),
        emailVerifiedAt=datetime.now(UTC),
    )
    session.add(created)
    await session.flush()
    return created, access


async def login_with_google(session: AsyncSession, token: str) -> tuple[User, Any]:
    if not google_auth.google_enabled():
        raise HTTPException(status.HTTP_400_BAD_REQUEST, GOOGLE_UNAVAILABLE_DETAIL)
    try:
        claims = await google_auth.verify_with_nonce(session, token)
    except google_auth.GoogleSignInRefused as exc:
        await session.commit()
        detail = GOOGLE_UNVERIFIED_DETAIL if exc.reason == "email_unverified" else GOOGLE_FAILED_DETAIL
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail) from exc
    await session.commit()
    mailbox = VerifiedMailbox(
        email=str(claims["email"]).strip().lower(),
        display_name=claims.get("name"),
        avatar_url=claims.get("picture"),
        provider=GOOGLE_PROVIDER,
    )
    return await sign_in_verified_mailbox(session, mailbox)


async def refuse_when_ip_throttled(request: Request) -> None:
    refuse_when_throttled(await sign_in_attempt_by_ip(request), THROTTLED_DETAIL)


async def login_with_oidc(session: AsyncSession, payload: LoginRequest, request: Request) -> tuple[User, Any]:
    name = payload.oidcProvider or ""
    label = oidc_sign_in.label_of(name)
    if oidc_sign_in.provider(name) is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, PROVIDER_UNAVAILABLE_DETAIL.format(label=label))
    await refuse_when_ip_throttled(request)
    proved = await _prove_with_provider(session, payload, label)
    await refund_ip(request)
    mailbox = VerifiedMailbox(
        email=proved.email, display_name=proved.name, avatar_url=None, provider=proved.provider
    )
    return await sign_in_verified_mailbox(session, mailbox)


async def login_with_password(
    session: AsyncSession, payload: LoginRequest, request: Request
) -> tuple[User, Any]:
    email = (payload.email or "").strip().lower()
    user = await find_user(session, email)
    if user is not None and user.passwordHash is None and user.deletedAt is None:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            PASSWORD_NOT_SET_DETAIL.format(label=_sign_in_label(user)),
            {SIGN_IN_HINT_HEADER: PASSWORD_NOT_SET_HINT},
        )
    account_key = str(user.id) if user is not None else f"addr:{email}"
    allowed, retry = await sign_in_attempt_by_ip(request)
    if allowed:
        allowed, retry = await sign_in_attempt_by_account(account_key)
    refuse_when_throttled((allowed, retry), THROTTLED_DETAIL)
    matched = await asyncio.to_thread(
        verify_password_or_decoy, payload.password or "", user.passwordHash if user else None
    )
    if not matched or user is None or user.deletedAt is not None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, INVALID_CREDENTIALS_DETAIL)
    if (
        user.emailVerifiedAt is None
        and not user.passwordIssuerKnown
        and user.firstLoginAt is None
        and not is_break_glass_master(user)
    ):
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            EMAIL_UNVERIFIED_DETAIL,
            {SIGN_IN_HINT_HEADER: EMAIL_UNVERIFIED_HINT},
        )
    await refund_account(account_key)
    await refund_ip(request)
    access = await assert_access_admits(session, user.email, is_master=is_break_glass_master(user))
    return user, access


def _sign_in_label(user: User) -> str:
    provider = str(user.authProvider or "")
    return oidc_sign_in.label_of(provider) if provider in oidc_sign_in.PROVIDERS else "Google"


def _account_name(mailbox: VerifiedMailbox, role: str, access: Any) -> str:
    if access is not None and access.fullName:
        return str(access.fullName)[:200]
    if role == MASTER_ADMIN:
        return get_settings().master_admin_name[:200]
    return str(mailbox.display_name or mailbox.email.split("@")[0])[:200]


async def _clear_unverified_credentials(session: AsyncSession, account: User) -> User:
    if account.emailVerifiedAt is not None or account.passwordIssuerKnown:
        return account
    had_password = account.passwordHash is not None
    had_two_factor = account.twoFactorEnabled or account.twoFactorPendingSecret is not None
    if not (had_password or had_two_factor):
        return account
    account.passwordHash = None
    account.passwordSetAt = None
    account.mustChangePassword = False
    await two_factor.reset_by_administrator(session, account)
    await credential_links.revoke_outstanding(session, account.id)
    await audit.record(
        session,
        action="auth.unverified_credentials_cleared",
        actor=None,
        target_type="User",
        target_id=account.id,
        detail={"password": had_password, "twoFactor": had_two_factor},
    )
    await session.flush()
    return await reload_user(session, account.id)


async def _update_verified_account(
    session: AsyncSession, existing: User, mailbox: VerifiedMailbox, *, name: str, role: str, access: Any
) -> User:
    if existing.deletedAt is not None:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, ACCESS_SUSPENDED_DETAIL, access_headers(access_roster.SUSPENDED)
        )
    existing = await _clear_unverified_credentials(session, existing)
    if existing.emailVerifiedAt is None:
        await adopt_admitted_role(session, existing, access)
    if existing.passwordHash is None:
        existing.name = name
        if str(existing.authProvider) in ("LOCAL", mailbox.provider):
            existing.authProvider = mailbox.provider
    if mailbox.provider == GOOGLE_PROVIDER:
        existing.avatarUrl = mailbox.avatar_url
    existing.emailVerifiedAt = existing.emailVerifiedAt or datetime.now(UTC)
    if role == MASTER_ADMIN and existing.passwordHash is None and role_value(existing) != MASTER_ADMIN:
        await reader_profiles.apply_role_change(session, existing, MASTER_ADMIN, objects=media_bucket())
        existing.role = MASTER_ADMIN
        existing.tokenVersion += 1
    await session.flush()
    return existing


async def _prove_with_provider(
    session: AsyncSession, payload: LoginRequest, label: str
) -> oidc_sign_in.ProvedIdentity:
    name = payload.oidcProvider or ""
    try:
        return await oidc_sign_in.prove_once(session, code_grant(payload), purpose=oidc_sign_in.NONCE_PURPOSE)
    except oidc_sign_in.EmailNotVerified as exc:
        logger.info("oidc sign-in refused", extra={"provider": name, "reason": exc.reason})
        detail = PROVIDER_UNVERIFIED_DETAIL.format(label=label)
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail) from exc
    except oidc_sign_in.SignInRefused as exc:
        logger.info("oidc sign-in refused", extra={"provider": name, "reason": exc.reason})
        detail = PROVIDER_FAILED_DETAIL.format(label=label)
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail) from exc
