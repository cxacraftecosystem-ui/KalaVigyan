from dataclasses import replace
from types import SimpleNamespace
from typing import Any

import pytest

from app.providers import router
from app.providers.answer_routes import (
    BUILDER_MODEL,
    BUILDER_TUNING,
    COMPOSE_TUNINGS,
    EXPERT_MODEL,
    EXPLAINER_TUNINGS,
    answer_models,
)
from app.providers.catalogue import AiTask
from app.providers.router import RouteChoice, RouteTuning, reasoning_effort


def _route(provider: str, model: str, *, cap: int | None = None) -> RouteChoice:
    return RouteChoice(
        ordinal=1,
        provider=provider,
        provider_id=None,
        preset=provider.lower(),
        kind=provider.lower(),
        base_url=None,
        key_name=f"{provider}_API_KEY",
        model=model,
        max_output_tokens=cap,
    )


def test_a_tuning_swaps_the_model_of_its_provider_only() -> None:
    tuning = RouteTuning(models={"ANTHROPIC": "claude-opus-5-5"}, effort="high", max_output_tokens=16000)
    anthropic = tuning.applied(_route("ANTHROPIC", "claude-sonnet-5-5"))
    gemini = tuning.applied(_route("GEMINI", "gemini-3.8-flash"))
    assert (anthropic.model, gemini.model) == ("claude-opus-5-5", "gemini-3.8-flash")
    assert reasoning_effort(AiTask.COMPOSE, anthropic) == "high"
    assert reasoning_effort(AiTask.COMPOSE, _route("ANTHROPIC", "claude-sonnet-5-5")) == "medium"


def test_a_tuning_raises_the_output_cap_and_never_lowers_it() -> None:
    tuning = RouteTuning(max_output_tokens=8192)
    assert tuning.applied(_route("ANTHROPIC", "m")).max_output_tokens == 8192
    assert tuning.applied(_route("ANTHROPIC", "m", cap=4096)).max_output_tokens == 8192
    assert tuning.applied(_route("ANTHROPIC", "m", cap=20000)).max_output_tokens == 20000


def test_a_tuning_refuses_an_unknown_effort() -> None:
    with pytest.raises(ValueError, match="effort"):
        RouteTuning(effort="huge")


def test_expert_composes_on_opus_at_high_effort_and_builders_stay_on_sonnet() -> None:
    expert = COMPOSE_TUNINGS["EXPERT"]
    assert (dict(expert.models), expert.effort, expert.max_output_tokens) == (
        {"ANTHROPIC": EXPERT_MODEL},
        "high",
        None,
    )
    assert EXPERT_MODEL == "claude-opus-5-5" and BUILDER_MODEL == "claude-sonnet-5-5"
    assert dict(BUILDER_TUNING.models) == {"ANTHROPIC": "claude-sonnet-5-5"}
    assert dict(EXPLAINER_TUNINGS["EXPERT"].models) == {"ANTHROPIC": "claude-opus-5-5"}
    assert dict(EXPLAINER_TUNINGS["DETAILED"].models) == {"ANTHROPIC": "claude-sonnet-5-5"}
    assert COMPOSE_TUNINGS["DETAILED"].models == {} and COMPOSE_TUNINGS["DETAILED"].max_output_tokens is None


async def test_each_answer_model_runs_its_task_with_its_tuning(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[tuple[AiTask, RouteTuning | None]] = []

    async def run(task: AiTask, **options: Any) -> SimpleNamespace:
        seen.append((task, options["tuning"]))
        return SimpleNamespace(text="{}", degraded=False, model="m")

    monkeypatch.setattr(router, "run", run)
    principal, optional = router.Principal(role="ADMIN"), router.Principal(role="ADMIN")
    models = answer_models("EXPERT", principal=principal, optional=optional)
    for model in (models.compose, models.builder_compose, models.explainer, models.plan, models.understand):
        await model(system="s", user="u", schema={"type": "object"})
    assert seen == [
        (AiTask.COMPOSE, COMPOSE_TUNINGS["EXPERT"]),
        (AiTask.COMPOSE, BUILDER_TUNING),
        (AiTask.COMPOSE, EXPLAINER_TUNINGS["EXPERT"]),
        (AiTask.PLAN, None),
        (AiTask.UNDERSTAND, None),
    ]


def test_a_tuned_route_keeps_everything_but_model_effort_and_cap() -> None:
    route = replace(_route("ANTHROPIC", "claude-sonnet-5-5", cap=1000), temperature=0.2)
    tuned = COMPOSE_TUNINGS["EXPERT"].applied(route)
    assert (tuned.temperature, tuned.key_name, tuned.provider) == (0.2, "ANTHROPIC_API_KEY", "ANTHROPIC")
