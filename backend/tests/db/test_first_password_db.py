import time
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
import pytest
from sqlalchemy import select, update

from app.api.auth_session import session_token
from app.core.config import get_settings
from app.core.db import session_scope
from app.core.security import verify_password
from app.models import AccessRoster, AuditLog, User
from app.services import two_factor
from tests.google_fake import GOOGLE_CLIENT_ID, FakeGoogle
from tests.oidc_fake_idp import YAHOO_CLIENT_ID, FakeIdP, login_body

from .accounts import PASSWORD, bearer, code, create_user, unique_email

pytestmark = pytest.mark.db

NEW_PASSWORD = "a-first-password-of-my-own"
CONFIRM_GOOGLE = "To add a password, first confirm it's you by signing in with Google again."
GOOGLE_AGAIN = (
    "That Google sign-in didn't match this account or has expired. "
    "Sign in with Google again to confirm it's you."
)
YAHOO_AGAIN = (
    "That Yahoo sign-in didn't match this account or has expired. "
    "Sign in with Yahoo again to confirm it's you."
)


@pytest.fixture
def google(monkeypatch: pytest.MonkeyPatch) -> FakeGoogle:
    return FakeGoogle().install(monkeypatch)


@pytest.fixture
def idp(monkeypatch: pytest.MonkeyPatch) -> FakeIdP:
    return FakeIdP().install(monkeypatch)


async def provider_account(provider: str, *, two_factor_secret: str | None = None) -> tuple[str, str]:
    email = unique_email(f"first-password-{provider.lower()}")
    async with session_scope() as session:
        user = User(
            email=email,
            name=email.split("@")[0],
            role="RESEARCHER",
            authProvider=provider,
            emailVerifiedAt=datetime.now(UTC),
            tokenVersion=0,
            twoFactorEnabled=two_factor_secret is not None,
            twoFactorSecret=two_factor.encrypt_secret(two_factor_secret) if two_factor_secret else None,
        )
        session.add(user)
        session.add(AccessRoster(email=email, status="ACTIVE", admitRole="RESEARCHER"))
        await session.flush()
        token = session_token(user)
    return email, token


async def account_at(email: str) -> User:
    async with session_scope() as session:
        return (await session.execute(select(User).where(User.email == email))).scalar_one()


async def confirm_nonce(client: httpx.AsyncClient, token: str) -> dict[str, Any]:
    answer = await client.post("/api/auth/first-password/nonce", headers=bearer(token))
    assert answer.status_code == 200, answer.text
    return answer.json()


async def set_first(client: httpx.AsyncClient, token: str, **proof: Any) -> httpx.Response:
    body = {"newPassword": NEW_PASSWORD, **proof}
    return await client.post("/api/auth/change-password", json=body, headers=bearer(token))


async def test_a_google_only_account_sets_a_first_password_with_a_fresh_proof(
    client: httpx.AsyncClient, google: FakeGoogle
) -> None:
    email, token = await provider_account("GOOGLE")
    nonce = await confirm_nonce(client, token)
    assert (nonce["provider"], nonce["clientId"]) == ("GOOGLE", GOOGLE_CLIENT_ID)
    answer = await set_first(client, token, googleIdToken=google.mint(email.upper(), nonce["nonce"]))
    assert answer.status_code == 200, answer.text
    account = await account_at(email)
    assert verify_password(NEW_PASSWORD, account.passwordHash)
    assert account.tokenVersion == 1
    assert (await client.get("/api/auth/me", headers=bearer(token))).status_code == 401
    renewed = answer.headers["x-session-token"]
    assert (await client.get("/api/auth/me", headers=bearer(renewed))).json()["hasPassword"] is True
    signed_in = await client.post("/api/auth/login", json={"email": email, "password": NEW_PASSWORD})
    assert signed_in.status_code == 200, signed_in.text
    async with session_scope() as session:
        audit = await session.execute(
            select(AuditLog.action, AuditLog.detail).where(AuditLog.targetId == str(account.id))
        )
        recorded = [tuple(row) for row in audit.all()]
    assert ("auth.password_changed", {"firstPassword": True, "provider": "GOOGLE"}) in recorded


async def test_a_yahoo_account_sets_a_first_password_with_a_fresh_code(
    client: httpx.AsyncClient, idp: FakeIdP
) -> None:
    email, token = await provider_account("YAHOO")
    nonce = await confirm_nonce(client, token)
    assert (nonce["provider"], nonce["clientId"]) == ("YAHOO", YAHOO_CLIENT_ID)
    idp.issue(idp.sign(idp.yahoo_claims(email, raw_nonce=nonce["nonce"]), alg="ES256"))
    answer = await set_first(client, token, **login_body("YAHOO", raw_nonce=nonce["nonce"]))
    assert answer.status_code == 200, answer.text
    assert verify_password(NEW_PASSWORD, (await account_at(email)).passwordHash)
    assert len(idp.redemptions) == 1


async def test_a_proof_of_another_address_is_refused(client: httpx.AsyncClient, google: FakeGoogle) -> None:
    email, token = await provider_account("GOOGLE")
    nonce = (await confirm_nonce(client, token))["nonce"]
    refused = await set_first(client, token, googleIdToken=google.mint("somebody-else@example.com", nonce))
    assert refused.status_code == 400
    assert refused.headers["x-confirm-provider"] == "GOOGLE"
    assert refused.json()["detail"] == GOOGLE_AGAIN
    assert (await account_at(email)).passwordHash is None


async def test_a_proof_from_another_provider_is_refused_and_spends_nothing(
    client: httpx.AsyncClient, google: FakeGoogle, idp: FakeIdP
) -> None:
    email, token = await provider_account("YAHOO")
    nonce = (await confirm_nonce(client, token))["nonce"]
    refused = await set_first(client, token, googleIdToken=google.mint(email, nonce))
    assert refused.status_code == 400
    assert refused.headers["x-confirm-provider"] == "YAHOO"
    assert refused.json()["detail"] == YAHOO_AGAIN
    assert (await account_at(email)).passwordHash is None
    idp.issue(idp.sign(idp.yahoo_claims(email, raw_nonce=nonce)))
    accepted = await set_first(client, token, **login_body("YAHOO", raw_nonce=nonce))
    assert accepted.status_code == 200, accepted.text


async def test_a_reused_nonce_is_refused_and_redeems_nothing(client: httpx.AsyncClient, idp: FakeIdP) -> None:
    email, token = await provider_account("YAHOO")
    nonce = (await confirm_nonce(client, token))["nonce"]
    idp.issue(idp.sign(idp.yahoo_claims("someone-else@yahoo.com", raw_nonce=nonce)))
    assert (await set_first(client, token, **login_body("YAHOO", raw_nonce=nonce))).status_code == 400
    idp.issue(idp.sign(idp.yahoo_claims(email, raw_nonce=nonce)))
    reused = await set_first(client, token, **login_body("YAHOO", code="a-second-code", raw_nonce=nonce))
    assert reused.status_code == 400
    assert reused.headers["x-confirm-provider"] == "YAHOO"
    assert len(idp.redemptions) == 1
    assert (await account_at(email)).passwordHash is None


async def test_a_reused_google_nonce_is_refused(client: httpx.AsyncClient, google: FakeGoogle) -> None:
    email, token = await provider_account("GOOGLE")
    nonce = (await confirm_nonce(client, token))["nonce"]
    assert (
        await set_first(client, token, googleIdToken=google.mint("x@example.com", nonce))
    ).status_code == 400
    reused = await set_first(client, token, googleIdToken=google.mint(email, nonce))
    assert reused.status_code == 400
    assert reused.json()["detail"] == GOOGLE_AGAIN
    assert (await account_at(email)).passwordHash is None


async def test_a_stale_token_is_refused(client: httpx.AsyncClient, google: FakeGoogle) -> None:
    email, token = await provider_account("GOOGLE")
    nonce = (await confirm_nonce(client, token))["nonce"]
    refused = await set_first(
        client, token, googleIdToken=google.mint(email, nonce, iat=time.time() - 6 * 60)
    )
    assert refused.status_code == 400
    assert refused.headers["x-confirm-provider"] == "GOOGLE"
    assert (await account_at(email)).passwordHash is None


async def test_no_proof_is_asked_to_confirm_with_the_accounts_provider(client: httpx.AsyncClient) -> None:
    email, token = await provider_account("GOOGLE")
    refused = await set_first(client, token)
    assert refused.status_code == 400
    assert refused.headers["x-confirm-provider"] == "GOOGLE"
    assert refused.json()["detail"] == CONFIRM_GOOGLE
    assert (await account_at(email)).passwordHash is None


async def test_a_sign_in_nonce_does_not_confirm(client: httpx.AsyncClient, google: FakeGoogle) -> None:
    email, token = await provider_account("GOOGLE")
    sign_in = await client.post("/api/auth/google/nonce")
    assert sign_in.status_code == 200, sign_in.text
    refused = await set_first(client, token, googleIdToken=google.mint(email, sign_in.json()["nonce"]))
    assert refused.status_code == 400
    assert (await account_at(email)).passwordHash is None


async def test_a_two_step_account_is_asked_for_its_code_before_the_proof_is_spent(
    client: httpx.AsyncClient, google: FakeGoogle
) -> None:
    secret = two_factor.generate_secret()
    email, token = await provider_account("GOOGLE", two_factor_secret=secret)
    proof = google.mint(email, (await confirm_nonce(client, token))["nonce"])
    missing = await set_first(client, token, googleIdToken=proof)
    assert missing.status_code == 400
    assert missing.headers["x-two-factor-required"] == "1"
    answer = await set_first(client, token, googleIdToken=proof, twoFactorCode=code(secret))
    assert answer.status_code == 200, answer.text


async def recovery_codes_for(email: str, count: int) -> list[str]:
    codes = two_factor.generate_recovery_codes(count)
    hashes = await two_factor.hash_recovery_codes(codes)
    async with session_scope() as session:
        await session.execute(update(User).where(User.email == email).values(twoFactorRecoveryCodes=hashes))
    return codes


async def recovery_locked_until(email: str, until: datetime | None) -> None:
    async with session_scope() as session:
        await session.execute(
            update(User).where(User.email == email).values(twoFactorRecoveryLockedUntil=until)
        )


async def test_a_recovery_code_stands_in_for_the_authenticator_and_is_spent(
    client: httpx.AsyncClient, google: FakeGoogle
) -> None:
    email, token = await provider_account("GOOGLE", two_factor_secret=two_factor.generate_secret())
    first, _second = await recovery_codes_for(email, 2)
    proof = google.mint(email, (await confirm_nonce(client, token))["nonce"])
    answer = await set_first(client, token, googleIdToken=proof, twoFactorCode=first)
    assert answer.status_code == 200, answer.text
    account = await account_at(email)
    assert verify_password(NEW_PASSWORD, account.passwordHash)
    assert len(account.twoFactorRecoveryCodes) == 1


async def test_a_locked_second_factor_is_answered_429_before_the_proof_is_spent(
    client: httpx.AsyncClient, google: FakeGoogle
) -> None:
    email, token = await provider_account("GOOGLE", two_factor_secret=two_factor.generate_secret())
    (recovery,) = await recovery_codes_for(email, 1)
    await recovery_locked_until(email, datetime.now(UTC) + timedelta(minutes=10))
    proof = google.mint(email, (await confirm_nonce(client, token))["nonce"])
    locked = await set_first(client, token, googleIdToken=proof, twoFactorCode=recovery)
    assert (locked.status_code, locked.json()["detail"]) == (429, "Too many attempts. Try again later.")
    assert (await account_at(email)).passwordHash is None
    await recovery_locked_until(email, None)
    answer = await set_first(client, token, googleIdToken=proof, twoFactorCode=recovery)
    assert answer.status_code == 200, answer.text


async def test_a_password_account_still_needs_its_current_password(
    client: httpx.AsyncClient, google: FakeGoogle
) -> None:
    email = unique_email("first-password-has-one")
    await create_user(email, "RESEARCHER")
    signed_in = await client.post("/api/auth/login", json={"email": email, "password": PASSWORD})
    token = signed_in.json()["accessToken"]
    refused_nonce = await client.post("/api/auth/first-password/nonce", headers=bearer(token))
    assert refused_nonce.status_code == 409
    proof = google.mint(email, "a-nonce-that-was-never-issued")
    refused = await set_first(client, token, googleIdToken=proof)
    assert refused.status_code == 400
    assert refused.json()["detail"] == "Current password is incorrect"
    assert "x-confirm-provider" not in refused.headers
    changed = await set_first(client, token, currentPassword=PASSWORD)
    assert changed.status_code == 200, changed.text
    assert verify_password(NEW_PASSWORD, (await account_at(email)).passwordHash)


async def test_no_nonce_for_an_account_without_a_provider_or_a_provider_that_is_off(
    client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    _email, local = await provider_account("LOCAL")
    no_provider = await client.post("/api/auth/first-password/nonce", headers=bearer(local))
    assert no_provider.status_code == 400
    monkeypatch.setattr(get_settings(), "google_client_id", "")
    _email, google_only = await provider_account("GOOGLE")
    off = await client.post("/api/auth/first-password/nonce", headers=bearer(google_only))
    assert off.status_code == 404
