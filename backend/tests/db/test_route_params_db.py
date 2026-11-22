from typing import Any

import pytest
from sqlalchemy import select, update

from app.core.db import session_scope
from app.models import Provider, RoutePolicy
from app.providers.catalogue import AiTask
from app.providers.router import REASONING_EFFORT_PARAM
from app.services.route_policy import save_order

pytestmark = pytest.mark.db

TASK = AiTask.EXTRACT
CHOSEN = {REASONING_EFFORT_PARAM: "high"}


async def _routes() -> list[dict[str, Any]]:
    async with session_scope() as session:
        rows = (
            await session.execute(
                select(RoutePolicy, Provider.name)
                .join(Provider, Provider.id == RoutePolicy.providerId)
                .where(RoutePolicy.task == TASK.value)
                .order_by(RoutePolicy.ordinal)
            )
        ).all()
    return [
        {
            "provider": name,
            "model": route.model,
            "maxOutputTokens": route.maxOutputTokens,
            "temperature": route.temperature,
            "enabled": route.enabled,
            "params": dict(route.params or {}),
        }
        for route, name in rows
    ]


async def _save(entries: list[dict[str, Any]]) -> None:
    async with session_scope() as session:
        await save_order(session, TASK, entries, None)


async def _set_params(provider: str, model: str, params: dict[str, Any]) -> None:
    async with session_scope() as session:
        provider_id = (
            await session.execute(select(Provider.id).where(Provider.name == provider))
        ).scalar_one()
        await session.execute(
            update(RoutePolicy)
            .where(
                RoutePolicy.task == TASK.value,
                RoutePolicy.providerId == provider_id,
                RoutePolicy.model == model,
            )
            .values(params=params)
        )


async def test_reordering_routes_keeps_each_route_s_own_settings() -> None:
    original = await _routes()
    assert len(original) >= 2
    first = original[0]
    await _set_params(first["provider"], first["model"], CHOSEN)
    try:
        await _save(list(reversed(original)))
        reordered = await _routes()
        assert [(r["provider"], r["model"]) for r in reordered] == [
            (r["provider"], r["model"]) for r in reversed(original)
        ]
        expected = {(r["provider"], r["model"]): r["params"] for r in original} | {
            (first["provider"], first["model"]): CHOSEN
        }
        assert {(r["provider"], r["model"]): r["params"] for r in reordered} == expected
    finally:
        await _save(original)
        for entry in original:
            await _set_params(entry["provider"], entry["model"], entry["params"])
    assert await _routes() == original
