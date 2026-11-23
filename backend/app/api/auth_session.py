import uuid
from datetime import UTC, datetime
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.roles import ADMIN, MASTER_ADMIN, STUDENT, has_rank, is_known_role, role_value
from app.core.security import create_access_token
from app.models import User
from app.schemas.auth import OidcCodeFields
from app.services import access_roster, oidc_sign_in, reader_profiles
from app.services.object_store import media_bucket
from app.services.users import serialize_user

__all__ = [
    "ACCESS_NOT_RECORDED_DETAIL",
    "ACCESS_PENDING_DETAIL",
    "ACCESS_REJECTED_DETAIL",
    "ACCESS_STATUS_HEADER",
    "ACCESS_SUSPENDED_DETAIL",
    "SAME_PASSWORD_DETAIL",
    "SESSION_TOKEN_HEADER",
    "SIGN_IN_HINT_HEADER",
    "THROTTLED_DETAIL",
    "TWO_FACTOR_REQUIRED_HEADER",
    "access_headers",
    "adopt_admitted_role",
    "assert_access_admits",
    "code_grant",
    "find_user",
    "open_session",
    "reload_user",
    "role_for_email",
    "session_token",
]

ACCESS_STATUS_HEADER = "X-Access-Status"
SESSION_TOKEN_HEADER = "X-Session-Token"
SIGN_IN_HINT_HEADER = "X-Sign-In-Hint"
TWO_FACTOR_REQUIRED_HEADER = "X-Two-Factor-Required"

ACCESS_PENDING_DETAIL = "Your access request is waiting for an administrator to approve it."
ACCESS_REJECTED_DETAIL = (
    "Your access request was not approved. Contact the administrator if this is a mistake."
)
ACCESS_SUSPENDED_DETAIL = "Your access has been suspended. Contact the administrator."
ACCESS_NOT_RECORDED_DETAIL = "Access requests are closed for now. Contact the administrator directly."
THROTTLED_DETAIL = "Too many sign-in attempts. Wait a few minutes and try again."
SAME_PASSWORD_DETAIL = "Choose a password different from the one you have now."


def access_headers(access_status: str) -> dict[str, str]:
    return {ACCESS_STATUS_HEADER: access_status}


def role_for_email(email: str) -> str:
    settings = get_settings()
    if email.strip().lower() == settings.master_admin_email.strip().lower():
        return MASTER_ADMIN
    role = settings.default_signup_role
    return role if is_known_role(role) and not has_rank(role, ADMIN) else STUDENT


async def assert_access_admits(session: AsyncSession, email: str, *, is_master: bool) -> Any:
    if is_master:
        return None
    row = await access_roster.access_row(session, email)
    if access_roster.admits(row):
        return row
    outcome = await access_roster.record_refused_attempt(session, email, row)
    if outcome == access_roster.REJECTED:
        raise HTTPException(status.HTTP_403_FORBIDDEN, ACCESS_REJECTED_DETAIL, access_headers(outcome))
    if outcome == access_roster.SUSPENDED:
        raise HTTPException(status.HTTP_403_FORBIDDEN, ACCESS_SUSPENDED_DETAIL, access_headers(outcome))
    if outcome == access_roster.NOT_RECORDED:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, ACCESS_NOT_RECORDED_DETAIL, access_headers(outcome)
        )
    raise HTTPException(
        status.HTTP_403_FORBIDDEN, ACCESS_PENDING_DETAIL, access_headers(access_roster.PENDING)
    )


def session_token(user: User) -> str:
    return create_access_token(
        str(user.id),
        token_version=user.tokenVersion,
        extra_claims={"email": user.email, "role": role_value(user)},
    )


async def reload_user(session: AsyncSession, user_id: uuid.UUID) -> User:
    user = (
        await session.execute(
            select(User).where(User.id == user_id).execution_options(populate_existing=True)
        )
    ).scalar_one_or_none()
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "This account no longer exists. Sign in again.")
    return user


async def open_session(session: AsyncSession, user: User, access: Any) -> dict[str, Any]:
    now = datetime.now(UTC)
    await access_roster.mark_access_seen(session, access)
    user.lastLoginAt = now
    if user.firstLoginAt is None:
        user.firstLoginAt = now
    await session.commit()
    user = await reload_user(session, user.id)
    return {
        "accessToken": session_token(user),
        "tokenType": "bearer",
        "user": serialize_user(user, access_status=access_roster.status_of(access) or "ACTIVE"),
    }


async def find_user(session: AsyncSession, email: str) -> User | None:
    return (
        await session.execute(select(User).where(func.lower(User.email) == email.strip().lower()))
    ).scalar_one_or_none()


async def adopt_admitted_role(session: AsyncSession, account: User, row: Any) -> None:
    admitted = access_roster.role_of(row) if access_roster.admits(row) else None
    if not admitted or role_value(account) in (admitted, MASTER_ADMIN):
        return
    await reader_profiles.apply_role_change(session, account, admitted, objects=media_bucket())
    account.role = admitted
    account.tokenVersion += 1


def code_grant(payload: OidcCodeFields) -> oidc_sign_in.CodeGrant:
    return oidc_sign_in.CodeGrant(
        provider=payload.oidcProvider or "",
        code=payload.oidcCode or "",
        code_verifier=payload.oidcCodeVerifier or "",
        redirect_uri=payload.oidcRedirectUri or "",
        raw_nonce=payload.oidcNonce or "",
    )
