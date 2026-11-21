import os
import uuid
from decimal import Decimal
from typing import Any

import httpx
import pytest
from sqlalchemy import func, select, text

from app.core.db import session_scope
from app.core.security import hash_password
from app.models import AccessRoster, Provider, RoutePolicy, UsageEvent, User
from app.providers import router as ai_router
from app.providers.base import Adapter, ChatResult, ProviderError
from app.services import app_settings, two_factor

from .accounts import PASSWORD, bearer, code, create_user, login, unique_email

pytestmark = pytest.mark.db

MASTER_EMAIL = os.environ["MASTER_ADMIN_EMAIL"].lower()


@pytest.fixture(scope="session")
async def master(client: httpx.AsyncClient) -> dict[str, Any]:
    async with session_scope() as session:
        existing = (
            await session.execute(select(User).where(User.email == MASTER_EMAIL))
        ).scalar_one_or_none()
        if existing is None:
            session.add(
                User(
                    email=MASTER_EMAIL,
                    name="Owner",
                    passwordHash=hash_password(PASSWORD),
                    role="MASTER_ADMIN",
                )
            )
    token = await login(client, MASTER_EMAIL)
    me = (await client.get("/api/auth/me", headers=bearer(token))).json()
    assert me["twoFactorSetupRequired"] is True
    gated = await client.get("/api/secrets", headers=bearer(token))
    assert gated.status_code == 403
    assert gated.headers["x-two-factor-setup-required"] == "1"
    setup = await client.post("/api/auth/two-factor/setup", headers=bearer(token))
    assert setup.status_code == 200, setup.text
    secret = setup.json()["secret"]
    enabled = await client.post(
        "/api/auth/two-factor/enable", headers=bearer(token), json={"code": code(secret)}
    )
    assert enabled.status_code == 200, enabled.text
    assert len(enabled.json()["recovery_codes"]) == two_factor.RECOVERY_CODE_COUNT
    stale = await client.get("/api/auth/me", headers=bearer(token))
    assert stale.status_code == 401
    return {"token": enabled.json()["accessToken"], "secret": secret}


async def test_schema_is_hardened_and_seeded() -> None:
    async with session_scope() as session:
        extensions = set((await session.execute(text("SELECT extname FROM pg_extension"))).scalars())
        assert {"vector", "postgis", "pg_trgm", "unaccent", "citext"} <= extensions
        unprotected = (
            (
                await session.execute(
                    text(
                        "SELECT c.relname FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace "
                        "WHERE n.nspname = 'public' AND c.relkind = 'r' AND NOT c.relrowsecurity "
                        "AND c.relname NOT IN ('spatial_ref_sys', 'alembic_version')"
                    )
                )
            )
            .scalars()
            .all()
        )
        assert unprotected == []
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


@pytest.fixture
def outbox(monkeypatch: pytest.MonkeyPatch) -> dict[str, list[Any]]:
    from app.services import credential_links, mailer

    box: dict[str, list[Any]] = {"mail": [], "tokens": []}
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


def token_for(box: dict[str, list[Any]], email: str) -> str:
    sent = [raw for address, raw in box["tokens"] if address == email]
    assert sent, f"no link was issued for {email}"
    return sent[-1]


async def test_signup_waits_for_approval(client: httpx.AsyncClient, outbox: dict[str, list[Any]]) -> None:
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

    confirmed = await client.post(
        "/api/auth/set-password", json={"token": token_for(outbox, applicant), "password": PASSWORD}
    )
    assert confirmed.status_code == 200, confirmed.text

    refused = await client.post("/api/auth/login", json={"email": applicant, "password": PASSWORD})
    assert refused.status_code == 403
    assert refused.headers["x-access-status"] == "PENDING"

    professor = unique_email("professor")
    secret = await create_user(professor, "PROFESSOR", with_two_factor=True)
    token = await login(client, professor, secret)

    count = await client.get("/api/access/roster/pending-count", headers=bearer(token))
    assert count.status_code == 200
    assert count.json()["pending"] >= 1

    listing = await client.get(
        "/api/access/roster", headers=bearer(token), params={"status": "PENDING", "search": applicant}
    )
    assert listing.status_code == 200, listing.text
    rows = listing.json()["items"]
    assert [row["email"] for row in rows] == [applicant]
    assert listing.json()["assignableRoles"] == ["RESEARCHER", "ARTISAN", "STUDENT"]

    too_high = await client.post(
        f"/api/access/roster/{rows[0]['id']}/decision",
        headers=bearer(token),
        json={"decision": "APPROVE", "role": "PROFESSOR"},
    )
    assert too_high.status_code == 403

    approved = await client.post(
        f"/api/access/roster/{rows[0]['id']}/decision",
        headers=bearer(token),
        json={"decision": "APPROVE", "role": "STUDENT"},
    )
    assert approved.status_code == 200, approved.text
    assert approved.json()["status"] == "ACTIVE"
    assert approved.json()["decidedByName"]

    student_token = await login(client, applicant)
    me = (await client.get("/api/auth/me", headers=bearer(student_token))).json()
    assert me["role"] == "STUDENT"
    assert "ASK_STANDARD" in me["capabilities"]
    assert "MARK_CLAIM_LEVEL" not in me["capabilities"]
    assert "passwordHash" not in me

    forbidden = await client.get("/api/users", headers=bearer(student_token))
    assert forbidden.status_code == 403


async def test_signup_cannot_take_over_a_rostered_address(
    client: httpx.AsyncClient, master: dict[str, Any], outbox: dict[str, list[Any]]
) -> None:
    victim = unique_email("victim")
    added = await client.post(
        "/api/access/roster",
        headers=bearer(master["token"]),
        json={"email": victim, "role": "PROFESSOR"},
    )
    assert added.status_code == 201, added.text

    fresh = unique_email("fresh")
    attempt = await client.post("/api/auth/signup", json=sign_up_body(victim, "Attacker", "PROFESSOR"))
    baseline = await client.post("/api/auth/signup", json=sign_up_body(fresh))
    assert attempt.status_code == baseline.status_code == 202
    assert set(attempt.json()) == set(baseline.json())
    repeat = await client.post("/api/auth/signup", json=sign_up_body(victim, "Attacker", "PROFESSOR"))
    assert repeat.status_code == 202
    assert repeat.json() == {"status": "EMAIL_SENT", "email": victim}

    async with session_scope() as session:
        account = await session.scalar(select(User).where(User.email == victim))
        assert account is not None
        assert account.passwordHash is None
        assert account.emailVerifiedAt is None
        assert account.role != "PROFESSOR"

    for password in (PASSWORD, "attacker-chosen-password"):
        refused = await client.post("/api/auth/login", json={"email": victim, "password": password})
        assert refused.status_code == 401

    async with session_scope() as session:
        account = await session.scalar(select(User).where(User.email == victim))
        account.passwordHash = hash_password(PASSWORD)
    unverified = await client.post("/api/auth/login", json={"email": victim, "password": PASSWORD})
    assert unverified.status_code == 401
    assert unverified.headers["x-sign-in-hint"] == "EMAIL_UNVERIFIED"

    owner_password = "owner-chosen-password"
    confirmed = await client.post(
        "/api/auth/set-password", json={"token": token_for(outbox, victim), "password": owner_password}
    )
    assert confirmed.status_code == 200, confirmed.text
    async with session_scope() as session:
        account = await session.scalar(select(User).where(User.email == victim))
        assert account.emailVerifiedAt is not None
        assert account.role == "PROFESSOR"
    signed_in = await client.post("/api/auth/login", json={"email": victim, "password": owner_password})
    assert signed_in.status_code == 200, signed_in.text


async def test_professor_cannot_reinstate_barred_access(
    client: httpx.AsyncClient, master: dict[str, Any]
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


async def test_master_manages_keys_routing_and_usage(
    client: httpx.AsyncClient, master: dict[str, Any]
) -> None:
    token = master["token"]
    listing = await client.get("/api/secrets", headers=bearer(token))
    assert listing.status_code == 200, listing.text
    keys = {entry["key"] for entry in listing.json()}
    assert {"GEMINI_API_KEY", "ANTHROPIC_API_KEY", "OPENAI_API_KEY", "DEEPSEEK_API_KEY"} <= keys

    no_code = await client.put(
        "/api/secrets/DEEPSEEK_API_KEY", headers=bearer(token), json={"value": "sk-test-value-0000-abcd"}
    )
    assert no_code.status_code == 401
    assert no_code.headers["x-two-factor-required"] == "1"

    saved = await client.put(
        "/api/secrets/DEEPSEEK_API_KEY",
        headers=bearer(token),
        json={"value": "sk-test-value-0000-abcd", "twoFactorCode": code(master["secret"], 1)},
    )
    assert saved.status_code == 200, saved.text
    body = saved.json()
    assert body["configured"] is True
    assert body["source"] == "database"
    assert body["hint"] == "abcd"
    assert "sk-test-value" not in saved.text

    unknown = await client.put("/api/secrets/JWT_SECRET", headers=bearer(token), json={"value": "x" * 20})
    assert unknown.status_code == 404

    routing = await client.get("/api/settings/ai-routing/COMPOSE", headers=bearer(token))
    assert routing.status_code == 200, routing.text
    assert routing.json()["routes"][0]["model"] == "claude-sonnet-5-5"
    assert all(m["provider"] != "DEEPSEEK" for m in routing.json()["availableModels"])

    refused = await client.put(
        "/api/settings/ai-routing/COMPOSE",
        headers=bearer(token),
        json={"routes": [{"provider": "DEEPSEEK", "model": "deepseek-v4-pro"}]},
    )
    assert refused.status_code == 422

    reordered = await client.put(
        "/api/settings/ai-routing/WEB_READ",
        headers=bearer(token),
        json={
            "routes": [
                {"provider": "DEEPSEEK", "model": "deepseek-flash"},
                {"provider": "GEMINI", "model": "gemini-3.5-flash-lite"},
            ]
        },
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


async def test_suspension_ends_sessions(client: httpx.AsyncClient, master: dict[str, Any]) -> None:
    email = unique_email("researcher")
    await create_user(email, "RESEARCHER")
    researcher_token = await login(client, email)
    me = (await client.get("/api/auth/me", headers=bearer(researcher_token))).json()

    changed = await client.patch(
        f"/api/users/{me['id']}", headers=bearer(master["token"]), json={"role": "STUDENT"}
    )
    assert changed.status_code == 200, changed.text
    assert (await client.get("/api/auth/me", headers=bearer(researcher_token))).status_code == 401

    researcher_token = await login(client, email)
    suspended = await client.post(f"/api/users/{me['id']}/suspend", headers=bearer(master["token"]))
    assert suspended.status_code == 200, suspended.text
    assert suspended.json()["accessStatus"] == "SUSPENDED"
    assert (await client.get("/api/auth/me", headers=bearer(researcher_token))).status_code == 401
    again = await client.post("/api/auth/login", json={"email": email, "password": PASSWORD})
    assert again.status_code == 403
    assert again.headers["x-access-status"] == "SUSPENDED"


class FakeAdapter(Adapter):
    failing_providers: set[str] = set()

    async def chat(self, req: Any) -> ChatResult:
        if self.preset in self.failing_providers:
            raise ProviderError("busy", retryable=True, status=429, kind="rate_limit", retry_after=30)
        return ChatResult(
            text=f"answer from {self.preset}", input_tokens=1000, output_tokens=200, latency_ms=5
        )

    async def list_models(self) -> list[dict]:
        return []


def fake_build_adapter(**kwargs: Any) -> Adapter:
    return FakeAdapter(api_key="k", base_url=None, preset=kwargs["preset"], extra={}, learned={})


async def test_router_falls_back_records_usage_and_enforces_ceiling(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ai_router, "build_adapter", fake_build_adapter)
    FakeAdapter.failing_providers = {"gemini"}
    user_email = unique_email("router")
    await create_user(user_email, "RESEARCHER")
    async with session_scope() as session:
        user_id = (await session.execute(select(User.id).where(User.email == user_email))).scalar_one()
    principal = ai_router.Principal(user_id=user_id, role="RESEARCHER")

    result = await ai_router.run(
        "PLAN", system="plan", user="what mordant does ajrakh use?", principal=principal
    )
    assert result.provider == "ANTHROPIC"
    assert result.model == "claude-haiku-5-5"
    assert result.cost_usd > 0
    assert [a["outcome"] for a in result.attempts] == ["rate_limit", "OK"]

    async with session_scope() as session:
        rows = (
            await session.execute(
                select(UsageEvent.outcome, UsageEvent.provider, UsageEvent.costUsd)
                .where(UsageEvent.userId == user_id)
                .order_by(UsageEvent.createdAt)
            )
        ).all()
    assert [(r[0], r[1]) for r in rows] == [("ERROR", "GEMINI"), ("OK", "ANTHROPIC")]
    assert rows[1][2] == result.cost_usd

    async with session_scope() as session:
        await app_settings.set_value(session, app_settings.MONTHLY_CEILING_USD, 0.000001)
    try:
        with pytest.raises(ai_router.RouterError) as refused:
            await ai_router.run("PLAN", system="plan", user="again", principal=principal)
        assert refused.value.kind == "ceiling"
        assert refused.value.reason == "MONTHLY_CEILING"
        async with session_scope() as session:
            refusals = (
                await session.execute(
                    select(func.count())
                    .select_from(UsageEvent)
                    .where(UsageEvent.userId == user_id, UsageEvent.outcome == "REFUSED_CEILING")
                )
            ).scalar_one()
        assert refusals == 1
    finally:
        async with session_scope() as session:
            await app_settings.set_value(session, app_settings.MONTHLY_CEILING_USD, None)


async def test_a_student_is_uncapped_by_default_and_a_set_role_cap_refuses(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(ai_router, "build_adapter", fake_build_adapter)
    FakeAdapter.failing_providers = set()
    email = unique_email("capped")
    await create_user(email, "STUDENT")
    async with session_scope() as session:
        user_id = (await session.execute(select(User.id).where(User.email == email))).scalar_one()
        session.add(
            UsageEvent(
                userId=user_id,
                role="STUDENT",
                task="COMPOSE",
                outcome="OK",
                costUsd=Decimal("0.5"),
                estimatedCostUsd=Decimal("0.5"),
            )
        )
    principal = ai_router.Principal(user_id, "STUDENT")
    uncapped = await ai_router.run("PLAN", system="s", user="u", principal=principal)
    assert (uncapped.degraded, uncapped.cost_usd > 0) == (False, True)
    async with session_scope() as session:
        await app_settings.set_value(session, app_settings.ROLE_DAILY_USD, {"STUDENT": 0.5})
    try:
        with pytest.raises(ai_router.RouterError) as refused:
            await ai_router.run("PLAN", system="s", user="u", principal=principal)
        assert refused.value.reason == "ROLE_DAILY_CAP"
    finally:
        async with session_scope() as session:
            await app_settings.set_value(
                session, app_settings.ROLE_DAILY_USD, dict(app_settings.UNCAPPED_ROLE_DAILY_USD)
            )
