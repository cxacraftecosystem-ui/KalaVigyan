import time
from collections.abc import Awaitable, Callable
from typing import Any

import httpx
import jwt
import pytest
from sqlalchemy import select

from app.api.auth_session import SESSION_TOKEN_HEADER
from app.core.config import get_settings
from app.core.db import session_scope
from app.core.security import TOKEN_VERSION_CLAIM, decode_access_token, session_id_of
from app.models import AccessRoster, SiteSession, User
from app.services import credential_links

from .accounts import PASSWORD, bearer, create_user, login, unique_email

pytestmark = pytest.mark.db

DAY = 24 * 60 * 60
YEAR = 365 * DAY
NEW_PASSWORD = "a-new-password-for-a-long-session"


async def person(client: httpx.AsyncClient, role: str = "RESEARCHER") -> tuple[str, str]:
    email = unique_email("long-session")
    await create_user(email, role)
    return email, await login(client, email)


async def admin(client: httpx.AsyncClient) -> str:
    email = unique_email("long-session-admin")
    secret = await create_user(email, "ADMIN", with_two_factor=True)
    return await login(client, email, secret)


async def renewed(client: httpx.AsyncClient, token: str) -> str:
    answer = await client.post("/api/auth/renew", headers=bearer(token))
    assert answer.status_code == 200, answer.text
    return answer.headers[SESSION_TOKEN_HEADER]


async def works(client: httpx.AsyncClient, token: str) -> bool:
    status = (await client.get("/api/auth/me", headers=bearer(token))).status_code
    assert status in (200, 401)
    return status == 200


async def renews(client: httpx.AsyncClient, token: str) -> bool:
    status = (await client.post("/api/auth/renew", headers=bearer(token))).status_code
    assert status in (200, 401)
    return status == 200


def aged(token: str, *, issued_days_ago: float, expires_in_days: float) -> str:
    claims = decode_access_token(token)
    now = time.time()
    claims["iat"] = now - issued_days_ago * DAY
    claims["exp"] = int(now + expires_in_days * DAY)
    settings = get_settings()
    return jwt.encode(claims, settings.jwt_secret, algorithm=settings.jwt_algorithm)


async def site_session(token: str) -> SiteSession:
    session_id = session_id_of(decode_access_token(token))
    assert session_id is not None
    async with session_scope() as session:
        found = await session.get(SiteSession, session_id)
        assert found is not None
        return found


async def test_signing_in_opens_a_session_of_a_year_and_using_it_renews_it_for_another(
    client: httpx.AsyncClient,
) -> None:
    _email, token = await person(client)
    claims = decode_access_token(token)
    assert YEAR - 60 <= claims["exp"] - claims["iat"] <= YEAR + 60
    old = aged(token, issued_days_ago=300, expires_in_days=65)
    assert await works(client, old)
    fresh = await renewed(client, old)
    again = decode_access_token(fresh)
    assert session_id_of(again) == session_id_of(claims)
    assert again["exp"] - time.time() > YEAR - 60
    assert again["exp"] > decode_access_token(old)["exp"] + 299 * DAY
    assert await works(client, fresh) and await works(client, old)
    record = await site_session(fresh)
    assert record.endedAt is None and record.renewedAt > record.createdAt


async def test_an_abandoned_session_expires_and_cannot_be_renewed(client: httpx.AsyncClient) -> None:
    _email, token = await person(client)
    lapsed = aged(token, issued_days_ago=366, expires_in_days=-1)
    assert not await works(client, lapsed)
    assert not await renews(client, lapsed)
    nearly = aged(token, issued_days_ago=364, expires_in_days=1)
    assert await renews(client, nearly)


async def test_signing_out_ends_that_session_and_every_token_it_renewed_but_not_the_others(
    client: httpx.AsyncClient,
) -> None:
    email, phone = await person(client)
    laptop = await login(client, email)
    renewed_phone = await renewed(client, phone)
    assert await works(client, phone) and await works(client, renewed_phone)
    signed_out = await client.post("/api/auth/logout", headers=bearer(renewed_phone))
    assert signed_out.status_code == 200 and signed_out.json() == {"ok": True}
    assert not await works(client, phone)
    assert not await works(client, renewed_phone)
    assert not await renews(client, phone)
    assert await works(client, laptop) and await renews(client, laptop)
    assert (await site_session(phone)).endedAt is not None
    assert (await client.post("/api/auth/logout")).json() == {"ok": True}


async def test_a_session_from_before_this_release_stands_and_renews_into_one_with_an_id(
    client: httpx.AsyncClient,
) -> None:
    email, _token = await person(client)
    async with session_scope() as session:
        user = (await session.execute(select(User).where(User.email == email))).scalar_one()
        claims = {"sub": str(user.id), TOKEN_VERSION_CLAIM: user.tokenVersion, "email": email}
    settings = get_settings()
    now = time.time()
    legacy = jwt.encode(
        {**claims, "iat": now - 2 * DAY, "exp": int(now + 5 * DAY)},
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
    )
    assert await works(client, legacy)
    moved = await renewed(client, legacy)
    assert session_id_of(decode_access_token(moved)) is not None
    assert await works(client, moved)
    await client.post("/api/auth/logout", headers=bearer(moved))
    assert not await works(client, moved)


async def _user_id(email: str) -> str:
    async with session_scope() as session:
        return str((await session.execute(select(User.id).where(User.email == email))).scalar_one())


async def _roster_id(email: str) -> str:
    async with session_scope() as session:
        found = await session.execute(select(AccessRoster.id).where(AccessRoster.email == email))
        return str(found.scalar_one())


async def _send(client: httpx.AsyncClient, token: str, method: str, path: str, body: Any = None) -> None:
    answer = await client.request(method, path, headers=bearer(token), json=body)
    assert answer.status_code < 300, answer.text


async def suspended(client: httpx.AsyncClient, email: str) -> None:
    await _send(client, await admin(client), "POST", f"/api/users/{await _user_id(email)}/suspend")


async def taken_off_the_roster(client: httpx.AsyncClient, email: str) -> None:
    await _send(client, await admin(client), "DELETE", f"/api/access/roster/{await _roster_id(email)}")


async def refused(client: httpx.AsyncClient, email: str) -> None:
    path = f"/api/access/roster/{await _roster_id(email)}/decision"
    await _send(client, await admin(client), "POST", path, {"decision": "REJECT"})


async def given_a_new_role(client: httpx.AsyncClient, email: str) -> None:
    path = f"/api/users/{await _user_id(email)}"
    await _send(client, await admin(client), "PATCH", path, {"role": "STUDENT"})


async def signed_out_everywhere(client: httpx.AsyncClient, email: str) -> None:
    path = f"/api/users/{await _user_id(email)}/sign-out-everywhere"
    await _send(client, await admin(client), "POST", path)


async def password_reset(client: httpx.AsyncClient, email: str) -> None:
    async with session_scope() as session:
        user = (await session.execute(select(User).where(User.email == email))).scalar_one()
        _issued, raw = await credential_links.issue_link(
            session, user=user, purpose="RESET", issued_by_id=None
        )
    answer = await client.post("/api/auth/set-password", json={"token": raw, "password": NEW_PASSWORD})
    assert answer.status_code == 200, answer.text


Cause = Callable[[httpx.AsyncClient, str], Awaitable[None]]


@pytest.mark.parametrize(
    "cause",
    [suspended, taken_off_the_roster, refused, given_a_new_role, signed_out_everywhere, password_reset],
)
async def test_each_revocation_ends_a_renewed_session_at_once(
    client: httpx.AsyncClient, cause: Cause
) -> None:
    email, token = await person(client)
    long_lived = await renewed(client, aged(token, issued_days_ago=200, expires_in_days=165))
    assert await works(client, token) and await works(client, long_lived)
    await cause(client, email)
    for each in (token, long_lived):
        assert not await works(client, each)
        assert not await renews(client, each)


async def test_a_password_change_ends_the_other_sessions_and_keeps_the_changer_s_own(
    client: httpx.AsyncClient,
) -> None:
    email, phone = await person(client)
    laptop = await login(client, email)
    changed = await client.post(
        "/api/auth/change-password",
        headers=bearer(laptop),
        json={"currentPassword": PASSWORD, "newPassword": NEW_PASSWORD},
    )
    assert changed.status_code == 200, changed.text
    kept = changed.headers[SESSION_TOKEN_HEADER]
    assert session_id_of(decode_access_token(kept)) == session_id_of(decode_access_token(laptop))
    assert await works(client, kept) and await renews(client, kept)
    assert not await works(client, phone) and not await works(client, laptop)
