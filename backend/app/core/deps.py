import uuid
from collections.abc import Callable, Coroutine
from typing import Any

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.requests import HTTPConnection

from app.core.config import get_settings
from app.core.db import get_session, release_connection
from app.core.guardian_hold import refuse_until_guardian_consent
from app.core.logging import set_log_user
from app.core.roles import (
    ROLE_LABELS,
    ROLE_RANK,
    Capability,
    assignable_roles,
    can,
    capabilities_of,
    has_rank,
    is_known_role,
    is_master_admin,
    may_assign,
    may_manage_target,
    requires_two_factor,
    role_rank,
    role_value,
)
from app.core.security import TOKEN_VERSION_CLAIM, decode_access_token, session_id_of
from app.core.site_sessions import site_session_live
from app.models import User

bearer_scheme = HTTPBearer(auto_error=False)

SIGN_IN_DETAIL = "Sign in to continue."
SESSION_ENDED_DETAIL = "This session is no longer valid. Sign in again."

PASSWORD_CHANGE_REQUIRED_HEADER = "X-Password-Change-Required"
PASSWORD_CHANGE_REQUIRED_DETAIL = "Choose a new password to continue."

TWO_FACTOR_SETUP_REQUIRED_HEADER = "X-Two-Factor-Setup-Required"
TWO_FACTOR_SETUP_REQUIRED_DETAIL = "Turn on two-step verification to continue."

API_PREFIX = "/api"

PASSWORD_CHANGE_ALLOWED_ROUTES: frozenset[tuple[str, str]] = frozenset(
    {
        ("GET", f"{API_PREFIX}/auth/me"),
        ("GET", f"{API_PREFIX}/me"),
        ("POST", f"{API_PREFIX}/auth/change-password"),
        ("POST", f"{API_PREFIX}/auth/logout"),
    }
)

TWO_FACTOR_SETUP_ALLOWED_ROUTES: frozenset[tuple[str, str]] = PASSWORD_CHANGE_ALLOWED_ROUTES | frozenset(
    {
        ("GET", f"{API_PREFIX}/auth/two-factor"),
        ("POST", f"{API_PREFIX}/auth/two-factor/setup"),
        ("POST", f"{API_PREFIX}/auth/two-factor/setup/cancel"),
        ("POST", f"{API_PREFIX}/auth/two-factor/enable"),
    }
)


def is_configured_master_admin(user: Any) -> bool:
    address = str(getattr(user, "email", "") or "").strip().lower()
    configured = (get_settings().master_admin_email or "").strip().lower()
    return bool(address) and address == configured


def is_break_glass_master(user: Any) -> bool:
    return is_master_admin(user) or is_configured_master_admin(user)


def password_change_pending(user: Any) -> bool:
    if not getattr(user, "mustChangePassword", False):
        return False
    if not getattr(user, "passwordHash", None):
        return False
    return not is_configured_master_admin(user)


def two_factor_setup_pending(user: Any) -> bool:
    return requires_two_factor(user) and not bool(getattr(user, "twoFactorEnabled", False))


def _route(connection: HTTPConnection) -> tuple[str, str]:
    method = str(connection.scope.get("method") or "").upper()
    path = str(connection.scope.get("path") or "")
    root = str(connection.scope.get("root_path") or "")
    if root and path.startswith(root):
        path = path[len(root) :] or "/"
    return method, path.rstrip("/") or "/"


def refuse_pending_steps(user: Any, connection: HTTPConnection) -> None:
    route = _route(connection)
    if password_change_pending(user) and route not in PASSWORD_CHANGE_ALLOWED_ROUTES:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=PASSWORD_CHANGE_REQUIRED_DETAIL,
            headers={PASSWORD_CHANGE_REQUIRED_HEADER: "1"},
        )
    if two_factor_setup_pending(user) and route not in TWO_FACTOR_SETUP_ALLOWED_ROUTES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=TWO_FACTOR_SETUP_REQUIRED_DETAIL,
            headers={TWO_FACTOR_SETUP_REQUIRED_HEADER: "1"},
        )


def token_matches_user(claims: dict[str, Any], user: Any) -> bool:
    if getattr(user, "deletedAt", None) is not None:
        return False
    if int(claims.get(TOKEN_VERSION_CLAIM, -1)) != int(getattr(user, "tokenVersion", 0) or 0):
        return False
    valid_from = getattr(user, "sessionsValidFrom", None)
    if valid_from is not None:
        issued = claims.get("iat")
        if not isinstance(issued, int | float) or issued < valid_from.timestamp():
            return False
    return True


async def user_from_token(session: AsyncSession, token: str) -> User:
    try:
        claims = decode_access_token(token)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc
    try:
        user_id = uuid.UUID(str(claims.get("sub")))
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=SESSION_ENDED_DETAIL) from exc
    user = await session.get(User, user_id)
    if user is None or not token_matches_user(claims, user):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=SESSION_ENDED_DETAIL)
    if not await site_session_live(session, user.id, session_id_of(claims)):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=SESSION_ENDED_DETAIL)
    return user


def _bearer_token(credentials: HTTPAuthorizationCredentials | None) -> str | None:
    if credentials is None or not credentials.credentials:
        return None
    return credentials.credentials


def bearer_claims(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> dict[str, Any] | None:
    token = _bearer_token(credentials)
    if token is None:
        return None
    try:
        return decode_access_token(token)
    except ValueError:
        return None


def current_session_id(claims: dict[str, Any] | None = Depends(bearer_claims)) -> uuid.UUID | None:
    return None if claims is None else session_id_of(claims)


async def _signed_in_user(session: AsyncSession, token: str) -> User:
    user = await user_from_token(session, token)
    await release_connection(session)
    set_log_user(str(user.id))
    return user


async def get_current_user_any_step(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    session: AsyncSession = Depends(get_session),
) -> User:
    token = _bearer_token(credentials)
    if token is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=SIGN_IN_DETAIL)
    return await _signed_in_user(session, token)


async def get_current_user(
    connection: HTTPConnection,
    user: User = Depends(get_current_user_any_step),
    session: AsyncSession = Depends(get_session),
) -> User:
    refuse_pending_steps(user, connection)
    await refuse_until_guardian_consent(session, user, _route(connection))
    return user


async def get_optional_user(
    connection: HTTPConnection,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    session: AsyncSession = Depends(get_session),
) -> User | None:
    token = _bearer_token(credentials)
    if token is None:
        return None
    user = await _signed_in_user(session, token)
    refuse_pending_steps(user, connection)
    await refuse_until_guardian_consent(session, user, _route(connection))
    return user


CAPABILITY_REFUSALS: dict[Capability, str] = {
    Capability.GENERATE_VIDEO: "Video is for researchers and above.",
    Capability.MANAGE_ACCESS: "Managing who may sign in is for professors and admins.",
    Capability.LIST_USERS: "Managing users is for professors and admins.",
    Capability.CHANGE_ROLES: "Only admins can change roles.",
    Capability.DISABLE_USERS: "Only admins can suspend accounts.",
    Capability.MANAGE_KEYS: "Only the master admin can manage keys.",
    Capability.MANAGE_ROUTING: "Only the master admin can change routing.",
    Capability.MANAGE_QUOTAS: "Only the master admin can change quotas.",
    Capability.MANAGE_CEILINGS: "Only the master admin can change spending limits.",
    Capability.VIEW_USAGE: "Only admins can see platform usage.",
    Capability.CONTRIBUTE_TESTIMONY: "Conversations about a craft are for artisans.",
    Capability.REVIEW_TESTIMONY: "Reviewing artisans' contributions is for professors and admins.",
    Capability.CONFIRM_GUARDIAN_CONSENT: "Confirming a guardian's agreement is for professors and admins.",
}


def refusal_for(capability: Capability) -> str:
    return CAPABILITY_REFUSALS.get(capability, "Your role does not allow this.")


def require(capability: Capability) -> Callable[..., Coroutine[Any, Any, User]]:
    async def dependency(user: User = Depends(get_current_user)) -> User:
        if not can(user, capability):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=refusal_for(capability))
        return user

    dependency.__name__ = f"require_{capability.value.lower()}"
    return dependency


MANAGE_TARGET_REFUSAL = "You can't change an account at or above your role."


def refuse_unless_assignable(actor: Any, role: Any) -> None:
    if not is_known_role(role):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=f"Unknown role {role!r}"
        )
    if may_assign(actor, role):
        return
    allowed = ", ".join(ROLE_LABELS[option] for option in assignable_roles(actor)) or "none"
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=f"You can give these roles: {allowed}.")


def refuse_unless_manageable(actor: Any, target: Any) -> None:
    if not may_manage_target(actor, target):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=MANAGE_TARGET_REFUSAL)


async def require_master_admin(user: User = Depends(get_current_user)) -> User:
    if not is_master_admin(user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Master admin access required")
    return user


__all__ = [
    "ROLE_RANK",
    "Capability",
    "bearer_claims",
    "can",
    "capabilities_of",
    "current_session_id",
    "get_current_user",
    "get_current_user_any_step",
    "get_optional_user",
    "has_rank",
    "is_break_glass_master",
    "is_configured_master_admin",
    "refusal_for",
    "refuse_unless_assignable",
    "refuse_unless_manageable",
    "require",
    "require_master_admin",
    "role_rank",
    "role_value",
]
