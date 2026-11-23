from datetime import UTC, datetime

import httpx
import pytest
from sqlalchemy import func, select

from app.core.db import session_scope
from app.core.roles import MASTER_ADMIN
from app.core.security import verify_password
from app.models import AccessRoster, ConsentRecord, User
from app.services import two_factor
from app.services.e2e_account import E2E_ACCOUNT_NAME, provision_e2e_account
from app.services.password_accounts import CREATED, UPDATED, upsert_password_account

from .accounts import PASSWORD, bearer, unique_email

pytestmark = pytest.mark.db

NEW_PASSWORD = "a-second-long-passphrase"


async def provision(email: str, password: str = PASSWORD) -> str:
    async with session_scope() as session:
        account = await provision_e2e_account(session, password, objects=None, email=email)
        return account.outcome


async def account(email: str) -> User:
    async with session_scope() as session:
        return (await session.execute(select(User).where(User.email == email))).scalar_one()


async def roster(email: str) -> AccessRoster:
    async with session_scope() as session:
        return (await session.execute(select(AccessRoster).where(AccessRoster.email == email))).scalar_one()


async def counts(email: str) -> tuple[int, int]:
    async with session_scope() as session:
        users = (await session.execute(select(func.count()).where(User.email == email))).scalar_one()
        rows = (await session.execute(select(func.count()).where(AccessRoster.email == email))).scalar_one()
        return users, rows


async def consent_kinds(user: User) -> list[str]:
    async with session_scope() as session:
        rows = await session.execute(select(ConsentRecord.kind).where(ConsentRecord.userId == user.id))
        return [str(kind) for kind in rows.scalars()]


async def password_login(client: httpx.AsyncClient, email: str, password: str) -> httpx.Response:
    return await client.post("/api/auth/login", json={"email": email, "password": password})


async def test_provisioning_creates_a_verified_researcher_with_no_consents() -> None:
    email = unique_email("e2e-researcher")
    assert await provision(email) == CREATED
    user = await account(email)
    assert user.role == "RESEARCHER"
    assert user.name == E2E_ACCOUNT_NAME
    assert user.emailVerifiedAt is not None
    assert user.passwordSetAt is not None
    assert user.twoFactorEnabled is False
    assert user.mustChangePassword is False
    assert user.deletedAt is None
    assert verify_password(PASSWORD, user.passwordHash)
    row = await roster(email)
    assert (row.status, row.admitRole, row.fullName) == ("ACTIVE", "RESEARCHER", E2E_ACCOUNT_NAME)
    assert row.joinedAt is not None
    assert await consent_kinds(user) == []


async def test_the_provisioned_account_signs_in_without_two_step_and_may_ask_deep(
    client: httpx.AsyncClient,
) -> None:
    email = unique_email("e2e-researcher")
    await provision(email)
    response = await password_login(client, email, PASSWORD)
    assert response.status_code == 200, response.text
    body = response.json()
    assert "two_factor_required" not in body
    me = (await client.get("/api/auth/me", headers=bearer(body["accessToken"]))).json()
    assert me["role"] == "RESEARCHER"
    assert me["accessStatus"] == "ACTIVE"
    assert me["twoFactorRequired"] is False
    assert me["twoFactorEnabled"] is False
    assert "PROPOSE_KNOWLEDGE" in me["capabilities"]
    assert "MANAGE_ACCESS" not in me["capabilities"]


async def test_provisioning_again_updates_the_same_rows_and_ends_old_sessions(
    client: httpx.AsyncClient,
) -> None:
    email = unique_email("e2e-researcher")
    await provision(email)
    first = await account(email)
    old_token = (await password_login(client, email, PASSWORD)).json()["accessToken"]
    assert await provision(email, NEW_PASSWORD) == UPDATED
    second = await account(email)
    assert second.id == first.id
    assert second.tokenVersion == first.tokenVersion + 1
    assert second.emailVerifiedAt == first.emailVerifiedAt
    assert await counts(email) == (1, 1)
    assert (await client.get("/api/auth/me", headers=bearer(old_token))).status_code == 401
    assert (await password_login(client, email, PASSWORD)).status_code == 401
    assert (await password_login(client, email, NEW_PASSWORD)).status_code == 200


async def test_provisioning_restores_an_account_someone_changed(client: httpx.AsyncClient) -> None:
    email = unique_email("e2e-researcher")
    await provision(email)
    secret = two_factor.generate_secret()
    async with session_scope() as session:
        user = (await session.execute(select(User).where(User.email == email))).scalar_one()
        user.role = "STUDENT"
        user.twoFactorEnabled = True
        user.twoFactorSecret = two_factor.encrypt_secret(secret)
        user.twoFactorEnabledAt = datetime.now(UTC)
        user.mustChangePassword = True
        user.deletedAt = datetime.now(UTC)
        row = (await session.execute(select(AccessRoster).where(AccessRoster.email == email))).scalar_one()
        row.status = "SUSPENDED"
        row.admitRole = "STUDENT"
    assert await provision(email) == UPDATED
    user = await account(email)
    assert (user.role, user.twoFactorEnabled, user.twoFactorSecret) == ("RESEARCHER", False, None)
    assert (user.mustChangePassword, user.deletedAt) == (False, None)
    row = await roster(email)
    assert (row.status, row.admitRole) == ("ACTIVE", "RESEARCHER")
    response = await password_login(client, email, PASSWORD)
    assert response.status_code == 200, response.text
    assert "accessToken" in response.json()


async def test_the_shared_upsert_keeps_the_master_admin_path() -> None:
    email = unique_email("break-glass")
    now = datetime.now(UTC)
    async with session_scope() as session:
        created = await upsert_password_account(
            session,
            email=email.upper(),
            name="Owner",
            role=MASTER_ADMIN,
            password=PASSWORD,
            now=now,
            objects=None,
        )
        assert created.outcome == CREATED
    async with session_scope() as session:
        updated = await upsert_password_account(
            session,
            email=email,
            name="Ignored",
            role=MASTER_ADMIN,
            password=NEW_PASSWORD,
            now=now,
            objects=None,
        )
        assert updated.outcome == UPDATED
    user = await account(email)
    assert (user.role, user.name, user.twoFactorEnabled) == (MASTER_ADMIN, "Owner", False)
    assert verify_password(NEW_PASSWORD, user.passwordHash)
    row = await roster(email)
    assert (row.status, row.admitRole) == ("ACTIVE", MASTER_ADMIN)
    assert await counts(email) == (1, 1)
