from collections.abc import AsyncIterator
from typing import Any

import httpx
import pytest
from sqlalchemy import delete, select

from app.core.db import session_scope
from app.models import AppSetting
from app.services import app_settings

from .accounts import bearer, code, create_user, login, unique_email

pytestmark = pytest.mark.db

CAPS_SAVED_BEFORE_ADMINS_AND_ARTISANS = {
    "STUDENT": 0.5,
    "RESEARCHER": 3.0,
    "PROFESSOR": 5.0,
    "MASTER_ADMIN": None,
}


async def signed_in(client: httpx.AsyncClient, role: str) -> dict[str, Any]:
    email = unique_email(f"role-caps-{role.lower().replace('_', '-')}")
    secret = await create_user(email, role, with_two_factor=True)
    assert secret is not None
    return {"token": await login(client, email, secret), "secret": secret}


async def stored_role_caps() -> Any:
    async with session_scope() as session:
        return await session.scalar(
            select(AppSetting.value).where(AppSetting.key == app_settings.ROLE_DAILY_USD)
        )


@pytest.fixture
async def caps_saved_before_two_roles() -> AsyncIterator[None]:
    before = await stored_role_caps()
    async with session_scope() as session:
        await app_settings.set_value(
            session, app_settings.ROLE_DAILY_USD, CAPS_SAVED_BEFORE_ADMINS_AND_ARTISANS
        )
    try:
        yield
    finally:
        async with session_scope() as session:
            if before is None:
                await session.execute(delete(AppSetting).where(AppSetting.key == app_settings.ROLE_DAILY_USD))
            else:
                await app_settings.set_value(session, app_settings.ROLE_DAILY_USD, before)


@pytest.mark.usefixtures("caps_saved_before_two_roles")
async def test_a_role_left_out_of_the_stored_caps_keeps_its_own_cap_and_a_partial_update_keeps_the_rest(
    client: httpx.AsyncClient,
) -> None:
    admin = await signed_in(client, "ADMIN")
    mine = (await client.get("/api/usage/me", headers=bearer(admin["token"]))).json()
    assert mine["dailyCapUsd"] is None
    master = await signed_in(client, "MASTER_ADMIN")
    shown = await client.get("/api/settings/ai-budget", headers=bearer(master["token"]))
    assert shown.status_code == 200, shown.text
    every_role = {**CAPS_SAVED_BEFORE_ADMINS_AND_ARTISANS, "ADMIN": None, "ARTISAN": None}
    assert shown.json()["roleDailyUsd"] == every_role
    saved = await client.put(
        "/api/settings/ai-budget",
        headers=bearer(master["token"]),
        json={"roleDailyUsd": {"PROFESSOR": 2.0}, "twoFactorCode": code(master["secret"], 1)},
    )
    assert saved.status_code == 200, saved.text
    assert saved.json()["roleDailyUsd"] == {**every_role, "PROFESSOR": 2.0}
    assert await stored_role_caps() == {**every_role, "PROFESSOR": 2.0}
