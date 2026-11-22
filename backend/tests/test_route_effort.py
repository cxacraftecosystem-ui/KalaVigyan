from typing import Any

import pytest

from app.providers import router as ai_router
from app.providers.anthropic_p import AnthropicAdapter
from app.providers.base import Adapter, ChatRequest, ChatResult
from app.providers.catalogue import AiTask
from app.providers.router import REASONING_EFFORT_PARAM, RouteChoice, reasoning_effort

OPUS = "claude-opus-5-5"
SONNET = "claude-sonnet-5-5"


def route(model: str, params: dict[str, Any] | None = None) -> RouteChoice:
    return RouteChoice(
        ordinal=1,
        provider="ANTHROPIC",
        provider_id=None,
        preset="anthropic",
        kind="x",
        base_url=None,
        key_name="ANTHROPIC_API_KEY",
        model=model,
        params=params or {},
    )


class RecordingAdapter(Adapter):
    def __init__(self) -> None:
        super().__init__(api_key=None, base_url=None, preset="anthropic", extra={}, learned={})
        self.requests: list[ChatRequest] = []

    async def chat(self, req: ChatRequest) -> ChatResult:
        self.requests.append(req)
        return ChatResult(text="{}")

    async def list_models(self) -> list[dict]:
        return []


def anthropic_adapter() -> AnthropicAdapter:
    return AnthropicAdapter(api_key="test-key", base_url=None, preset="anthropic", extra={}, learned={})


def test_composing_answers_reasons_at_medium_effort_by_default() -> None:
    assert reasoning_effort(AiTask.COMPOSE, route(OPUS)) == "medium"


def test_other_tasks_keep_the_provider_default() -> None:
    assert reasoning_effort(AiTask.PLAN, route(OPUS)) is None
    assert reasoning_effort(AiTask.EXTRACT, route(OPUS)) is None


def test_a_route_can_set_its_own_effort() -> None:
    assert reasoning_effort(AiTask.COMPOSE, route(OPUS, {REASONING_EFFORT_PARAM: "low"})) == "low"
    assert reasoning_effort(AiTask.PLAN, route(OPUS, {REASONING_EFFORT_PARAM: "high"})) == "high"


@pytest.mark.parametrize("stored", ["", "fast", 3, None])
def test_an_unknown_stored_effort_falls_back_to_the_task_default(stored: Any) -> None:
    assert reasoning_effort(AiTask.COMPOSE, route(OPUS, {REASONING_EFFORT_PARAM: stored})) == "medium"


async def test_the_router_sends_the_route_effort_to_the_model() -> None:
    adapter = RecordingAdapter()
    await ai_router._call(
        adapter,
        AiTask.COMPOSE,
        route(OPUS),
        system="s",
        user="u",
        json_schema=None,
        max_tokens=100,
        temperature=None,
        texts=None,
    )
    (sent,) = adapter.requests
    assert sent.reasoning_effort == "medium"
    assert sent.reasoning is False


def test_an_always_thinking_model_is_asked_for_the_chosen_effort() -> None:
    params, meta = anthropic_adapter()._build(
        ChatRequest(model=OPUS, system="s", user="u", reasoning_effort="medium")
    )
    assert params["output_config"]["effort"] == "medium"
    assert meta["thinking"] == "forced_on"


def test_a_model_with_optional_thinking_keeps_thinking_off_whatever_the_effort() -> None:
    params, meta = anthropic_adapter()._build(
        ChatRequest(model=SONNET, system="s", user="u", reasoning_effort="medium")
    )
    assert params["thinking"] == {"type": "disabled"}
    assert "output_config" not in params
    assert meta["thinking"] == "off"
