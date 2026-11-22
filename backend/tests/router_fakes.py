from collections.abc import AsyncIterator, Callable, Mapping
from contextlib import asynccontextmanager
from decimal import Decimal
from typing import Any

import pytest

from app.models import UsageEvent
from app.providers import budget, router as ai_router
from app.providers.base import Adapter, ChatRequest, ChatResult
from app.providers.catalogue import AiTask
from app.providers.router import Principal, RouteChoice
from app.services import app_settings

FAR_PAST_ANY_EARLIER_CAP = budget.SpendState(Decimal(1_000_000), Decimal(1_000_000), Decimal(1_000_000))
USAGE = {"input_tokens": 2_000, "output_tokens": 30_000}


class RecordingAdapter(Adapter):
    def __init__(self, requests: list[ChatRequest]) -> None:
        super().__init__(api_key="k", base_url=None, preset="anthropic", extra={}, learned={})
        self.requests = requests

    async def chat(self, req: ChatRequest) -> ChatResult:
        self.requests.append(req)
        return ChatResult(text="{}", **USAGE)

    async def list_models(self) -> list[dict]:
        return []


class QuietSession:
    def __init__(self, added: list[Any]) -> None:
        self.added = added

    async def execute(self, *_: Any, **__: Any) -> None:
        return None

    def add(self, row: Any) -> None:
        self.added.append(row)

    async def flush(self) -> None:
        return None

    async def commit(self) -> None:
        return None


class Recorded:
    def __init__(self) -> None:
        self.requests: list[ChatRequest] = []
        self.reserved: list[UsageEvent] = []
        self.settled: list[dict[str, Any]] = []

    def sessions(self) -> Any:
        @asynccontextmanager
        async def session() -> AsyncIterator[QuietSession]:
            yield QuietSession(self.reserved)

        return session


def anthropic_route(model: str = "claude-sonnet-5-5") -> RouteChoice:
    return RouteChoice(
        ordinal=1,
        provider="ANTHROPIC",
        provider_id=None,
        preset="anthropic",
        kind="anthropic",
        base_url=None,
        key_name="ANTHROPIC_API_KEY",
        model=model,
    )


def record_router(
    monkeypatch: pytest.MonkeyPatch,
    *,
    adapter: Callable[[Recorded], Adapter] = lambda found: RecordingAdapter(found.requests),
    settings: Mapping[str, Any] | None = None,
) -> Recorded:
    found = Recorded()
    values = {**app_settings.DEFAULTS, **(settings or {})}

    async def load_routes(_session: Any, _task: AiTask) -> list[RouteChoice]:
        return [anthropic_route()]

    async def load_all(_session: Any) -> dict[str, Any]:
        return dict(values)

    async def current_spend(_session: Any, _principal: Principal, _now: Any = None) -> budget.SpendState:
        return FAR_PAST_ANY_EARLIER_CAP

    async def settle(_session: Any, event_id: Any, **recorded: Any) -> None:
        found.settled.append(recorded)

    async def refresh_if_stale(_session: Any, force: bool = False) -> None:
        return None

    monkeypatch.setattr(ai_router, "load_routes", load_routes)
    monkeypatch.setattr(ai_router.spend_settings, "load_spend_settings", load_all)
    monkeypatch.setattr(ai_router, "current_spend", current_spend)
    monkeypatch.setattr(ai_router, "settle", settle)
    monkeypatch.setattr(ai_router.managed_keys, "refresh_if_stale", refresh_if_stale)
    monkeypatch.setattr(ai_router.managed_keys, "peek_secret", lambda _key: "k")
    monkeypatch.setattr(ai_router, "build_adapter", lambda **_: adapter(found))
    return found
