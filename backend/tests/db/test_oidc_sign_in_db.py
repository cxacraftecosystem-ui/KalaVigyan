import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Any

import httpx
import pytest
from sqlalchemy import select

from app.core.db import session_scope
from app.core.security import hash_password
from app.main import app
from app.models import AccessRoster, AuditLog, User
from app.services import two_factor
from tests.oidc_fake_idp import REDIRECT_URI, FakeIdP, login_body

pytestmark = pytest.mark.db

PASSWORD = "correct-horse-battery"


def address(slug: str) -> str:
    return f"oidc-{slug}-{uuid.uuid4().hex[:10]}@example.com"


@pytest.fixture(scope="module")
async def client() -> AsyncIterator[httpx.AsyncClient]:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as http:
        yield http


async def admit(email: str, *, status: str = "ACTIVE", role: str | None = "RESEARCHER") -> None:
    async with session_scope() as session:
        session.add(AccessRoster(email=email, status=status, admitRole=role))


async def add_user(email: str, **fields: Any) -> uuid.UUID:
    values = {"email": email, "name": email.split("@")[0], "role": "RESEARCHER"} | fields
    async with session_scope() as session:
        user = User(**values)
        session.add(user)
        await session.flush()
        return user.id


async def user_at(email: str) -> User | None:
    async with session_scope() as session:
        return (await session.execute(select(User).where(User.email == email))).scalar_one_or_none()


async def yahoo_nonce(client: httpx.AsyncClient) -> str:
    response = await client.post("/api/auth/oidc/nonce", json={"provider": "YAHOO"})
    assert response.status_code == 200, response.text
    return response.json()["nonce"]


async def yahoo_sign_in(client: httpx.AsyncClient, idp: FakeIdP, email: str, **claims: Any) -> httpx.Response:
    nonce = await yahoo_nonce(client)
    idp.issue(idp.sign(idp.yahoo_claims(email, raw_nonce=nonce, **claims), alg="ES256"))
    return await client.post("/api/auth/login", json=login_body("YAHOO", raw_nonce=nonce))


@pytest.fixture
def idp(monkeypatch: pytest.MonkeyPatch) -> FakeIdP:
    return FakeIdP().install(monkeypatch)


async def test_an_admitted_yahoo_address_gets_a_yahoo_account_at_its_admitted_tier(
    client: httpx.AsyncClient, idp: FakeIdP
) -> None:
    email = address("admitted")
    await admit(email, role="RESEARCHER")
    response = await yahoo_sign_in(client, idp, email.upper())
    assert response.status_code == 200, response.text
    user = response.json()["user"]
    assert response.json()["accessToken"]
    assert (user["email"], user["authProvider"], user["role"]) == (email, "YAHOO", "RESEARCHER")
    assert user["name"] == "Ravi Kumar"
    assert user["emailVerifiedAt"] and user["avatarUrl"] is None


async def test_an_unknown_address_becomes_a_pending_request_and_gets_no_account(
    client: httpx.AsyncClient, idp: FakeIdP
) -> None:
    email = address("stranger")
    response = await yahoo_sign_in(client, idp, email)
    assert response.status_code == 403, response.text
    assert response.headers["x-access-status"] == "PENDING"
    assert await user_at(email) is None
    async with session_scope() as session:
        row = (await session.execute(select(AccessRoster).where(AccessRoster.email == email))).scalar_one()
        assert row.status == "PENDING"


async def test_a_suspended_address_is_refused_as_suspended(client: httpx.AsyncClient, idp: FakeIdP) -> None:
    email = address("suspended")
    await admit(email, status="SUSPENDED")
    response = await yahoo_sign_in(client, idp, email)
    assert response.status_code == 403
    assert response.headers["x-access-status"] == "SUSPENDED"
    assert await user_at(email) is None


async def test_an_unverified_yahoo_address_is_refused_before_admission(
    client: httpx.AsyncClient, idp: FakeIdP
) -> None:
    email = address("unverified")
    response = await yahoo_sign_in(client, idp, email, email_verified=False)
    assert response.status_code == 401
    assert response.json()["detail"] == "This Yahoo account's email address isn't verified."
    assert await user_at(email) is None
    async with session_scope() as session:
        found = await session.execute(select(AccessRoster).where(AccessRoster.email == email))
        assert found.scalar_one_or_none() is None


async def test_a_master_admin_signing_in_with_yahoo_is_challenged_for_the_second_step(
    client: httpx.AsyncClient, idp: FakeIdP
) -> None:
    email = address("master")
    secret = two_factor.generate_secret()
    user_id = await add_user(
        email,
        role="MASTER_ADMIN",
        passwordHash=hash_password(PASSWORD),
        emailVerifiedAt=datetime.now(UTC),
        twoFactorEnabled=True,
        twoFactorSecret=two_factor.encrypt_secret(secret),
    )
    await admit(email, role="MASTER_ADMIN")
    challenged = await yahoo_sign_in(client, idp, email)
    assert challenged.status_code == 200, challenged.text
    assert challenged.json()["two_factor_required"] is True
    assert "accessToken" not in challenged.json()
    verified = await client.post(
        "/api/auth/two-factor/verify",
        json={
            "challenge_token": challenged.json()["challenge_token"],
            "code": two_factor.current_totp(secret),
        },
    )
    assert verified.status_code == 200, verified.text
    assert verified.json()["user"]["id"] == str(user_id)
    assert verified.json()["user"]["authProvider"] == "LOCAL"


async def test_a_nonce_signs_in_once(client: httpx.AsyncClient, idp: FakeIdP) -> None:
    email = address("replay")
    await admit(email)
    nonce = await yahoo_nonce(client)
    idp.issue(idp.sign(idp.yahoo_claims(email, raw_nonce=nonce)))
    first = await client.post("/api/auth/login", json=login_body("YAHOO", raw_nonce=nonce))
    assert first.status_code == 200, first.text
    replayed = await client.post("/api/auth/login", json=login_body("YAHOO", raw_nonce=nonce))
    assert replayed.status_code == 401
    assert replayed.json()["detail"] == "Yahoo sign-in didn't work. Try again."
    assert len(idp.redemptions) == 1


async def test_a_redirect_uri_other_than_the_web_callback_redeems_nothing(
    client: httpx.AsyncClient, idp: FakeIdP
) -> None:
    nonce = await yahoo_nonce(client)
    body = login_body("YAHOO", raw_nonce=nonce) | {
        "oidcRedirectUri": REDIRECT_URI.replace("https://", "https://x.")
    }
    response = await client.post("/api/auth/login", json=body)
    assert response.status_code == 401
    assert idp.redemptions == []


async def test_a_google_account_keeps_its_provider_and_its_avatar(
    client: httpx.AsyncClient, idp: FakeIdP
) -> None:
    email = address("google")
    avatar = "https://lh3.googleusercontent.com/a/photo"
    verified_at = datetime.now(UTC)
    await add_user(email, authProvider="GOOGLE", avatarUrl=avatar, emailVerifiedAt=verified_at)
    await admit(email)
    response = await yahoo_sign_in(client, idp, email)
    assert response.status_code == 200, response.text
    user = response.json()["user"]
    assert (user["authProvider"], user["avatarUrl"]) == ("GOOGLE", avatar)


async def test_an_unconfirmed_password_account_is_cleared_and_audited_as_google_does(
    client: httpx.AsyncClient, idp: FakeIdP
) -> None:
    email = address("unconfirmed")
    user_id = await add_user(email, passwordHash=hash_password(PASSWORD), authProvider="LOCAL")
    await admit(email, role="STUDENT")
    response = await yahoo_sign_in(client, idp, email)
    assert response.status_code == 200, response.text
    user = response.json()["user"]
    assert (user["hasPassword"], user["authProvider"], user["role"]) == (False, "YAHOO", "STUDENT")
    assert user["emailVerifiedAt"]
    me = await client.get(
        "/api/auth/me", headers={"Authorization": f"Bearer {response.json()['accessToken']}"}
    )
    assert me.status_code == 200, me.text
    async with session_scope() as session:
        actions = await session.execute(select(AuditLog.action).where(AuditLog.targetId == str(user_id)))
        assert "auth.unverified_credentials_cleared" in set(actions.scalars())


async def test_a_password_attempt_on_a_yahoo_account_points_back_to_yahoo(
    client: httpx.AsyncClient, idp: FakeIdP
) -> None:
    email = address("no-password")
    await admit(email)
    assert (await yahoo_sign_in(client, idp, email)).status_code == 200
    refused = await client.post("/api/auth/login", json={"email": email, "password": PASSWORD})
    assert refused.status_code == 401
    assert refused.json()["detail"] == (
        "This account has no password yet. Sign in with Yahoo, or ask for a set-password link."
    )
    assert refused.headers["x-sign-in-hint"] == "PASSWORD_NOT_SET"
