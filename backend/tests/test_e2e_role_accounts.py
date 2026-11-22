import base64
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import Any

import pytest

from app.core.roles import ADMIN, MASTER_ADMIN, PROFESSOR, STUDENT, Capability, can, requires_two_factor
from app.schemas.admin import AccessRosterCreate
from app.schemas.auth import ForgotPasswordRequest
from app.services import e2e_account, two_factor
from app.services.e2e_account import (
    E2E_ACCOUNT_EMAIL,
    E2E_ADDRESSES,
    E2E_ADMIN,
    E2E_PROFESSOR,
    E2E_ROLE_ACCOUNTS,
    E2E_ROLE_NOTE,
    E2ERoleAccount,
    NotAnE2EAccount,
    e2e_address,
    provision_role_account,
    totp_secret_refusal,
)
from app.services.password_accounts import CREATED, UPDATED, PasswordAccount

PASSWORDS = {PROFESSOR: "professor-long-passphrase-7", ADMIN: "admin-long-passphrase-9"}
SECRETS = {PROFESSOR: two_factor.generate_secret(), ADMIN: two_factor.generate_secret()}
FIRST = datetime(2026, 11, 18, 9, 0, tzinfo=UTC)
LATER = FIRST + timedelta(days=3)
OWNER = "owner@example.com"


def blank_user(email: str, name: str, role: str) -> SimpleNamespace:
    return SimpleNamespace(
        email=email,
        name=name,
        role=role,
        tokenVersion=0,
        emailVerifiedAt=None,
        deletedAt=None,
        **two_factor.OFF_VALUES,
    )


class FakeAccounts:
    def __init__(self) -> None:
        self.users: dict[str, SimpleNamespace] = {}
        self.rosters: dict[str, SimpleNamespace] = {}
        self.calls: list[str] = []

    async def upsert(
        self,
        session: Any,
        *,
        email: str,
        name: str,
        role: str,
        password: str,
        now: datetime,
        objects: Any,
    ) -> PasswordAccount:
        self.calls.append(email)
        user = self.users.get(email)
        outcome = UPDATED
        if user is None:
            user = self.users[email] = blank_user(email, name, role)
            outcome = CREATED
        else:
            user.tokenVersion += 1
        user.role, user.password, user.deletedAt = role, password, None
        roster = self.rosters.setdefault(email, SimpleNamespace(email=email, fullName=None, notes=None))
        roster.status, roster.admitRole = "ACTIVE", role
        return PasswordAccount(user=user, roster=roster, outcome=outcome)


@pytest.fixture
def accounts(monkeypatch: pytest.MonkeyPatch) -> FakeAccounts:
    fake = FakeAccounts()
    monkeypatch.setattr(e2e_account, "upsert_password_account", fake.upsert)
    return fake


async def provision_all(now: datetime, secrets: dict[str, str] = SECRETS) -> list[PasswordAccount]:
    return [
        await provision_role_account(
            None, account, PASSWORDS[account.role], secrets[account.role], objects=None, now=now
        )
        for account in E2E_ROLE_ACCOUNTS
    ]


def test_the_role_addresses_are_reserved_and_pass_every_api_address_check() -> None:
    assert E2E_PROFESSOR.email == "e2e-professor@kalavigyan.example"
    assert E2E_ADMIN.email == "e2e-admin@kalavigyan.example"
    assert {E2E_ACCOUNT_EMAIL, E2E_PROFESSOR.email, E2E_ADMIN.email} == E2E_ADDRESSES
    for account in E2E_ROLE_ACCOUNTS:
        assert AccessRosterCreate(email=account.email).email == account.email
        assert ForgotPasswordRequest(email=account.email).email == account.email


def test_the_role_accounts_are_a_professor_and_an_admin_who_must_use_two_step() -> None:
    assert [account.role for account in E2E_ROLE_ACCOUNTS] == [PROFESSOR, ADMIN]
    assert all(requires_two_factor(account.role) for account in E2E_ROLE_ACCOUNTS)
    assert can(PROFESSOR, Capability.BUILD_LESSONS)
    assert can(ADMIN, Capability.MANAGE_ACCESS)
    assert MASTER_ADMIN not in {account.role for account in E2E_ROLE_ACCOUNTS}
    assert E2E_PROFESSOR.secret_name("TOTP_SECRET") == "E2E_PROFESSOR_TOTP_SECRET"
    assert E2E_ADMIN.secret_name("PASSWORD") == "E2E_ADMIN_PASSWORD"


async def test_provisioning_turns_two_step_on_with_the_secret_it_was_given(accounts: FakeAccounts) -> None:
    done = await provision_all(FIRST)
    assert [item.outcome for item in done] == [CREATED, CREATED]
    for account in E2E_ROLE_ACCOUNTS:
        user = accounts.users[account.email]
        assert (user.role, user.name, user.password) == (account.role, account.name, PASSWORDS[account.role])
        assert user.twoFactorEnabled is True
        assert two_factor.decrypt_secret(user.twoFactorSecret) == SECRETS[account.role]
        assert SECRETS[account.role] not in user.twoFactorSecret
        assert (user.twoFactorEnabledAt, user.emailVerifiedAt) == (FIRST, FIRST)
        assert (user.twoFactorPendingSecret, user.twoFactorRecoveryCodes, user.twoFactorLastStep) == (
            None,
            [],
            None,
        )
        roster = accounts.rosters[account.email]
        assert (roster.status, roster.admitRole, roster.fullName, roster.notes) == (
            "ACTIVE",
            account.role,
            account.name,
            E2E_ROLE_NOTE,
        )


async def test_a_code_from_the_given_secret_passes_the_servers_check(accounts: FakeAccounts) -> None:
    spaced = " ".join(SECRETS[PROFESSOR][i : i + 4] for i in range(0, 32, 4)).lower()
    await provision_role_account(None, E2E_PROFESSOR, PASSWORDS[PROFESSOR], spaced, objects=None, now=FIRST)
    stored = two_factor.decrypt_secret(accounts.users[E2E_PROFESSOR.email].twoFactorSecret)
    assert stored == SECRETS[PROFESSOR]
    assert two_factor.match_totp_step(stored, two_factor.current_totp(SECRETS[PROFESSOR])) is not None


async def test_provisioning_again_changes_nothing_but_ends_sessions(accounts: FakeAccounts) -> None:
    await provision_all(FIRST)
    before = {email: (id(user), user.tokenVersion) for email, user in accounts.users.items()}
    again = await provision_all(LATER)
    assert [item.outcome for item in again] == [UPDATED, UPDATED]
    assert set(accounts.users) == {E2E_PROFESSOR.email, E2E_ADMIN.email}
    for account in E2E_ROLE_ACCOUNTS:
        user = accounts.users[account.email]
        assert (id(user), user.tokenVersion) == (before[account.email][0], before[account.email][1] + 1)
        assert (user.emailVerifiedAt, user.twoFactorEnabledAt, user.twoFactorEnabled) == (FIRST, FIRST, True)
        assert two_factor.decrypt_secret(user.twoFactorSecret) == SECRETS[account.role]


async def test_a_new_secret_replaces_the_old_one_and_restarts_two_step(accounts: FakeAccounts) -> None:
    await provision_all(FIRST)
    fresh = {role: two_factor.generate_secret() for role in SECRETS}
    await provision_all(LATER, fresh)
    for account in E2E_ROLE_ACCOUNTS:
        user = accounts.users[account.email]
        assert two_factor.decrypt_secret(user.twoFactorSecret) == fresh[account.role]
        assert user.twoFactorEnabledAt == LATER


async def test_provisioning_restores_an_account_someone_locked_or_changed(accounts: FakeAccounts) -> None:
    changed = blank_user(E2E_ADMIN.email, "Renamed", STUDENT)
    changed.twoFactorRecoveryCodes = ["hash"]
    changed.twoFactorFailedAttempts = 10
    changed.twoFactorLockedUntil = LATER
    changed.twoFactorPendingSecret = "pending"
    accounts.users[E2E_ADMIN.email] = changed
    done = await provision_role_account(
        None, E2E_ADMIN, PASSWORDS[ADMIN], SECRETS[ADMIN], objects=None, now=FIRST
    )
    assert done.outcome == UPDATED
    assert (changed.role, changed.name, changed.twoFactorEnabled) == (ADMIN, E2E_ADMIN.name, True)
    assert (
        changed.twoFactorRecoveryCodes,
        changed.twoFactorFailedAttempts,
        changed.twoFactorLockedUntil,
    ) == ([], 0, None)
    assert changed.twoFactorPendingSecret is None


async def test_other_accounts_are_never_touched(accounts: FakeAccounts) -> None:
    owner = blank_user(OWNER, "Owner", MASTER_ADMIN)
    owner.twoFactorEnabled, owner.twoFactorSecret = (
        True,
        two_factor.encrypt_secret(two_factor.generate_secret()),
    )
    accounts.users[OWNER] = owner
    snapshot = dict(vars(owner))
    await provision_all(FIRST)
    await provision_all(LATER)
    assert vars(owner) == snapshot
    assert set(accounts.calls) == {E2E_PROFESSOR.email, E2E_ADMIN.email}
    assert OWNER not in accounts.rosters


@pytest.mark.parametrize(
    "forged",
    [
        E2ERoleAccount(ADMIN, OWNER, "Owner"),
        E2ERoleAccount(MASTER_ADMIN, E2E_ADMIN.email, E2E_ADMIN.name),
        E2ERoleAccount(ADMIN, E2E_ACCOUNT_EMAIL, E2E_ADMIN.name),
        E2ERoleAccount(PROFESSOR, "E2E-Professor@kalavigyan.example.org", E2E_PROFESSOR.name),
    ],
)
async def test_an_account_outside_the_registry_is_refused_before_any_write(
    forged: E2ERoleAccount, accounts: FakeAccounts
) -> None:
    with pytest.raises(NotAnE2EAccount):
        await provision_role_account(None, forged, PASSWORDS[ADMIN], SECRETS[ADMIN], objects=None, now=FIRST)
    assert accounts.calls == []
    assert accounts.users == {}


def test_only_the_reserved_addresses_pass_the_address_guard() -> None:
    assert e2e_address(" E2E-Admin@KalaVigyan.example ") == E2E_ADMIN.email
    for other in (OWNER, "e2e-admin@kalavigyan.example.com", "admin@kalavigyan.example"):
        with pytest.raises(NotAnE2EAccount):
            e2e_address(other)


@pytest.mark.parametrize(
    ("password", "secret"),
    [
        ("short-pass", SECRETS[ADMIN]),
        (PASSWORDS[ADMIN], "not-base32-at-all-1890"),
        (PASSWORDS[ADMIN], base64.b32encode(b"x" * 15).decode()),
    ],
)
async def test_a_weak_password_or_secret_is_refused_before_any_write_and_not_echoed(
    password: str, secret: str, accounts: FakeAccounts
) -> None:
    with pytest.raises(ValueError) as refused:
        await provision_role_account(None, E2E_ADMIN, password, secret, objects=None, now=FIRST)
    assert password not in str(refused.value)
    assert secret not in str(refused.value)
    assert accounts.calls == []


@pytest.mark.parametrize(
    ("secret", "refused"),
    [
        (two_factor.generate_secret(), False),
        (base64.b32encode(b"k" * 16).decode(), False),
        (base64.b32encode(b"k" * 16).decode().rstrip("="), False),
        (base64.b32encode(b"k" * 15).decode(), True),
        ("0189ABCD0189ABCD0189ABCD0189ABCD", True),
        ("", True),
    ],
)
def test_two_step_secrets_are_base32_of_at_least_sixteen_bytes(secret: str, refused: bool) -> None:
    assert (totp_secret_refusal(secret) is not None) is refused
