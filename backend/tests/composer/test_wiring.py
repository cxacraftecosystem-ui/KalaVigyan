from types import SimpleNamespace
from typing import Any

import pytest

from app.composer.candidates import compose_request
from app.composer.composer import ModelComposer
from app.composer.prompt import COMPOSE_SYSTEM_PROMPT, compose_schema
from app.core.errors import NEXT_ROUTE_KINDS
from app.providers import router
from app.providers.base import ProviderError
from app.providers.catalogue import DEFAULT_ROUTES, AiProvider, AiTask
from app.providers.registry import build_adapter
from app.providers.structured import router_structured_model

from .fixtures import ALUM_CLAIM_ID, QUESTION, answer, pack, quote, sentence


async def test_the_composer_runs_through_the_router_compose_task(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[dict[str, Any]] = []
    reply = answer(
        ("Alum", [sentence("Alum binds alizarin.", quote(ALUM_CLAIM_ID, "binds alizarin to cotton"))])
    )

    async def run(task: AiTask, **options: Any) -> SimpleNamespace:
        seen.append({"task": task, **options})
        return SimpleNamespace(text=reply, degraded=False, model="claude-opus-5-5")

    monkeypatch.setattr(router, "run", run)
    principal = router.Principal(role="STUDENT")
    composer = ModelComposer(model=router_structured_model(AiTask.COMPOSE, principal))
    result = await composer.compose(compose_request(pack(), QUESTION))
    assert [s.text for s in result.sections[0].sentences] == ["Alum binds alizarin."]
    [call] = seen
    assert call["task"] == AiTask.COMPOSE
    assert call["system"] == COMPOSE_SYSTEM_PROMPT
    assert call["json_schema"] == compose_schema()
    assert call["principal"] == principal


def test_compose_routes_to_sonnet_first_and_gemini_next() -> None:
    assert DEFAULT_ROUTES[AiTask.COMPOSE][:2] == (
        (AiProvider.ANTHROPIC, "claude-sonnet-5-5"),
        (AiProvider.GEMINI, "gemini-3.8-flash"),
    )


def test_a_missing_sonnet_key_moves_the_router_to_the_next_route() -> None:
    with pytest.raises(ProviderError) as raised:
        build_adapter(preset="anthropic", kind="anthropic", api_key=None, api_key_name="ANTHROPIC_API_KEY")
    assert raised.value.kind == "auth"
    assert raised.value.kind in NEXT_ROUTE_KINDS
