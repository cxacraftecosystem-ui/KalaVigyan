import importlib.util
from pathlib import Path
from types import ModuleType

import httpx
import pytest
from sqlalchemy import text

from app.core.db import session_scope

from .accounts import bearer, create_user, login, unique_email

pytestmark = pytest.mark.db

MIGRATION = Path(__file__).resolve().parents[2] / "migrations" / "versions" / "0046_contrast_preference.py"


def contrast_migration() -> ModuleType:
    spec = importlib.util.spec_from_file_location("contrast_preference", MIGRATION)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


async def reader_token(client: httpx.AsyncClient) -> str:
    email = unique_email("contrast")
    await create_user(email, "RESEARCHER")
    return await login(client, email)


async def test_a_new_reader_s_contrast_follows_the_device(client: httpx.AsyncClient) -> None:
    token = await reader_token(client)
    answer = await client.get("/api/preferences/me", headers=bearer(token))
    assert answer.status_code == 200, answer.text
    assert answer.json()["highContrast"] == "system"


@pytest.mark.parametrize("choice", ["standard", "high", "system"])
async def test_a_contrast_choice_is_kept_as_sent(client: httpx.AsyncClient, choice: str) -> None:
    token = await reader_token(client)
    saved = await client.put("/api/preferences/me", headers=bearer(token), json={"highContrast": choice})
    assert saved.status_code == 200, saved.text
    assert (await client.get("/api/preferences/me", headers=bearer(token))).json()["highContrast"] == choice


async def test_an_old_client_s_on_switch_is_kept_as_high(client: httpx.AsyncClient) -> None:
    token = await reader_token(client)
    saved = await client.put("/api/preferences/me", headers=bearer(token), json={"highContrast": True})
    assert saved.status_code == 200, saved.text
    assert saved.json()["highContrast"] == "high"


async def test_the_migration_turns_on_into_high_and_off_into_the_device() -> None:
    migration = contrast_migration()
    query = text(
        f'SELECT "highContrast" AS flag, {migration.CHOICE_FROM_FLAG} AS choice '
        'FROM (VALUES (true), (false)) AS flags("highContrast")'
    )
    async with session_scope() as session:
        rows = (await session.execute(query)).all()
    assert {row.flag: row.choice for row in rows} == {True: "high", False: "system"}


async def test_the_way_back_keeps_only_high_as_on() -> None:
    migration = contrast_migration()
    query = text(
        f'SELECT "highContrast" AS choice, {migration.FLAG_FROM_CHOICE} AS flag '
        "FROM (VALUES ('high'), ('standard'), ('system')) AS choices(\"highContrast\")"
    )
    async with session_scope() as session:
        rows = (await session.execute(query)).all()
    assert {row.choice: row.flag for row in rows} == {"high": True, "standard": False, "system": False}
