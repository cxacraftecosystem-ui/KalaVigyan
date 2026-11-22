import asyncio

import pytest

from app.core.research_gate import SHORT_REQUEST_CONNECTIONS, ResearchGate, research_slots


def test_research_leaves_two_connections_of_the_pool_to_short_requests() -> None:
    assert SHORT_REQUEST_CONNECTIONS == 2
    assert research_slots(5, 0) == 3
    assert research_slots(12, 0) == 10
    assert research_slots(5, 2) == 5
    assert research_slots(2, 0) == 1
    assert research_slots(1, 0) == 1


def test_a_gate_holds_at_least_one_slot() -> None:
    with pytest.raises(ValueError, match="at least one slot"):
        ResearchGate(0)


async def test_no_more_research_sessions_than_slots_run_at_once() -> None:
    gate = ResearchGate(2)
    running = 0
    most = 0

    async def work() -> None:
        nonlocal running, most
        async with gate.held():
            running += 1
            most = max(most, running)
            await asyncio.sleep(0.01)
            running -= 1

    await asyncio.gather(*(work() for _ in range(7)))
    assert most == 2


async def test_a_holder_opening_another_session_does_not_wait_for_a_second_slot() -> None:
    gate = ResearchGate(1)

    async def nested() -> str:
        async with gate.held(), gate.held():
            return "nested"

    assert await asyncio.wait_for(nested(), timeout=1) == "nested"
