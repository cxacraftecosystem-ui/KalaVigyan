from __future__ import annotations

import uuid
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

import pytest

from app.providers import budget, media_router, router as provider_router
from app.providers.base import Adapter, MediaRequest, MediaResult
from app.providers.catalogue import MEDIA_TASKS, AiTask
from app.providers.media_router import MediaRouter
from app.providers.router import RouteChoice

__all__ = [
    "BYTES_PER_SECOND",
    "Budgeted",
    "SoundStudio",
    "budgeted",
    "elevenlabs_route",
    "mp3",
    "no_session",
    "studio_router",
]

BYTES_PER_SECOND = 128_000 // 8
CEILINGS = budget.Ceilings(
    monthly_usd=Decimal(800),
    media_usd=Decimal(150),
    role_daily_usd={"STUDENT": Decimal(2), "MASTER_ADMIN": None},
    degrade_at=Decimal("0.8"),
    answer_usd={},
)


def mp3(seconds: float) -> bytes:
    return b"\xff\xfb" * round(seconds * BYTES_PER_SECOND / 2)


def elevenlabs_route(model: str, ordinal: int = 1) -> RouteChoice:
    return RouteChoice(
        ordinal=ordinal,
        provider="ELEVENLABS",
        provider_id=None,
        preset="elevenlabs",
        kind="elevenlabs",
        base_url=None,
        key_name="ELEVENLABS_API_KEY",
        model=model,
    )


@dataclass
class Budgeted:
    routes: dict[AiTask, list[RouteChoice]]
    spend: budget.SpendState = field(default_factory=budget.SpendState)
    reserved: list[dict[str, Any]] = field(default_factory=list)
    settled: list[dict[str, Any]] = field(default_factory=list)


def budgeted(monkeypatch: pytest.MonkeyPatch, routes: dict[AiTask, list[RouteChoice]]) -> Budgeted:
    found = Budgeted(routes=routes)

    async def load_routes(session: Any, task: AiTask) -> list[RouteChoice]:
        return list(found.routes.get(task, []))

    async def reserve(session: Any, **kw: Any) -> tuple[uuid.UUID, budget.BudgetDecision]:
        decision = budget.evaluate(
            CEILINGS,
            found.spend,
            estimate_usd=kw["estimate_usd"],
            is_media=kw["task"] in MEDIA_TASKS,
            role=kw["principal"].role,
        )
        found.reserved.append(
            {"model": kw["choice"].model, "estimate": kw["estimate_usd"], "allowed": decision.allowed}
        )
        return uuid.uuid4(), decision

    async def settle(session: Any, event_id: uuid.UUID, **kw: Any) -> None:
        found.settled.append(kw)

    async def nothing(*_: Any, **__: Any) -> Any:
        return {}

    monkeypatch.setattr(media_router, "load_routes", load_routes)
    monkeypatch.setattr(media_router, "reserve", reserve)
    monkeypatch.setattr(media_router, "settle", settle)
    monkeypatch.setattr(provider_router, "settle", settle)
    monkeypatch.setattr(media_router.spend_settings, "load_spend_settings", nothing)
    monkeypatch.setattr(media_router.managed_keys, "refresh_if_stale", nothing)
    monkeypatch.setattr(media_router.managed_keys, "peek_secret", lambda name: "test-only-key")
    return found


class SoundStudio(Adapter):
    def __init__(self, calls: list[MediaRequest]) -> None:
        super().__init__(api_key="k", base_url=None, preset="elevenlabs", extra={}, learned={})
        self.calls = calls

    async def chat(self, req: Any) -> Any:
        raise AssertionError("the score never chats")

    async def list_models(self) -> list[dict]:
        return []

    async def generate_audio(self, req: MediaRequest) -> MediaResult:
        self.calls.append(req)
        return MediaResult(mp3(float(req.output["seconds"])), "audio/mpeg", None, None, None, None, req.model)


@asynccontextmanager
async def no_session() -> Any:
    yield None


def studio_router(calls: list[MediaRequest]) -> MediaRouter:
    return MediaRouter(session_factory=no_session, adapter_factory=lambda choice, key: SoundStudio(calls))
