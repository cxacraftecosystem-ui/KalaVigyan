import asyncio
from decimal import Decimal
from typing import Any

import pytest

from app.providers import router as ai_router
from app.providers.base import Adapter, ChatRequest, ChatResult, ProviderError
from app.providers.budget import AnswerSpend, Ceilings
from app.providers.catalogue import AiTask
from app.providers.router import ABANDONED_KIND, Principal, RouterError
from app.providers.spend_settings import ANSWER_CAP_USD, MODEL_PRICES

from .router_fakes import Recorded, record_router

PRICED = {
    MODEL_PRICES: {"claude-sonnet-5-5": {"in": 2, "out": 10}},
    ANSWER_CAP_USD: {"BASIC": 0.02, "DETAILED": 0.05, "EXPERT": 0.2},
}
ESTIMATE = Decimal("0.010002")


class Failing(Adapter):
    def __init__(self, failure: BaseException | None) -> None:
        super().__init__(api_key="k", base_url=None, preset="anthropic", extra={}, learned={})
        self.failure = failure

    async def chat(self, req: ChatRequest) -> ChatResult:
        if self.failure is None:
            await asyncio.Event().wait()
        raise self.failure

    async def list_models(self) -> list[dict]:
        return []


def failing(monkeypatch: pytest.MonkeyPatch, failure: BaseException | None) -> Recorded:
    return record_router(monkeypatch, adapter=lambda _found: Failing(failure), settings=PRICED)


async def composed(recorded: Recorded, answer: AnswerSpend) -> Any:
    return await ai_router.run(
        AiTask.COMPOSE,
        system="s",
        user="u",
        max_tokens=1000,
        principal=Principal(role="STUDENT", answer=answer),
        session_factory=recorded.sessions(),
    )


async def test_a_bug_in_a_call_settles_its_hold_and_its_usage_at_the_estimate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    recorded = failing(monkeypatch, RuntimeError("a bug in the adapter"))
    answer = AnswerSpend(depth="DETAILED")
    with pytest.raises(RuntimeError, match="a bug in the adapter"):
        await composed(recorded, answer)
    assert (answer.held_usd, answer.spent_usd) == (Decimal(0), ESTIMATE)
    assert answer.left(Ceilings.from_settings(PRICED)) == Decimal("0.039998")
    assert recorded.settled == [{"outcome": "CANCELLED", "cost_usd": ESTIMATE, "error_kind": ABANDONED_KIND}]


async def test_a_cancelled_call_settles_its_hold_and_its_usage_at_the_estimate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    recorded = failing(monkeypatch, None)
    answer = AnswerSpend(depth="DETAILED")
    with pytest.raises(TimeoutError):
        async with asyncio.timeout(0.05):
            await composed(recorded, answer)
    assert (answer.held_usd, answer.spent_usd) == (Decimal(0), ESTIMATE)
    assert recorded.settled == [{"outcome": "CANCELLED", "cost_usd": ESTIMATE, "error_kind": ABANDONED_KIND}]


async def test_a_provider_failure_releases_the_hold_and_spends_nothing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    recorded = failing(monkeypatch, ProviderError("down", kind="unavailable", status=503))
    answer = AnswerSpend(depth="DETAILED")
    with pytest.raises(RouterError) as raised:
        await composed(recorded, answer)
    assert raised.value.kind == "exhausted"
    assert (answer.held_usd, answer.spent_usd) == (Decimal(0), Decimal(0))
    assert [(entry["outcome"], entry["error_kind"]) for entry in recorded.settled] == [
        ("ERROR", "unavailable")
    ]
