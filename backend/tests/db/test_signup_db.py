from typing import Any

import httpx
import pytest
from sqlalchemy import select

from app.core.db import session_scope
from app.core.security import hash_password
from app.models import AccessRoster, User

from .accounts import PASSWORD, bearer, create_user, login, unique_email

pytestmark = pytest.mark.db

Outbox = dict[str, list[Any]]


@pytest.fixture
def outbox(monkeypatch: pytest.MonkeyPatch) -> Outbox:
    from app.services import credential_links, mailer

    box: Outbox = {"mail": [], "tokens": []}
    issue = credential_links.issue_link

    async def capture_issue(*args: Any, **kwargs: Any) -> Any:
        issued, raw = await issue(*args, **kwargs)
        box["tokens"].append((kwargs["user"].email, raw))
        return issued, raw

    async def capture_send(mail: Any) -> bool:
        box["mail"].append(mail)
        return True

    monkeypatch.setattr(mailer, "mail_configured", lambda: True)
    monkeypatch.setattr(mailer, "send", capture_send)
    monkeypatch.setattr(credential_links, "issue_link", capture_issue)
    return box


def sign_up_body(email: str, name: str = "New Student", role: str = "STUDENT") -> dict[str, Any]:
    return {
        "email": email,
        "name": name,
        "requestedRole": role,
        "ageAttested": True,
        "privacyNoticeVersion": "2026-11-16",
    }


def token_for(box: Outbox, email: str) -> str:
    sent = [raw for address, raw in box["tokens"] if address == email]
    assert sent, f"no link was issued for {email}"
    return sent[-1]


async def signed_up_and_confirmed(client: httpx.AsyncClient, outbox: Outbox) -> str:
    applicant = unique_email("student")
    response = await client.post("/api/auth/signup", json=sign_up_body(applicant))
    assert response.status_code == 202, response.text
    assert response.json() == {"status": "EMAIL_SENT", "email": applicant}
    assert [mail.to for mail in outbox["mail"]] == [applicant]
    async with session_scope() as session:
        assert await session.scalar(select(AccessRoster).where(AccessRoster.email == applicant)) is None
    no_password = await client.post("/api/auth/login", json={"email": applicant, "password": PASSWORD})
    assert no_password.status_code == 401
    assert no_password.headers["x-sign-in-hint"] == "PASSWORD_NOT_SET"
    set_password = {"token": token_for(outbox, applicant), "password": PASSWORD}
    confirmed = await client.post("/api/auth/set-password", json=set_password)
    assert confirmed.status_code == 200, confirmed.text
    refused = await client.post("/api/auth/login", json={"email": applicant, "password": PASSWORD})
    assert refused.status_code == 403
    assert refused.headers["x-access-status"] == "PENDING"
    return applicant


async def approved_by_a_professor(client: httpx.AsyncClient, applicant: str) -> None:
    professor = unique_email("professor")
    token = await login(client, professor, await create_user(professor, "PROFESSOR", with_two_factor=True))
    count = await client.get("/api/access/roster/pending-count", headers=bearer(token))
    assert count.status_code == 200
    assert count.json()["pending"] >= 1
    pending = {"status": "PENDING", "search": applicant}
    listing = await client.get("/api/access/roster", headers=bearer(token), params=pending)
    assert listing.status_code == 200, listing.text
    rows = listing.json()["items"]
    assert [row["email"] for row in rows] == [applicant]
    assert listing.json()["assignableRoles"] == ["RESEARCHER", "ARTISAN", "STUDENT"]
    decision = f"/api/access/roster/{rows[0]['id']}/decision"
    too_high = await client.post(
        decision, headers=bearer(token), json={"decision": "APPROVE", "role": "PROFESSOR"}
    )
    assert too_high.status_code == 403
    approved = await client.post(
        decision, headers=bearer(token), json={"decision": "APPROVE", "role": "STUDENT"}
    )
    assert approved.status_code == 200, approved.text
    assert approved.json()["status"] == "ACTIVE"
    assert approved.json()["decidedByName"]


async def test_signup_waits_for_approval(client: httpx.AsyncClient, outbox: Outbox) -> None:
    applicant = await signed_up_and_confirmed(client, outbox)
    await approved_by_a_professor(client, applicant)
    student_token = await login(client, applicant)
    me = (await client.get("/api/auth/me", headers=bearer(student_token))).json()
    assert me["role"] == "STUDENT"
    assert "ASK_STANDARD" in me["capabilities"]
    assert "MARK_CLAIM_LEVEL" not in me["capabilities"]
    assert "passwordHash" not in me
    forbidden = await client.get("/api/users", headers=bearer(student_token))
    assert forbidden.status_code == 403


async def rostered_account(email: str) -> User:
    async with session_scope() as session:
        account = await session.scalar(select(User).where(User.email == email))
    assert account is not None
    return account


async def test_signup_cannot_take_over_a_rostered_address(
    client: httpx.AsyncClient, owner: dict[str, Any], outbox: Outbox
) -> None:
    victim = unique_email("victim")
    rostered = {"email": victim, "role": "PROFESSOR"}
    added = await client.post("/api/access/roster", headers=bearer(owner["token"]), json=rostered)
    assert added.status_code == 201, added.text
    attempt = await client.post("/api/auth/signup", json=sign_up_body(victim, "Attacker", "PROFESSOR"))
    baseline = await client.post("/api/auth/signup", json=sign_up_body(unique_email("fresh")))
    assert attempt.status_code == baseline.status_code == 202
    assert set(attempt.json()) == set(baseline.json())
    repeat = await client.post("/api/auth/signup", json=sign_up_body(victim, "Attacker", "PROFESSOR"))
    assert (repeat.status_code, repeat.json()) == (202, {"status": "EMAIL_SENT", "email": victim})
    account = await rostered_account(victim)
    assert (account.passwordHash, account.emailVerifiedAt) == (None, None)
    assert account.role != "PROFESSOR"
    for password in (PASSWORD, "attacker-chosen-password"):
        refused = await client.post("/api/auth/login", json={"email": victim, "password": password})
        assert refused.status_code == 401
    async with session_scope() as session:
        (await session.scalar(select(User).where(User.email == victim))).passwordHash = hash_password(
            PASSWORD
        )
    unverified = await client.post("/api/auth/login", json={"email": victim, "password": PASSWORD})
    assert (unverified.status_code, unverified.headers["x-sign-in-hint"]) == (401, "EMAIL_UNVERIFIED")
    owned = {"token": token_for(outbox, victim), "password": "owner-chosen-password"}
    confirmed = await client.post("/api/auth/set-password", json=owned)
    assert confirmed.status_code == 200, confirmed.text
    account = await rostered_account(victim)
    assert account.emailVerifiedAt is not None and account.role == "PROFESSOR"
    signed_in = await client.post(
        "/api/auth/login", json={"email": victim, "password": "owner-chosen-password"}
    )
    assert signed_in.status_code == 200, signed_in.text
