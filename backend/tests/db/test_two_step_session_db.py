import httpx
import pytest

from app.api.auth_session import SESSION_TOKEN_HEADER
from app.core.security import TOKEN_VERSION_CLAIM, decode_access_token

from .accounts import bearer, code, create_user, login, unique_email

pytestmark = pytest.mark.db


async def _version(client: httpx.AsyncClient, token: str) -> int:
    me = await client.get("/api/auth/me", headers=bearer(token))
    assert me.status_code == 200, me.text
    return int(decode_access_token(token)[TOKEN_VERSION_CLAIM])


async def test_turning_two_step_on_and_off_answers_the_one_session_that_still_works(
    client: httpx.AsyncClient,
) -> None:
    email = unique_email("two-step-session")
    await create_user(email, "RESEARCHER")
    first = await login(client, email)
    start = await _version(client, first)
    setup = await client.post("/api/auth/two-factor/setup", headers=bearer(first))
    assert setup.status_code == 200, setup.text

    enabled = await client.post(
        "/api/auth/two-factor/enable", headers=bearer(first), json={"code": code(setup.json()["secret"])}
    )
    assert enabled.status_code == 200, enabled.text
    second = enabled.headers[SESSION_TOKEN_HEADER]
    assert enabled.json()["accessToken"] == second
    assert (await client.get("/api/auth/me", headers=bearer(first))).status_code == 401
    assert await _version(client, second) == start + 1
    assert (await client.get("/api/auth/me", headers=bearer(second))).json()["twoFactorEnabled"] is True

    recovery = enabled.json()["recovery_codes"][0]
    disabled = await client.post(
        "/api/auth/two-factor/disable", headers=bearer(second), json={"code": recovery}
    )
    assert disabled.status_code == 200, disabled.text
    third = disabled.headers[SESSION_TOKEN_HEADER]
    assert disabled.json() == {"ok": True, "accessToken": third}
    assert (await client.get("/api/auth/me", headers=bearer(second))).status_code == 401
    assert await _version(client, third) == start + 2
    assert (await client.get("/api/auth/me", headers=bearer(third))).json()["twoFactorEnabled"] is False
