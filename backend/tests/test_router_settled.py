import asyncio
from decimal import Decimal
from typing import Any

import pytest
from sqlalchemy.exc import OperationalError

from app.providers import router as ai_router
from app.providers.catalogue import AiTask
from app.providers.spend_settings import MODEL_PRICES

from .router_fakes import Recorded, record_router

PRICED = {MODEL_PRICES: {"claude-sonnet-5-5": {"in": 2, "out": 10}}}
ANSWERED_COST = Decimal("0.304000")
POOLER_FULL = (
    "FATAL:  (EMAXCONNSESSION) max clients reached in session mode - max clients are limited to pool_size: 30"
)


def pooler_full_error() -> OperationalError:
    return OperationalError('UPDATE "UsageEvent"', {}, Exception(POOLER_FULL))


def settling(
    monkeypatch: pytest.MonkeyPatch, recorded: Recorded, *, refusals: int, seconds: float = 0.0
) -> None:
    left = [refusals]

    async def settle(_session: Any, _event_id: Any, **values: Any) -> None:
        if left[0] > 0:
            left[0] -= 1
            raise pooler_full_error()
        await asyncio.sleep(seconds)
        recorded.settled.append(values)

    monkeypatch.setattr(ai_router, "settle", settle)


async def composed(recorded: Recorded) -> ai_router.RouterResult:
    return await ai_router.run(AiTask.COMPOSE, system="s", user="u", session_factory=recorded.sessions())


async def test_an_answered_call_settles_at_its_cost_when_the_pooler_first_refuses_the_settlement(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    recorded = record_router(monkeypatch, settings=PRICED)
    settling(monkeypatch, recorded, refusals=1)
    result = await composed(recorded)
    assert (result.text, result.cost_usd) == ("{}", ANSWERED_COST)
    assert [(entry["outcome"], entry["cost_usd"], entry["output_tokens"]) for entry in recorded.settled] == [
        ("OK", ANSWERED_COST, 30_000)
    ]


async def test_an_answered_call_whose_caller_is_cut_off_while_it_settles_still_settles_at_its_cost(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    recorded = record_router(monkeypatch, settings=PRICED)
    settling(monkeypatch, recorded, refusals=0, seconds=0.2)
    with pytest.raises(TimeoutError):
        async with asyncio.timeout(0.05):
            await composed(recorded)
    await asyncio.sleep(0.5)
    assert [(entry["outcome"], entry["cost_usd"]) for entry in recorded.settled] == [("OK", ANSWERED_COST)]


async def test_a_settlement_failing_for_another_reason_still_fails_the_call(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    recorded = record_router(monkeypatch, settings=PRICED)

    async def settle(_session: Any, _event_id: Any, **_values: Any) -> None:
        raise OperationalError("UPDATE", {}, Exception("server closed the connection unexpectedly"))

    monkeypatch.setattr(ai_router, "settle", settle)
    with pytest.raises(OperationalError, match="server closed"):
        await composed(recorded)
