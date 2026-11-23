import hashlib
import hmac
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
from sqlalchemy import delete, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models import TwoFactorChallenge, User

from .two_factor_attempts import (
    CLEAR_FAILURES,
    SecondFactorLocked,
    aware_utc,
    budget_for,
    check_second_factor,
    fully_locked,
    is_locked,
)
from .two_factor_codes import (
    RECOVERY,
    RECOVERY_CODE_COUNT,
    TOTP,
    canonical_recovery_code,
    code_kind,
    current_totp,
    generate_recovery_codes,
    generate_secret,
    hash_recovery_codes,
    hotp,
    match_totp_step,
    qr_svg,
    time_step,
    totp_uri,
)
from .two_factor_keys import VERSIONED_PREFIX, decrypt_secret, encrypt_secret, verify_key_configuration

__all__ = [
    "ALREADY_ON_DETAIL",
    "CHALLENGE_DEAD_DETAIL",
    "NOT_ON_DETAIL",
    "NO_SETUP_DETAIL",
    "OFF_VALUES",
    "RECOVERY",
    "RECOVERY_CODE_COUNT",
    "REQUIRED_FOR_ROLE_DETAIL",
    "TOO_MANY_ATTEMPTS_DETAIL",
    "TOTP",
    "VERSIONED_PREFIX",
    "WRONG_CODE_DETAIL",
    "Challenge",
    "SecondFactorLocked",
    "TwoFactorError",
    "begin_setup",
    "budget_for",
    "canonical_recovery_code",
    "check_second_factor",
    "clear_pending",
    "close_challenge",
    "code_kind",
    "current_totp",
    "decrypt_secret",
    "disable",
    "enable",
    "encrypt_secret",
    "fully_locked",
    "generate_recovery_codes",
    "generate_secret",
    "hash_recovery_codes",
    "hotp",
    "is_locked",
    "issue_challenge",
    "match_totp_step",
    "pending_is_live",
    "qr_svg",
    "read_challenge",
    "regenerate_recovery_codes",
    "reset_by_administrator",
    "spend_challenge_attempt",
    "status_of",
    "step_up",
    "time_step",
    "totp_uri",
    "verify_key_configuration",
]

CHALLENGE_PURPOSE = "2fa"
CHALLENGE_MINUTES = 5
MAX_CHALLENGE_ATTEMPTS = 5
PENDING_SETUP_MINUTES = 15

_CHALLENGE_CONTEXT = b"kalavigyan-two-factor-challenge-v1"

WRONG_CODE_DETAIL = "That code didn't work. Check your authenticator app and try again."
CHALLENGE_DEAD_DETAIL = "This sign-in has timed out. Sign in again."
ALREADY_ON_DETAIL = "Two-step verification is already on for this account."
NOT_ON_DETAIL = "Two-step verification is not on for this account."
NO_SETUP_DETAIL = "Start the setup again to get a new key."
TOO_MANY_ATTEMPTS_DETAIL = "Too many attempts. Try again later."
REQUIRED_FOR_ROLE_DETAIL = "Two-step verification is required for your role and cannot be turned off."


class TwoFactorError(Exception):
    def __init__(self, kind: str, detail: str) -> None:
        super().__init__(detail)
        self.kind = kind
        self.detail = detail


def _challenge_key() -> bytes:
    return hmac.new(get_settings().jwt_secret.encode("utf-8"), _CHALLENGE_CONTEXT, hashlib.sha256).digest()


@dataclass(frozen=True)
class Challenge:
    user_id: uuid.UUID
    challenge_id: uuid.UUID


async def issue_challenge(session: AsyncSession, user: User) -> str:
    now = datetime.now(UTC)
    await session.execute(delete(TwoFactorChallenge).where(TwoFactorChallenge.expiresAt < now))
    expires = now + timedelta(minutes=CHALLENGE_MINUTES)
    row = TwoFactorChallenge(userId=user.id, expiresAt=expires)
    session.add(row)
    await session.flush()
    await session.commit()
    return jwt.encode(
        {
            "sub": str(user.id),
            "jti": str(row.id),
            "purpose": CHALLENGE_PURPOSE,
            "iat": int(now.timestamp()),
            "exp": expires,
        },
        _challenge_key(),
        algorithm="HS256",
    )


def read_challenge(token: str) -> Challenge:
    try:
        claims = jwt.decode(
            token or "", _challenge_key(), algorithms=["HS256"], options={"require": ["exp", "sub", "jti"]}
        )
        if claims.get("purpose") != CHALLENGE_PURPOSE:
            raise TwoFactorError("dead", CHALLENGE_DEAD_DETAIL)
        return Challenge(user_id=uuid.UUID(str(claims["sub"])), challenge_id=uuid.UUID(str(claims["jti"])))
    except (jwt.PyJWTError, ValueError) as exc:
        raise TwoFactorError("dead", CHALLENGE_DEAD_DETAIL) from exc


async def spend_challenge_attempt(session: AsyncSession, challenge: Challenge) -> bool:
    result = await session.execute(
        update(TwoFactorChallenge)
        .where(
            TwoFactorChallenge.id == challenge.challenge_id,
            TwoFactorChallenge.userId == challenge.user_id,
            TwoFactorChallenge.usedAt.is_(None),
            TwoFactorChallenge.attempts < MAX_CHALLENGE_ATTEMPTS,
            TwoFactorChallenge.expiresAt > datetime.now(UTC),
        )
        .values(attempts=TwoFactorChallenge.attempts + 1)
    )
    await session.commit()
    return result.rowcount == 1


async def close_challenge(session: AsyncSession, challenge: Challenge) -> bool:
    result = await session.execute(
        update(TwoFactorChallenge)
        .where(TwoFactorChallenge.id == challenge.challenge_id, TwoFactorChallenge.usedAt.is_(None))
        .values(usedAt=datetime.now(UTC))
    )
    return result.rowcount == 1


def pending_is_live(user: Any, now: datetime | None = None) -> bool:
    if getattr(user, "twoFactorEnabled", False) or not getattr(user, "twoFactorPendingSecret", None):
        return False
    since = aware_utc(getattr(user, "twoFactorPendingSince", None))
    if since is None:
        return False
    return (now or datetime.now(UTC)) - since < timedelta(minutes=PENDING_SETUP_MINUTES)


def status_of(user: Any, now: datetime | None = None) -> dict[str, Any]:
    from app.core.roles import requires_two_factor

    enabled = bool(getattr(user, "twoFactorEnabled", False))
    enabled_at = getattr(user, "twoFactorEnabledAt", None) if enabled else None
    return {
        "enabled": enabled,
        "pending": pending_is_live(user, now),
        "required": requires_two_factor(user),
        "recovery_codes_remaining": len(getattr(user, "twoFactorRecoveryCodes", None) or [])
        if enabled
        else 0,
        "enabled_at": enabled_at.isoformat() if enabled_at else None,
    }


async def clear_pending(session: AsyncSession, user_id: uuid.UUID) -> bool:
    result = await session.execute(
        update(User)
        .where(User.id == user_id, User.twoFactorEnabled.is_(False), User.twoFactorPendingSecret.is_not(None))
        .values(twoFactorPendingSecret=None, twoFactorPendingSince=None)
    )
    return bool(result.rowcount)


async def begin_setup(session: AsyncSession, user: User) -> dict[str, str]:
    if user.twoFactorEnabled:
        raise TwoFactorError("conflict", ALREADY_ON_DETAIL)
    secret = generate_secret()
    user.twoFactorPendingSecret = encrypt_secret(secret)
    user.twoFactorPendingSince = datetime.now(UTC)
    await session.commit()
    uri = totp_uri(secret, user.email)
    return {"secret": secret, "otpauth_uri": uri, "qr_svg": qr_svg(uri)}


async def enable(session: AsyncSession, user: User, code: str) -> list[str]:
    if user.twoFactorEnabled:
        raise TwoFactorError("conflict", ALREADY_ON_DETAIL)
    pending = user.twoFactorPendingSecret
    secret = decrypt_secret(pending) if pending_is_live(user) else None
    if secret is None:
        raise TwoFactorError("invalid", NO_SETUP_DETAIL)
    step = match_totp_step(secret, code)
    if step is None:
        raise TwoFactorError("invalid", WRONG_CODE_DETAIL)
    codes = generate_recovery_codes()
    hashes = await hash_recovery_codes(codes)
    result = await session.execute(
        update(User)
        .where(User.id == user.id, User.twoFactorEnabled.is_(False), User.twoFactorPendingSecret == pending)
        .values(
            twoFactorEnabled=True,
            twoFactorSecret=encrypt_secret(secret),
            twoFactorPendingSecret=None,
            twoFactorPendingSince=None,
            twoFactorRecoveryCodes=hashes,
            twoFactorLastStep=step,
            twoFactorEnabledAt=datetime.now(UTC),
            tokenVersion=User.tokenVersion + 1,
        )
    )
    if result.rowcount != 1:
        raise TwoFactorError("conflict", NO_SETUP_DETAIL)
    await session.commit()
    return codes


OFF_VALUES: dict[str, Any] = {
    "twoFactorEnabled": False,
    "twoFactorSecret": None,
    "twoFactorPendingSecret": None,
    "twoFactorPendingSince": None,
    "twoFactorRecoveryCodes": [],
    "twoFactorLastStep": None,
    "twoFactorEnabledAt": None,
    **CLEAR_FAILURES,
}


async def _checked(session: AsyncSession, user: User, code: str, *, allow_recovery: bool = True) -> bool:
    try:
        return await check_second_factor(session, user, code, allow_recovery=allow_recovery)
    except SecondFactorLocked as exc:
        raise TwoFactorError("locked", TOO_MANY_ATTEMPTS_DETAIL) from exc


async def disable(session: AsyncSession, user: User, code: str) -> str:
    from app.core.roles import requires_two_factor

    if not user.twoFactorEnabled:
        raise TwoFactorError("conflict", NOT_ON_DETAIL)
    if requires_two_factor(user):
        raise TwoFactorError("conflict", REQUIRED_FOR_ROLE_DETAIL)
    if not await _checked(session, user, code):
        raise TwoFactorError("invalid", WRONG_CODE_DETAIL)
    await session.execute(
        update(User).where(User.id == user.id).values(**OFF_VALUES, tokenVersion=User.tokenVersion + 1)
    )
    await session.commit()
    return code_kind(code) or TOTP


async def regenerate_recovery_codes(session: AsyncSession, user: User, code: str) -> list[str]:
    if not user.twoFactorEnabled:
        raise TwoFactorError("conflict", NOT_ON_DETAIL)
    if not await _checked(session, user, code, allow_recovery=False):
        raise TwoFactorError("invalid", WRONG_CODE_DETAIL)
    codes = generate_recovery_codes()
    hashes = await hash_recovery_codes(codes)
    await session.execute(update(User).where(User.id == user.id).values(twoFactorRecoveryCodes=hashes))
    await session.commit()
    return codes


async def reset_by_administrator(session: AsyncSession, target: User) -> int:
    destroyed = len(target.twoFactorRecoveryCodes or [])
    await session.execute(
        update(User)
        .where(User.id == target.id)
        .values(**OFF_VALUES, tokenVersion=User.tokenVersion + 1, sessionsValidFrom=datetime.now(UTC))
    )
    return destroyed


async def step_up(session: AsyncSession, user: User, code: str | None) -> bool:
    if not user.twoFactorEnabled or not code:
        return False
    try:
        return await check_second_factor(session, user, code, allow_recovery=False)
    except SecondFactorLocked:
        return False
