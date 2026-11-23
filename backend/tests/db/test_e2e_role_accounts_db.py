import httpx
import pytest
from sqlalchemy import func, select

from app.core.db import session_scope
from app.models import AccessRoster, User
from app.services import two_factor
from app.services.e2e_account import (
    E2E_ROLE_ACCOUNTS,
    E2ERoleAccount,
    NotAnE2EAccount,
    provision_role_account,
)

from .accounts import PASSWORD, bearer, code, create_user, unique_email

pytestmark = pytest.mark.db


def new_secrets() -> dict[str, str]:
    return {account.role: two_factor.generate_secret() for account in E2E_ROLE_ACCOUNTS}


async def provision_both(secrets: dict[str, str]) -> None:
    async with session_scope() as session:
        for account in E2E_ROLE_ACCOUNTS:
            await provision_role_account(session, account, PASSWORD, secrets[account.role], objects=None)


async def user_at(email: str) -> User:
    async with session_scope() as session:
        return (await session.execute(select(User).where(User.email == email))).scalar_one()


async def counts(email: str) -> tuple[int, int]:
    async with session_scope() as session:
        users = (await session.execute(select(func.count()).where(User.email == email))).scalar_one()
        rows = (await session.execute(select(func.count()).where(AccessRoster.email == email))).scalar_one()
        return users, rows


async def two_step_sign_in(client: httpx.AsyncClient, email: str, secret: str) -> httpx.Response:
    first = await client.post("/api/auth/login", json={"email": email, "password": PASSWORD})
    assert first.status_code == 200, first.text
    body = first.json()
    assert body["two_factor_required"] is True
    assert "accessToken" not in body
    return await client.post(
        "/api/auth/two-factor/verify", json={"challenge_token": body["challenge_token"], "code": code(secret)}
    )


async def test_each_role_account_signs_in_with_its_password_and_a_code_from_its_secret(
    client: httpx.AsyncClient,
) -> None:
    secrets = new_secrets()
    await provision_both(secrets)
    for account in E2E_ROLE_ACCOUNTS:
        verified = await two_step_sign_in(client, account.email, secrets[account.role])
        assert verified.status_code == 200, verified.text
        me = (await client.get("/api/auth/me", headers=bearer(verified.json()["accessToken"]))).json()
        assert me["role"] == account.role
        assert me["accessStatus"] == "ACTIVE"
        assert (me["twoFactorEnabled"], me["twoFactorRequired"]) == (True, True)
        user = await user_at(account.email)
        assert (user.name, user.emailVerifiedAt is not None, user.twoFactorRecoveryCodes) == (
            account.name,
            True,
            [],
        )


async def test_provisioning_again_keeps_one_row_each_and_ends_old_sessions(client: httpx.AsyncClient) -> None:
    secrets = new_secrets()
    await provision_both(secrets)
    first = {account.email: await user_at(account.email) for account in E2E_ROLE_ACCOUNTS}
    professor = E2E_ROLE_ACCOUNTS[0]
    token = (await two_step_sign_in(client, professor.email, secrets[professor.role])).json()["accessToken"]
    rotated = new_secrets()
    await provision_both(rotated)
    for account in E2E_ROLE_ACCOUNTS:
        user = await user_at(account.email)
        assert user.id == first[account.email].id
        assert user.tokenVersion == first[account.email].tokenVersion + 1
        assert two_factor.decrypt_secret(user.twoFactorSecret) == rotated[account.role]
        assert await counts(account.email) == (1, 1)
    assert (await client.get("/api/auth/me", headers=bearer(token))).status_code == 401
    stale = await two_step_sign_in(client, professor.email, secrets[professor.role])
    assert stale.status_code == 401


async def test_other_accounts_are_left_exactly_as_they_were() -> None:
    other = unique_email("not-e2e-admin")
    await create_user(other, "ADMIN", with_two_factor=True)
    before = await user_at(other)
    await provision_both(new_secrets())
    forged = E2ERoleAccount("ADMIN", other, "Forged")
    async with session_scope() as session:
        with pytest.raises(NotAnE2EAccount):
            await provision_role_account(
                session, forged, PASSWORD, two_factor.generate_secret(), objects=None
            )
    after = await user_at(other)
    columns = ("name", "role", "passwordHash", "tokenVersion", "twoFactorSecret", "twoFactorEnabledAt")
    assert {column: getattr(after, column) for column in columns} == {
        column: getattr(before, column) for column in columns
    }
