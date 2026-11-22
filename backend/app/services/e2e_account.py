import base64
import re
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.roles import ADMIN, PROFESSOR, RESEARCHER
from app.services import access_roster, two_factor
from app.services.password_accounts import (
    PasswordAccount,
    operator_password_refusal,
    upsert_password_account,
)
from app.services.shared_files import FileDeleter

__all__ = [
    "E2E_ACCOUNT_EMAIL",
    "E2E_ACCOUNT_NAME",
    "E2E_ACCOUNT_NOTE",
    "E2E_ACCOUNT_ROLE",
    "E2E_ADDRESSES",
    "E2E_ADMIN",
    "E2E_PROFESSOR",
    "E2E_ROLE_ACCOUNTS",
    "E2E_ROLE_NOTE",
    "MIN_TOTP_SECRET_BYTES",
    "E2ERoleAccount",
    "NotAnE2EAccount",
    "canonical_totp_secret",
    "e2e_address",
    "provision_e2e_account",
    "provision_role_account",
    "totp_secret_refusal",
]

E2E_ACCOUNT_EMAIL = "e2e-researcher@kalavigyan.example"
E2E_ACCOUNT_NAME = "KalaVigyan E2E Researcher"
E2E_ACCOUNT_ROLE = RESEARCHER
E2E_ACCOUNT_NOTE = "Signs in for the E2E production workflow (decision 0029)."
E2E_ROLE_NOTE = "Signs in with two-step for the E2E production workflow's role screens (decision 0029)."
MIN_TOTP_SECRET_BYTES = 16


@dataclass(frozen=True)
class E2ERoleAccount:
    role: str
    email: str
    name: str

    def secret_name(self, part: str) -> str:
        return f"E2E_{self.role}_{part}"


E2E_PROFESSOR = E2ERoleAccount(PROFESSOR, "e2e-professor@kalavigyan.example", "KalaVigyan E2E Professor")
E2E_ADMIN = E2ERoleAccount(ADMIN, "e2e-admin@kalavigyan.example", "KalaVigyan E2E Admin")
E2E_ROLE_ACCOUNTS: tuple[E2ERoleAccount, ...] = (E2E_PROFESSOR, E2E_ADMIN)
E2E_ADDRESSES = frozenset({E2E_ACCOUNT_EMAIL, *(account.email for account in E2E_ROLE_ACCOUNTS)})


class NotAnE2EAccount(ValueError):
    pass


def e2e_address(email: str) -> str:
    address = access_roster.normalise_email(email)
    if address not in E2E_ADDRESSES:
        raise NotAnE2EAccount(f"{address} is not a reserved E2E address; nothing was changed.")
    return address


def canonical_totp_secret(secret: str) -> str:
    return re.sub(r"\s", "", secret or "").upper().rstrip("=")


def totp_secret_refusal(secret: str) -> str | None:
    cleaned = canonical_totp_secret(secret)
    try:
        key = base64.b32decode(cleaned + "=" * (-len(cleaned) % 8))
    except ValueError:
        return "The two-step secret must be base32 (A to Z and 2 to 7)."
    if len(key) < MIN_TOTP_SECRET_BYTES:
        return f"The two-step secret must hold at least {MIN_TOTP_SECRET_BYTES} bytes (26 base32 characters)."
    return None


async def provision_e2e_account(
    session: AsyncSession,
    password: str,
    *,
    objects: FileDeleter | None,
    email: str = E2E_ACCOUNT_EMAIL,
    now: datetime | None = None,
) -> PasswordAccount:
    moment = now or datetime.now(UTC)
    account = await upsert_password_account(
        session,
        email=email,
        name=E2E_ACCOUNT_NAME,
        role=E2E_ACCOUNT_ROLE,
        password=password,
        now=moment,
        objects=objects,
    )
    user = account.user
    user.emailVerifiedAt = user.emailVerifiedAt or moment
    for column, value in two_factor.OFF_VALUES.items():
        setattr(user, column, value)
    account.roster.fullName = E2E_ACCOUNT_NAME
    account.roster.notes = E2E_ACCOUNT_NOTE
    return account


async def provision_role_account(
    session: AsyncSession,
    account: E2ERoleAccount,
    password: str,
    totp_secret: str,
    *,
    objects: FileDeleter | None,
    now: datetime | None = None,
) -> PasswordAccount:
    _refuse_unless_provisionable(account, password, totp_secret)
    address = e2e_address(account.email)
    moment = now or datetime.now(UTC)
    provisioned = await upsert_password_account(
        session,
        email=address,
        name=account.name,
        role=account.role,
        password=password,
        now=moment,
        objects=objects,
    )
    user = provisioned.user
    secret = canonical_totp_secret(totp_secret)
    kept = bool(user.twoFactorEnabled) and two_factor.decrypt_secret(user.twoFactorSecret) == secret
    values = {
        **two_factor.OFF_VALUES,
        "twoFactorEnabled": True,
        "twoFactorSecret": two_factor.encrypt_secret(secret),
        "twoFactorEnabledAt": user.twoFactorEnabledAt if kept else moment,
    }
    for column, value in values.items():
        setattr(user, column, value)
    user.name = account.name
    user.emailVerifiedAt = user.emailVerifiedAt or moment
    provisioned.roster.fullName = account.name
    provisioned.roster.notes = E2E_ROLE_NOTE
    return provisioned


def _refuse_unless_provisionable(account: E2ERoleAccount, password: str, totp_secret: str) -> None:
    if account not in E2E_ROLE_ACCOUNTS:
        raise NotAnE2EAccount(
            f"{account.email} as {account.role} is not an E2E role account; nothing was changed."
        )
    refusal = operator_password_refusal(password) or totp_secret_refusal(totp_secret)
    if refusal:
        raise ValueError(refusal)
