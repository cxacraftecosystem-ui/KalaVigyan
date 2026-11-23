import asyncio
from dataclasses import replace
from typing import Any

import pytest

from app.providers import router as ai_router
from app.providers.anthropic_p import AnthropicAdapter
from app.providers.base import ChatRequest, ProviderError
from app.providers.catalogue import AiTask
from app.providers.gemini_p import GeminiAdapter
from app.providers.openai_p import OpenAICompatAdapter
from app.providers.router import Principal, RouteChoice, RouterError
from app.providers.spend_settings import MODEL_PRICES

from .router_fakes import Recorded, anthropic_route, record_router

FLASH = "gemini-3.8-flash"
EMBEDDING_MODEL = "gemini-embedding-2"
BOUND = 0.05
TEST_DEADLINE = 5


class StalledModels:
    def __init__(self) -> None:
        self.calls = 0

    async def generate_content(self, **_: Any) -> Any:
        self.calls += 1
        await asyncio.Event().wait()

    async def embed_content(self, **_: Any) -> Any:
        self.calls += 1
        await asyncio.Event().wait()


def stalled_adapter(models: StalledModels) -> GeminiAdapter:
    adapter = GeminiAdapter(api_key="test-key", base_url=None, preset="gemini", extra={}, learned={})
    adapter.client = type("Client", (), {"aio": type("Aio", (), {"models": models})()})()
    adapter.chat_seconds = BOUND
    adapter.embed_seconds = BOUND
    return adapter


async def test_a_stalled_gemini_chat_ends_as_a_failure_the_next_route_can_take() -> None:
    models = StalledModels()
    with pytest.raises(ProviderError) as stalled:
        async with asyncio.timeout(TEST_DEADLINE):
            await stalled_adapter(models).chat(ChatRequest(model=FLASH, system="s", user="u"))
    assert (stalled.value.kind, stalled.value.retryable, stalled.value.tries_next) == (
        "unavailable",
        True,
        True,
    )
    assert str(stalled.value) == "Gemini did not answer within 0.05 s"
    assert models.calls == 1


async def test_a_stalled_gemini_embedding_ends_as_a_failure() -> None:
    models = StalledModels()
    with pytest.raises(ProviderError) as stalled:
        async with asyncio.timeout(TEST_DEADLINE):
            await stalled_adapter(models).embed(["Alum fixes alizarin."], EMBEDDING_MODEL)
    assert (stalled.value.kind, str(stalled.value)) == ("unavailable", "Gemini did not answer within 0.05 s")


async def test_a_caller_s_own_deadline_still_cancels_a_gemini_call() -> None:
    adapter = stalled_adapter(StalledModels())
    adapter.chat_seconds = 60.0
    with pytest.raises(TimeoutError):
        async with asyncio.timeout(BOUND):
            await adapter.chat(ChatRequest(model=FLASH, system="s", user="u"))


def test_gemini_bounds_a_chat_as_long_as_the_other_chat_adapters_and_an_embedding_to_two_minutes() -> None:
    anthropic = AnthropicAdapter(api_key="k", base_url=None, preset="anthropic", extra={}, learned={})
    openai = OpenAICompatAdapter(api_key="k", base_url=None, preset="openai", extra={}, learned={})
    assert anthropic.client.timeout == openai.client.timeout == GeminiAdapter.chat_seconds == 600.0
    assert GeminiAdapter.embed_seconds == 120.0


async def composed(recorded: Recorded) -> Any:
    return await ai_router.run(
        AiTask.COMPOSE,
        system="s",
        user="u",
        max_tokens=1000,
        principal=Principal(role="STUDENT"),
        session_factory=recorded.sessions(),
    )


async def test_a_stalled_gemini_call_gives_back_its_provider_slot_and_settles_as_an_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    models = StalledModels()
    adapter = stalled_adapter(models)
    recorded = record_router(
        monkeypatch,
        adapter=lambda _found: adapter,
        settings={MODEL_PRICES: {"claude-sonnet-5-5": {"in": 2, "out": 10}}},
    )

    async def one_slot(_session: Any, _task: AiTask) -> list[RouteChoice]:
        return [replace(anthropic_route(), max_concurrency=1)]

    monkeypatch.setattr(ai_router, "load_routes", one_slot)
    monkeypatch.setattr(ai_router, "_semaphores", {})
    for _ in range(2):
        with pytest.raises(RouterError) as raised:
            async with asyncio.timeout(TEST_DEADLINE):
                await composed(recorded)
        assert raised.value.kind == "exhausted"
    assert models.calls == 2
    assert not ai_router._semaphores["ANTHROPIC"].locked()
    assert [(entry["outcome"], entry["error_kind"]) for entry in recorded.settled] == [
        ("ERROR", "unavailable"),
        ("ERROR", "unavailable"),
    ]
