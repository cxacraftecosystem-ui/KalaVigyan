import pytest

from app.providers.answer_routes import BUILDER_TUNING, COMPOSE_TUNINGS, EXPLAINER_TUNINGS
from app.providers.catalogue import (
    CHAT_TASKS,
    DEFAULT_ROUTES,
    PROVIDERS,
    AiTask,
    catalogue,
    output_limit,
    supports,
)
from app.providers.router import (
    DEFAULT_MAX_OUTPUT_TOKENS,
    RouteChoice,
    RouteTuning,
    output_tokens_for,
    route_allowed,
)

DOCUMENTED_MAXIMA = {
    ("ANTHROPIC", "claude-opus-5-5"): 128_000,
    ("ANTHROPIC", "claude-sonnet-5-5"): 128_000,
    ("ANTHROPIC", "claude-haiku-5-5"): 128_000,
    ("ANTHROPIC", "claude-opus-5"): 128_000,
    ("ANTHROPIC", "claude-sonnet-5"): 128_000,
    ("GEMINI", "gemini-3.8-flash"): 65_536,
    ("GEMINI", "gemini-3.7-flash"): 65_536,
    ("GEMINI", "gemini-3.5-flash-lite"): 65_536,
    ("GEMINI", "gemini-3.1-pro-preview"): 65_536,
    ("GEMINI", "gemini-4-argon"): 65_536,
    ("GEMINI", "gemini-3.8-flash-tts"): 16_384,
    ("OPENAI", "gpt-6-luna"): 128_000,
    ("OPENAI", "gpt-6.1-terra"): 128_000,
    ("OPENAI", "gpt-5.6-terra"): 128_000,
    ("OPENAI", "gpt-5.6-sol"): 128_000,
    ("DEEPSEEK", "deepseek-flash"): 384_000,
    ("DEEPSEEK", "deepseek-v4-pro"): 384_000,
}
EARLIER_OUTPUT_LIMITS = {AiTask.COMPOSE: 18_000, AiTask.TRANSLATE: 8192, AiTask.SUMMARISE: 2048}
EARLIER_DEFAULT_OUTPUT_LIMIT = 4096
ANSWER_TASKS = (
    AiTask.COMPOSE,
    AiTask.PLAN,
    AiTask.TRANSLATE,
    AiTask.SUMMARISE,
    AiTask.VOICE_TURN,
    AiTask.INTERVIEW,
    AiTask.TESTIMONY,
)
ANSWER_TUNINGS: tuple[RouteTuning | None, ...] = (
    None,
    BUILDER_TUNING,
    *COMPOSE_TUNINGS.values(),
    *EXPLAINER_TUNINGS.values(),
)


def route(provider: str, model: str, *, cap: int | None = None) -> RouteChoice:
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


def test_the_catalogue_holds_the_documented_output_maxima() -> None:
    for (provider, model), documented in DOCUMENTED_MAXIMA.items():
        assert output_limit(provider, model) == documented, (provider, model)


def test_every_chat_model_of_every_provider_has_its_documented_maximum() -> None:
    chat_models = {
        (provider.value, model.id): model.max_output_tokens
        for provider, spec in PROVIDERS.items()
        for model in spec.models
        if model.tasks & CHAT_TASKS
    }
    assert chat_models == DOCUMENTED_MAXIMA


def test_the_catalogue_lists_each_model_s_output_maximum() -> None:
    listed = {
        (provider["provider"], model["id"]): model["maxOutputTokens"]
        for provider in catalogue()
        for model in provider["models"]
    }
    assert {key: listed[key] for key in DOCUMENTED_MAXIMA} == DOCUMENTED_MAXIMA


@pytest.mark.parametrize("tuning", ANSWER_TUNINGS)
@pytest.mark.parametrize("task", ANSWER_TASKS)
def test_every_answer_route_asks_for_its_model_s_documented_maximum(
    task: AiTask, tuning: RouteTuning | None
) -> None:
    for provider, model in DEFAULT_ROUTES[task]:
        choice = route(provider.value, model)
        tuned = tuning.applied(choice) if tuning else choice
        expected = DOCUMENTED_MAXIMA[(tuned.provider, tuned.model)]
        assert output_tokens_for(tuned) == expected, (task, tuned.provider, tuned.model)


@pytest.mark.parametrize("tuning", ANSWER_TUNINGS)
def test_no_model_a_route_can_use_asks_for_fewer_tokens_than_before(tuning: RouteTuning | None) -> None:
    for task in DEFAULT_ROUTES:
        if task not in CHAT_TASKS:
            continue
        earlier = EARLIER_OUTPUT_LIMITS.get(task, EARLIER_DEFAULT_OUTPUT_LIMIT)
        for provider, spec in PROVIDERS.items():
            for model in spec.models:
                if not supports(provider, model.id, task):
                    continue
                choice = route(provider.value, model.id)
                tuned = tuning.applied(choice) if tuning else choice
                assert output_tokens_for(tuned) >= earlier, (task, tuned.provider, tuned.model)


@pytest.mark.parametrize("depth", ["DETAILED", "EXPERT"])
def test_the_openai_fallback_keeps_more_than_its_earlier_compose_and_translate_limits(depth: str) -> None:
    terra = route("OPENAI", "gpt-6.1-terra")
    assert output_tokens_for(COMPOSE_TUNINGS[depth].applied(terra)) == 128_000
    assert output_tokens_for(EXPLAINER_TUNINGS[depth].applied(terra)) == 128_000
    assert output_tokens_for(terra) == 128_000
    assert output_tokens_for(route("DEEPSEEK", "deepseek-v4-pro")) == 384_000


@pytest.mark.parametrize("depth", ["BASIC", "DETAILED", "EXPERT"])
def test_compose_and_the_generated_explainer_reach_the_claude_maximum_at_every_depth(depth: str) -> None:
    sonnet = route("ANTHROPIC", "claude-sonnet-5-5")
    for tuning in (COMPOSE_TUNINGS[depth], EXPLAINER_TUNINGS[depth], BUILDER_TUNING):
        assert output_tokens_for(tuning.applied(sonnet)) == 128_000
    assert output_tokens_for(COMPOSE_TUNINGS[depth].applied(route("GEMINI", "gemini-3.8-flash"))) == 65_536


def test_a_route_cap_set_in_ai_routing_is_kept_and_never_passes_the_model_maximum() -> None:
    assert output_tokens_for(route("ANTHROPIC", "claude-sonnet-5-5", cap=8192)) == 8192
    assert output_tokens_for(route("GEMINI", "gemini-3.8-flash", cap=128_000)) == 65_536
    assert output_tokens_for(route("GEMINI", "gemini-3.8-flash"), 200_000) == 65_536
    assert output_tokens_for(route("ANTHROPIC", "claude-opus-5-5"), 1_000) == 1_000


def test_a_model_outside_the_catalogue_is_never_routed_and_keeps_the_router_default() -> None:
    unlisted = route("OPENAI", "gpt-unlisted")
    assert not any(route_allowed(unlisted, task) for task in DEFAULT_ROUTES)
    assert output_tokens_for(unlisted) == DEFAULT_MAX_OUTPUT_TOKENS == 4096
    assert output_tokens_for(route("OPENAI", "gpt-unlisted", cap=12_000)) == 12_000
