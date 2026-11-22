from collections.abc import AsyncIterator
from typing import Any

import httpx
import pytest
from sqlalchemy import update

from app.core import daily_allowances
from app.core.db import session_scope
from app.models import QuotaPolicy

from .accounts import bearer, code, create_user, login, unique_email

pytestmark = pytest.mark.db

NO_CAPS = {"VOICE_SECONDS": None, "IMAGE": None, "VIDEO": None}


@pytest.fixture
async def master(client: httpx.AsyncClient) -> AsyncIterator[dict[str, Any]]:
    email = unique_email("allowance-master")
    secret = await create_user(email, "MASTER_ADMIN", with_two_factor=True)
    assert secret is not None
    try:
        yield {"token": await login(client, email, secret), "secret": secret}
    finally:
        async with session_scope() as session:
            await session.execute(update(QuotaPolicy).values(perDay=None))


async def put_budget(
    client: httpx.AsyncClient, master: dict[str, Any], body: dict[str, Any]
) -> httpx.Response:
    sent = {**body, "twoFactorCode": code(master["secret"], 1)}
    return await client.put("/api/settings/ai-budget", headers=bearer(master["token"]), json=sent)


async def test_a_daily_allowance_is_set_on_the_budget_and_read_by_every_check(
    client: httpx.AsyncClient, master: dict[str, Any]
) -> None:
    shown = await client.get("/api/settings/ai-budget", headers=bearer(master["token"]))
    assert shown.status_code == 200, shown.text
    assert shown.json()["dailyAllowances"]["STUDENT"] == NO_CAPS
    saved = await put_budget(
        client, master, {"dailyAllowances": {"STUDENT": {"VOICE_SECONDS": 600, "IMAGE": 5}}}
    )
    assert saved.status_code == 200, saved.text
    assert saved.json()["dailyAllowances"]["STUDENT"] == {"VOICE_SECONDS": 600, "IMAGE": 5, "VIDEO": None}
    assert saved.json()["dailyAllowances"]["ARTISAN"] == NO_CAPS
    async with session_scope() as session:
        await daily_allowances.refresh_if_stale(session)
    assert daily_allowances.daily_allowance("STUDENT", "VOICE_SECONDS") == 600
    assert daily_allowances.daily_allowance("GUEST", "IMAGE") == 5
    assert daily_allowances.daily_allowance("ARTISAN", "VOICE_SECONDS") is None


async def test_a_master_admin_allowance_is_refused(client: httpx.AsyncClient, master: dict[str, Any]) -> None:
    capped = await put_budget(client, master, {"dailyAllowances": {"MASTER_ADMIN": {"IMAGE": 3}}})
    assert (capped.status_code, capped.json()["detail"]) == (422, "Master Admins have no caps.")


async def test_an_allowance_of_an_unknown_resource_is_refused(
    client: httpx.AsyncClient, master: dict[str, Any]
) -> None:
    unknown = await put_budget(client, master, {"dailyAllowances": {"STUDENT": {"TEXT_Q": 3}}})
    assert (unknown.status_code, unknown.json()["detail"]) == (422, "Unknown allowances: TEXT_Q")
