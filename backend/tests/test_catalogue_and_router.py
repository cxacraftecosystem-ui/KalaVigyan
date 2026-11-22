from decimal import Decimal

import pytest

from app.providers.catalogue import (
    DEFAULT_ROUTES,
    MEDIA_TASKS,
    PROVIDERS,
    PUBLIC_TEXT_TASKS,
    AiProvider,
    AiTask,
    allows_data,
    catalogue,
    looks_like_key,
    supports,
)
from app.providers.router import RouteChoice, estimate_for, order_routes, route_allowed


def test_deepseek_is_registered_as_public_text_only() -> None:
    assert PROVIDERS[AiProvider.DEEPSEEK].data_class == "PUBLIC_TEXT_ONLY"
    assert PROVIDERS[AiProvider.DEEPSEEK].base_url == "https://api.deepseek.com"


@pytest.mark.parametrize("task", list(AiTask))
def test_deepseek_only_takes_public_text(task: AiTask) -> None:
    allowed = allows_data(AiProvider.DEEPSEEK, task)
    assert allowed == (task in PUBLIC_TEXT_TASKS)
    assert supports("DEEPSEEK", "deepseek-flash", task) == (task in PUBLIC_TEXT_TASKS)


def test_every_default_route_is_supported() -> None:
    for task, entries in DEFAULT_ROUTES.items():
        assert entries
        for provider, model in entries:
            assert supports(provider, model, task), (task, provider, model)


def test_default_routes_follow_plan_first_choices() -> None:
    assert DEFAULT_ROUTES[AiTask.COMPOSE][0] == (AiProvider.ANTHROPIC, "claude-sonnet-5-5")
    assert DEFAULT_ROUTES[AiTask.PLAN][0] == (AiProvider.GEMINI, "gemini-3.5-flash-lite")
    assert DEFAULT_ROUTES[AiTask.EMBED] == ((AiProvider.GEMINI, "gemini-embedding-2"),)
    assert DEFAULT_ROUTES[AiTask.VIDEO] == ((AiProvider.GEMINI, "gemini-omni-1.2-flash"),)
    assert DEFAULT_ROUTES[AiTask.TRANSLATE][0] == (AiProvider.GEMINI, "gemini-3.8-flash")


def test_supports_rejects_unknowns() -> None:
    assert not supports("MISTRAL", "x", AiTask.COMPOSE)
    assert not supports("ANTHROPIC", "claude-unknown", AiTask.COMPOSE)
    assert not supports("ANTHROPIC", "claude-sonnet-5-5", "NOT_A_TASK")
    assert not supports("ANTHROPIC", "claude-sonnet-5-5", AiTask.TRANSCRIBE)
    assert not supports("GEMINI", "gemini-embedding-2", AiTask.COMPOSE)
    assert supports("gemini", "gemini-embedding-2", "embed")


def test_media_models_only_do_media() -> None:
    for spec in PROVIDERS.values():
        for model in spec.models:
            if model.tasks & MEDIA_TASKS:
                assert model.tasks <= MEDIA_TASKS
                assert model.unit in {"image", "second"}


def test_key_shapes() -> None:
    assert looks_like_key("ANTHROPIC", "sk-ant-abc")
    assert not looks_like_key("ANTHROPIC", "sk-abc")
    assert looks_like_key("GEMINI", "AIzaXYZ")
    assert not looks_like_key("NOPE", "x")


def test_catalogue_lists_deepseek_tasks_honestly() -> None:
    entry = next(p for p in catalogue() if p["provider"] == "DEEPSEEK")
    for model in entry["models"]:
        assert set(model["tasks"]) <= {"WEB_READ", "EXTRACT"}
        assert model["priceVerified"] is False


def choice(provider: str, model: str, ordinal: int, data_class: str = "ANY") -> RouteChoice:
    return RouteChoice(
        ordinal=ordinal,
        provider=provider,
        provider_id=None,
        preset=provider.lower(),
        kind="x",
        base_url=None,
        key_name=f"{provider}_API_KEY",
        model=model,
        data_class=data_class,
    )


def test_public_text_provider_row_is_refused_for_private_tasks() -> None:
    row = choice("DEEPSEEK", "deepseek-v4-pro", 1, "PUBLIC_TEXT_ONLY")
    assert route_allowed(row, AiTask.EXTRACT)
    assert not route_allowed(row, AiTask.COMPOSE)
    forced = choice("GEMINI", "gemini-3.8-flash", 1, "PUBLIC_TEXT_ONLY")
    assert not route_allowed(forced, AiTask.COMPOSE)
    assert route_allowed(forced, AiTask.WEB_READ)


def zero(_: RouteChoice) -> Decimal:
    return Decimal(0)


def test_order_routes_keeps_ordinal_and_drops_unsupported() -> None:
    routes = [
        choice("OPENAI", "gpt-6.1-terra", 3),
        choice("ANTHROPIC", "claude-sonnet-5-5", 1),
        choice("DEEPSEEK", "deepseek-flash", 2, "PUBLIC_TEXT_ONLY"),
        choice("GEMINI", "gemini-3.8-flash", 4),
    ]
    ordered = order_routes(AiTask.COMPOSE, routes, degrade=False, estimate=zero)
    assert [r.provider for r in ordered] == ["ANTHROPIC", "OPENAI", "GEMINI"]


def test_degrade_prefers_cheaper_composer() -> None:
    routes = [choice("ANTHROPIC", "claude-sonnet-5-5", 1), choice("GEMINI", "gemini-3.8-flash", 2)]

    def estimate(r: RouteChoice) -> Decimal:
        return estimate_for(
            r, AiTask.COMPOSE, prompt_tokens=12_000, max_tokens=1_200, units=None, overrides={}
        )

    normal = order_routes(AiTask.COMPOSE, routes, degrade=False, estimate=estimate)
    degraded = order_routes(AiTask.COMPOSE, routes, degrade=True, estimate=estimate)
    assert normal[0].provider == "ANTHROPIC"
    assert degraded[0].provider == "GEMINI"


def test_degrade_does_not_reorder_judge() -> None:
    routes = [choice("ANTHROPIC", "claude-opus-5-5", 1), choice("GEMINI", "gemini-4-argon", 2)]
    ordered = order_routes(
        AiTask.EVAL_JUDGE, routes, degrade=True, estimate=lambda r: Decimal(r.ordinal * -1)
    )
    assert ordered[0].provider == "ANTHROPIC"


def test_media_estimates_use_units() -> None:
    image = choice("GEMINI", "gemini-3.1-flash-image", 1)
    assert estimate_for(
        image, AiTask.IMAGE, prompt_tokens=100, max_tokens=0, units=2, overrides={}
    ) == Decimal("0.134000")


def test_elevenlabs_makes_only_media_with_the_listen_key_and_scores_by_default() -> None:
    spec = PROVIDERS[AiProvider.ELEVENLABS]
    assert (spec.managed_key, spec.preset, spec.kind) == ("ELEVENLABS_API_KEY", "elevenlabs", "elevenlabs")
    assert all(model.tasks <= MEDIA_TASKS and not model.price_verified for model in spec.models)
    assert DEFAULT_ROUTES[AiTask.MUSIC] == ((AiProvider.ELEVENLABS, "music_v2_5"),)
    assert DEFAULT_ROUTES[AiTask.SOUND_EFFECT] == ((AiProvider.ELEVENLABS, "eleven_text_to_sound_v3"),)
    assert all(provider == AiProvider.GEMINI for provider, _ in DEFAULT_ROUTES[AiTask.IMAGE])
    assert supports("ELEVENLABS", "veo-3.1-fast-generate-001", AiTask.VIDEO)
    assert supports("ELEVENLABS", "gemini-3.1-flash-image", AiTask.IMAGE)
    assert not supports("ELEVENLABS", "music_v2_5", AiTask.COMPOSE)
    assert {AiTask.MUSIC, AiTask.SOUND_EFFECT} <= MEDIA_TASKS
