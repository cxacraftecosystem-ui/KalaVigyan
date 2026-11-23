import uuid
from decimal import Decimal
from typing import Any

import pytest
from sqlalchemy import func, select

from app.core.db import session_scope
from app.models import UsageEvent, User
from app.providers import router as ai_router
from app.providers.base import Adapter, ChatResult, ProviderError
from app.providers.spend_settings import UNCAPPED_ROLE_DAILY_USD
from app.services import app_settings

from .accounts import create_user, unique_email

pytestmark = pytest.mark.db


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


async def principal_of(role: str) -> ai_router.Principal:
    email = unique_email(role.lower())
    await create_user(email, role)
    async with session_scope() as session:
        user_id = (await session.execute(select(User.id).where(User.email == email))).scalar_one()
    return ai_router.Principal(user_id=user_id, role=role)


async def usage_of(user_id: uuid.UUID) -> list[tuple[str, str, Decimal]]:
    async with session_scope() as session:
        rows = await session.execute(
            select(UsageEvent.outcome, UsageEvent.provider, UsageEvent.costUsd)
            .where(UsageEvent.userId == user_id)
            .order_by(UsageEvent.createdAt)
        )
        return [(outcome, provider, cost) for outcome, provider, cost in rows.all()]


async def ceiling_refusals(user_id: uuid.UUID) -> int:
    async with session_scope() as session:
        counted = select(func.count()).select_from(UsageEvent)
        refused = UsageEvent.outcome == "REFUSED_CEILING"
        return (await session.execute(counted.where(UsageEvent.userId == user_id, refused))).scalar_one()


async def test_router_falls_back_records_usage_and_enforces_ceiling(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ai_router, "build_adapter", fake_build_adapter)
    FakeAdapter.failing_providers = {"gemini"}
    principal = await principal_of("RESEARCHER")
    result = await ai_router.run(
        "PLAN", system="plan", user="what mordant does ajrakh use?", principal=principal
    )
    assert (result.provider, result.model) == ("ANTHROPIC", "claude-haiku-5-5")
    assert result.cost_usd > 0
    assert [a["outcome"] for a in result.attempts] == ["rate_limit", "OK"]
    rows = await usage_of(principal.user_id)
    assert [(outcome, provider) for outcome, provider, _ in rows] == [
        ("ERROR", "GEMINI"),
        ("OK", "ANTHROPIC"),
    ]
    assert rows[1][2] == result.cost_usd
    async with session_scope() as session:
        await app_settings.set_value(session, app_settings.MONTHLY_CEILING_USD, 0.000001)
    try:
        with pytest.raises(ai_router.RouterError) as refused:
            await ai_router.run("PLAN", system="plan", user="again", principal=principal)
        assert (refused.value.kind, refused.value.reason) == ("ceiling", "MONTHLY_CEILING")
        assert await ceiling_refusals(principal.user_id) == 1
    finally:
        async with session_scope() as session:
            await app_settings.set_value(session, app_settings.MONTHLY_CEILING_USD, None)


async def test_a_student_is_uncapped_by_default_and_a_set_role_cap_refuses(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(ai_router, "build_adapter", fake_build_adapter)
    FakeAdapter.failing_providers = set()
    principal = await principal_of("STUDENT")
    async with session_scope() as session:
        spent = Decimal("0.5")
        session.add(
            UsageEvent(
                userId=principal.user_id,
                role="STUDENT",
                task="COMPOSE",
                outcome="OK",
                costUsd=spent,
                estimatedCostUsd=spent,
            )
        )
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
            await app_settings.set_value(session, app_settings.ROLE_DAILY_USD, dict(UNCAPPED_ROLE_DAILY_USD))
