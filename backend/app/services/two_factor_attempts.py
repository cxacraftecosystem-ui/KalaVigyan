import logging
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import User

from .two_factor_codes import RECOVERY, TOTP, code_kind, match_totp_step, matching_hash
from .two_factor_keys import decrypt_secret

__all__ = [
    "BUDGETS",
    "CLEAR_FAILURES",
    "CODE_BUDGET",
    "FAILURE_BUDGET",
    "FAILURE_WINDOW",
    "FIRST_LOCKOUT",
    "LOCKOUT_DECAY",
    "MAX_LOCKOUT",
    "RECOVERY_BUDGET",
    "RECOVERY_FAILURE_BUDGET",
    "AttemptBudget",
    "SecondFactorLocked",
    "aware_utc",
    "budget_for",
    "check_second_factor",
    "claim_attempt_slot",
    "consume_recovery_code",
    "consume_totp_step",
    "fully_locked",
    "is_locked",
    "lock_if_spent",
    "lockout_duration",
    "settle_success",
    "verify_second_factor",
]

logger = logging.getLogger(__name__)

FAILURE_BUDGET = 10
RECOVERY_FAILURE_BUDGET = 5
FAILURE_WINDOW = timedelta(minutes=15)
FIRST_LOCKOUT = timedelta(minutes=15)
MAX_LOCKOUT = timedelta(hours=1)
LOCKOUT_DECAY = timedelta(hours=24)


class SecondFactorLocked(Exception):
    pass


@dataclass(frozen=True)
class AttemptBudget:
    name: str
    limit: int
    attempts: str
    window_started: str
    locked_until: str
    lockouts: str


CODE_BUDGET = AttemptBudget(
    "code",
    FAILURE_BUDGET,
    "twoFactorFailedAttempts",
    "twoFactorFailureWindowStartedAt",
    "twoFactorLockedUntil",
    "twoFactorLockouts",
)
RECOVERY_BUDGET = AttemptBudget(
    "recovery",
    RECOVERY_FAILURE_BUDGET,
    "twoFactorRecoveryFailedAttempts",
    "twoFactorRecoveryWindowStartedAt",
    "twoFactorRecoveryLockedUntil",
    "twoFactorRecoveryLockouts",
)
BUDGETS = (CODE_BUDGET, RECOVERY_BUDGET)

CLEAR_FAILURES: dict[str, Any] = {
    column: value
    for budget in BUDGETS
    for column, value in (
        (budget.attempts, 0),
        (budget.window_started, None),
        (budget.locked_until, None),
        (budget.lockouts, 0),
    )
}


def lockout_duration(previous_lockouts: int) -> timedelta:
    return min(FIRST_LOCKOUT * (2 ** min(max(previous_lockouts, 0), 16)), MAX_LOCKOUT)


def aware_utc(value: datetime | None) -> datetime | None:
    if value is not None and value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value


def is_locked(user: Any, budget: AttemptBudget = CODE_BUDGET, now: datetime | None = None) -> bool:
    until = aware_utc(getattr(user, budget.locked_until, None))
    return until is not None and until > (now or datetime.now(UTC))


def fully_locked(user: Any, now: datetime | None = None) -> bool:
    return all(is_locked(user, budget, now) for budget in BUDGETS)


def budget_for(code: str, *, allow_recovery: bool = True) -> AttemptBudget:
    return RECOVERY_BUDGET if allow_recovery and code_kind(code) == RECOVERY else CODE_BUDGET


def _col(name: str) -> Any:
    return getattr(User, name)


async def _fresh(session: AsyncSession, user_id: uuid.UUID) -> User | None:
    return (
        await session.execute(
            select(User).where(User.id == user_id).execution_options(populate_existing=True)
        )
    ).scalar_one_or_none()


async def consume_totp_step(session: AsyncSession, user_id: uuid.UUID, step: int) -> bool:
    result = await session.execute(
        update(User)
        .where(User.id == user_id, or_(User.twoFactorLastStep.is_(None), User.twoFactorLastStep < step))
        .values(twoFactorLastStep=step)
    )
    return result.rowcount == 1


async def consume_recovery_code(session: AsyncSession, user: User, submitted: str) -> bool:
    stored = list(user.twoFactorRecoveryCodes or [])
    if not stored:
        return False
    match = await matching_hash(stored, submitted)
    if match is None:
        return False
    remaining = [hashed for hashed in stored if hashed != match]
    result = await session.execute(
        update(User)
        .where(User.id == user.id, User.twoFactorRecoveryCodes == stored)
        .values(twoFactorRecoveryCodes=remaining)
    )
    return result.rowcount == 1


async def verify_second_factor(
    session: AsyncSession, user: User, code: str, *, allow_recovery: bool = True
) -> str | None:
    kind = code_kind(code)
    if kind == TOTP:
        secret = decrypt_secret(user.twoFactorSecret)
        if secret is None:
            return None
        step = match_totp_step(secret, code)
        if step is None or not await consume_totp_step(session, user.id, step):
            return None
        return TOTP
    if kind == RECOVERY and allow_recovery:
        return RECOVERY if await consume_recovery_code(session, user, code) else None
    return None


async def claim_attempt_slot(session: AsyncSession, user_id: uuid.UUID, budget: AttemptBudget) -> int:
    now = datetime.now(UTC)
    row = await _fresh(session, user_id)
    if row is None or is_locked(row, budget, now):
        raise SecondFactorLocked()
    started = aware_utc(getattr(row, budget.window_started))
    if started is None or now - started > FAILURE_WINDOW:
        values: dict[str, Any] = {budget.attempts: 0, budget.window_started: now}
        last_lock_end = aware_utc(getattr(row, budget.locked_until))
        if last_lock_end is not None and now - last_lock_end > LOCKOUT_DECAY:
            values[budget.lockouts] = 0
        await session.execute(update(User).where(User.id == user_id).values(**values))
    claimed = await session.execute(
        update(User)
        .where(
            User.id == user_id,
            _col(budget.attempts) < budget.limit,
            or_(_col(budget.locked_until).is_(None), _col(budget.locked_until) < now),
        )
        .values({budget.attempts: _col(budget.attempts) + 1})
        .returning(_col(budget.attempts))
    )
    count = claimed.scalar_one_or_none()
    if count is None:
        raise SecondFactorLocked()
    return int(count)


async def settle_success(session: AsyncSession, user_id: uuid.UUID, budget: AttemptBudget) -> None:
    await session.execute(
        update(User)
        .where(User.id == user_id)
        .values({budget.attempts: 0, budget.window_started: None, budget.lockouts: 0})
    )


async def lock_if_spent(session: AsyncSession, user_id: uuid.UUID, budget: AttemptBudget) -> bool:
    row = await _fresh(session, user_id)
    if row is None or (getattr(row, budget.attempts) or 0) < budget.limit:
        return False
    now = datetime.now(UTC)
    lockouts = int(getattr(row, budget.lockouts) or 0)
    until = now + lockout_duration(lockouts)
    result = await session.execute(
        update(User)
        .where(User.id == user_id, _col(budget.attempts) >= budget.limit)
        .values({budget.locked_until: until, budget.window_started: None, budget.lockouts: lockouts + 1})
    )
    if result.rowcount:
        logger.warning("two-factor locked", extra={"userId": str(user_id), "budget": budget.name})
    return bool(result.rowcount)


async def check_second_factor(
    session: AsyncSession, user: User, code: str, *, allow_recovery: bool = True
) -> bool:
    budget = budget_for(code, allow_recovery=allow_recovery)
    await claim_attempt_slot(session, user.id, budget)
    await session.commit()
    fresh = await _fresh(session, user.id)
    if fresh is None:
        return False
    if budget is RECOVERY_BUDGET:
        accepted = await consume_recovery_code(session, fresh, code)
    else:
        accepted = await verify_second_factor(session, fresh, code, allow_recovery=False) is not None
    if accepted:
        await settle_success(session, user.id, budget)
        await session.commit()
        return True
    await lock_if_spent(session, user.id, budget)
    await session.commit()
    return False
