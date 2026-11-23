import uuid
from typing import Any

import httpx
import pytest
from sqlalchemy import select, text

from app.core.db import session_scope
from app.models import AccessRoster, Provider, RoutePolicy
from app.services import app_settings

from .accounts import PASSWORD, bearer, code, create_user, login, unique_email

pytestmark = pytest.mark.db

PROTECTED_TABLES = (
    "SELECT c.relname FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace "
    "WHERE n.nspname = 'public' AND c.relkind = 'r' AND NOT c.relrowsecurity "
    "AND c.relname NOT IN ('spatial_ref_sys', 'alembic_version')"
)
DEEPSEEK_KEY = "/api/secrets/DEEPSEEK_API_KEY"
DEEPSEEK_VALUE = "sk-test-value-0000-abcd"


async def test_schema_is_hardened_and_seeded() -> None:
    async with session_scope() as session:
        extensions = set((await session.execute(text("SELECT extname FROM pg_extension"))).scalars())
        assert {"vector", "postgis", "pg_trgm", "unaccent", "citext"} <= extensions
        assert (await session.execute(text(PROTECTED_TABLES))).scalars().all() == []
        providers = set((await session.execute(select(Provider.name))).scalars())
        assert providers == {"OPENAI", "GEMINI", "ANTHROPIC", "DEEPSEEK", "ELEVENLABS", "VOYAGE"}
        deepseek = (await session.execute(select(Provider).where(Provider.name == "DEEPSEEK"))).scalar_one()
        assert deepseek.dataClass == "PUBLIC_TEXT_ONLY"
        first_compose = (
            await session.execute(
                select(RoutePolicy.model).where(RoutePolicy.task == "COMPOSE", RoutePolicy.ordinal == 1)
            )
        ).scalar_one()
        assert first_compose == "claude-sonnet-5-5"
        caps = app_settings.public_view(await app_settings.load_all(session))
        assert [caps["monthlyCeilingUsd"], caps["mediaCapUsd"], caps["degradeAtFraction"]] == [None] * 3
        assert set(caps["roleDailyUsd"].values()) | set(caps["answerCapUsd"].values()) <= {None}
        assert set((await session.execute(select(RoutePolicy.maxOutputTokens))).scalars()) == {None}
    with pytest.raises(Exception, match="append-only"):
        async with session_scope() as session:
            await session.execute(text("INSERT INTO \"AuditLog\" (action) VALUES ('test.probe')"))
            await session.execute(
                text("UPDATE \"AuditLog\" SET action = 'changed' WHERE action = 'test.probe'")
            )


async def test_professor_cannot_reinstate_barred_access(
    client: httpx.AsyncClient, owner: dict[str, Any]
) -> None:
    professor = unique_email("professor")
    secret = await create_user(professor, "PROFESSOR", with_two_factor=True)
    token = await login(client, professor, secret)
    barred = unique_email("barred")
    async with session_scope() as session:
        row = AccessRoster(email=barred, status="SUSPENDED", admitRole="STUDENT")
        session.add(row)
        await session.flush()
        row_id = str(row.id)
    refused = await client.post(
        f"/api/access/roster/{row_id}/decision",
        headers=bearer(token),
        json={"decision": "APPROVE", "role": "STUDENT"},
    )
    assert refused.status_code == 403, refused.text
    async with session_scope() as session:
        assert (await session.get(AccessRoster, uuid.UUID(row_id))).status == "SUSPENDED"


async def test_google_nonce_is_single_use_by_hash() -> None:
    from app.services import auth_nonces

    async with session_scope() as session:
        raw, _expires = await auth_nonces.issue_nonce(session, purpose="GOOGLE_SIGN_IN")
    async with session_scope() as session:
        assert await auth_nonces.consume_nonce(session, raw, purpose="GOOGLE_SIGN_IN")
    async with session_scope() as session:
        assert not await auth_nonces.consume_nonce(session, raw, purpose="GOOGLE_SIGN_IN")
        assert not await auth_nonces.consume_nonce(session, "forged", purpose="GOOGLE_SIGN_IN")


async def test_the_owner_saves_a_key_only_with_a_fresh_code(
    client: httpx.AsyncClient, owner: dict[str, Any]
) -> None:
    token = owner["token"]
    listing = await client.get("/api/secrets", headers=bearer(token))
    assert listing.status_code == 200, listing.text
    keys = {entry["key"] for entry in listing.json()}
    assert {"GEMINI_API_KEY", "ANTHROPIC_API_KEY", "OPENAI_API_KEY", "DEEPSEEK_API_KEY"} <= keys
    no_code = await client.put(DEEPSEEK_KEY, headers=bearer(token), json={"value": DEEPSEEK_VALUE})
    assert no_code.status_code == 401
    assert no_code.headers["x-two-factor-required"] == "1"
    sent = {"value": DEEPSEEK_VALUE, "twoFactorCode": code(owner["secret"], 1)}
    saved = await client.put(DEEPSEEK_KEY, headers=bearer(token), json=sent)
    assert saved.status_code == 200, saved.text
    body = saved.json()
    assert (body["configured"], body["source"], body["hint"]) == (True, "database", "abcd")
    assert "sk-test-value" not in saved.text
    unknown = await client.put("/api/secrets/JWT_SECRET", headers=bearer(token), json={"value": "x" * 20})
    assert unknown.status_code == 404


async def test_the_owner_routes_tasks_and_reads_usage(
    client: httpx.AsyncClient, owner: dict[str, Any]
) -> None:
    token = owner["token"]
    routing = await client.get("/api/settings/ai-routing/COMPOSE", headers=bearer(token))
    assert routing.status_code == 200, routing.text
    assert routing.json()["routes"][0]["model"] == "claude-sonnet-5-5"
    assert all(m["provider"] != "DEEPSEEK" for m in routing.json()["availableModels"])
    deepseek = {"routes": [{"provider": "DEEPSEEK", "model": "deepseek-v4-pro"}]}
    refused = await client.put("/api/settings/ai-routing/COMPOSE", headers=bearer(token), json=deepseek)
    assert refused.status_code == 422
    routes = [
        {"provider": "DEEPSEEK", "model": "deepseek-flash"},
        {"provider": "GEMINI", "model": "gemini-3.5-flash-lite"},
    ]
    reordered = await client.put(
        "/api/settings/ai-routing/WEB_READ", headers=bearer(token), json={"routes": routes}
    )
    assert reordered.status_code == 200, reordered.text
    assert [r["provider"] for r in reordered.json()["routes"]] in (
        ["DEEPSEEK", "GEMINI"],
        ["GEMINI", "DEEPSEEK"],
    )
    everything = await client.get("/api/settings/ai-routing", headers=bearer(token))
    assert {t["task"] for t in everything.json()["tasks"]} >= {"PLAN", "COMPOSE", "EMBED", "IMAGE", "VIDEO"}
    summary = await client.get("/api/usage/summary", headers=bearer(token))
    assert summary.status_code == 200, summary.text
    assert (summary.json()["monthlyCeilingUsd"], summary.json()["mediaCapUsd"]) == (None, None)


async def test_suspension_ends_sessions(client: httpx.AsyncClient, owner: dict[str, Any]) -> None:
    email = unique_email("researcher")
    await create_user(email, "RESEARCHER")
    researcher_token = await login(client, email)
    me = (await client.get("/api/auth/me", headers=bearer(researcher_token))).json()

    changed = await client.patch(
        f"/api/users/{me['id']}", headers=bearer(owner["token"]), json={"role": "STUDENT"}
    )
    assert changed.status_code == 200, changed.text
    assert (await client.get("/api/auth/me", headers=bearer(researcher_token))).status_code == 401

    researcher_token = await login(client, email)
    suspended = await client.post(f"/api/users/{me['id']}/suspend", headers=bearer(owner["token"]))
    assert suspended.status_code == 200, suspended.text
    assert suspended.json()["accessStatus"] == "SUSPENDED"
    assert (await client.get("/api/auth/me", headers=bearer(researcher_token))).status_code == 401
    again = await client.post("/api/auth/login", json={"email": email, "password": PASSWORD})
    assert again.status_code == 403
    assert again.headers["x-access-status"] == "SUSPENDED"
