from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from decimal import Decimal
from typing import Any

import pytest

from app.core.roles import ROLE_RANK
from app.models import UsageEvent
from app.models.enums import EXPLAINER_DEPTHS
from app.providers import budget, router as ai_router
from app.providers.answer_routes import COMPOSE_TUNINGS, EXPLAINER_TUNINGS
from app.providers.base import Adapter, ChatRequest, ChatResult
from app.providers.catalogue import AiTask
from app.providers.router import Principal, RouteChoice, RouteTuning
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


@pytest.fixture
def recorded(monkeypatch: pytest.MonkeyPatch) -> Recorded:
    found = Recorded()

    async def load_routes(_session: Any, _task: AiTask) -> list[RouteChoice]:
        return [anthropic_route()]

    async def load_all(_session: Any) -> dict[str, Any]:
        return dict(app_settings.DEFAULTS)

    async def current_spend(_session: Any, _principal: Principal, _now: Any = None) -> budget.SpendState:
        return FAR_PAST_ANY_EARLIER_CAP

    async def settle(_session: Any, event_id: Any, **values: Any) -> None:
        found.settled.append(values)

    async def refresh_if_stale(_session: Any, force: bool = False) -> None:
        return None

    monkeypatch.setattr(ai_router, "load_routes", load_routes)
    monkeypatch.setattr(ai_router.spend_settings, "load_spend_settings", load_all)
    monkeypatch.setattr(ai_router, "current_spend", current_spend)
    monkeypatch.setattr(ai_router, "settle", settle)
    monkeypatch.setattr(ai_router.managed_keys, "refresh_if_stale", refresh_if_stale)
    monkeypatch.setattr(ai_router.managed_keys, "peek_secret", lambda _key: "k")
    monkeypatch.setattr(ai_router, "build_adapter", lambda **_: RecordingAdapter(found.requests))
    return found


def tunings_of(depth: str) -> tuple[tuple[str, RouteTuning, str], ...]:
    expert = depth == "EXPERT"
    return (
        ("compose", COMPOSE_TUNINGS[depth], "claude-opus-5-5" if expert else "claude-sonnet-5-5"),
        ("explainer", EXPLAINER_TUNINGS[depth], "claude-opus-5-5" if expert else "claude-sonnet-5-5"),
    )


@pytest.mark.parametrize("depth", EXPLAINER_DEPTHS)
@pytest.mark.parametrize("role", ROLE_RANK)
async def test_no_role_or_depth_is_refused_degraded_or_cut_short_and_every_cost_is_recorded(
    recorded: Recorded, role: str, depth: str
) -> None:
    answer = budget.AnswerSpend(depth=depth)
    asks = [Principal(role=role, answer=answer), Principal(role=role, answer=answer.headroom())]
    for (_name, tuning, model), principal in zip(tunings_of(depth), asks, strict=True):
        result = await ai_router.run(
            AiTask.COMPOSE,
            system="s",
            user="u",
            principal=principal,
            session_factory=recorded.sessions(),
            tuning=tuning,
        )
        assert (result.degraded, result.model, result.cost_usd > 0) == (False, model, True)
    assert [request.max_tokens for request in recorded.requests] == [128_000, 128_000]
    assert [(event.outcome, event.role, event.estimatedCostUsd > 0) for event in recorded.reserved] == [
        ("RESERVED", role, True),
        ("RESERVED", role, True),
    ]
    assert [(entry["outcome"], entry["output_tokens"]) for entry in recorded.settled] == [
        ("OK", 30_000),
        ("OK", 30_000),
    ]
    assert answer.spent_usd == sum((entry["cost_usd"] for entry in recorded.settled), Decimal(0))
    assert answer.held_usd == Decimal(0)


@pytest.mark.parametrize("role", ROLE_RANK)
@pytest.mark.parametrize(
    "task",
    [AiTask.PLAN, AiTask.TRANSLATE, AiTask.SUMMARISE, AiTask.VOICE_TURN, AiTask.INTERVIEW, AiTask.TESTIMONY],
)
async def test_term_summaries_translation_voice_interview_and_testimony_run_uncapped_at_the_maximum(
    recorded: Recorded, role: str, task: AiTask
) -> None:
    result = await ai_router.run(
        task, system="s", user="u", principal=Principal(role=role), session_factory=recorded.sessions()
    )
    assert (result.degraded, recorded.requests[0].max_tokens) == (False, 128_000)
    assert recorded.settled[0]["outcome"] == "OK" and recorded.settled[0]["cost_usd"] > 0
