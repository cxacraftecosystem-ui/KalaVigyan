from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import MAX_PASSWORD_LENGTH, hash_password
from app.models import AccessRoster, User
from app.services import access_roster, reader_profiles
from app.services.shared_files import FileDeleter

__all__ = [
    "CREATED",
    "MIN_OPERATOR_PASSWORD_LENGTH",
    "UPDATED",
    "PasswordAccount",
    "account_by_email",
    "operator_password_refusal",
    "upsert_password_account",
]

MIN_OPERATOR_PASSWORD_LENGTH = 12
CREATED = "created"
UPDATED = "updated"


@dataclass(frozen=True)
class PasswordAccount:
    user: User
    roster: AccessRoster
    outcome: str


def operator_password_refusal(password: str) -> str | None:
    if len(password) < MIN_OPERATOR_PASSWORD_LENGTH:
        return f"The password must be at least {MIN_OPERATOR_PASSWORD_LENGTH} characters."
    if len(password) > MAX_PASSWORD_LENGTH:
        return f"The password must be at most {MAX_PASSWORD_LENGTH} characters."
    return None


async def account_by_email(session: AsyncSession, email: str) -> User | None:
    address = access_roster.normalise_email(email)
    return (await session.execute(select(User).where(func.lower(User.email) == address))).scalar_one_or_none()


async def upsert_password_account(
    session: AsyncSession,
    *,
    email: str,
    name: str,
    role: str,
    password: str,
    now: datetime,
    objects: FileDeleter | None,
) -> PasswordAccount:
    address = access_roster.normalise_email(email)
    user = await account_by_email(session, address)
    if user is None:
        user = User(email=address, name=name, role=role)
        session.add(user)
        outcome = CREATED
    else:
        user.tokenVersion += 1
        outcome = UPDATED
        await reader_profiles.apply_role_change(session, user, role, objects=objects)
    user.role = role
    user.passwordHash = hash_password(password)
    user.passwordSetAt = now
    user.mustChangePassword = False
    user.deletedAt = None
    row = await access_roster.admit(session, address, admit_role=role, decided=False)
    return PasswordAccount(user=user, roster=row, outcome=outcome)
