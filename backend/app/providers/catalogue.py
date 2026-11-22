from __future__ import annotations

from .catalogue_specs import PROVIDERS
from .catalogue_types import (
    AUDIO_TASKS,
    CHAT_TASKS,
    CLAUDE_MAX_OUTPUT_TOKENS,
    DEEPSEEK_MAX_OUTPUT_TOKENS,
    GEMINI_MAX_OUTPUT_TOKENS,
    GEMINI_TTS_MAX_OUTPUT_TOKENS,
    MEDIA_TASKS,
    OPENAI_MAX_OUTPUT_TOKENS,
    PRICES_CHECKED_ON,
    PUBLIC_TEXT_TASKS,
    RESEARCH_TEXT_TASKS,
    TASK_LABELS,
    TEXT_AND_VISION,
    TEXT_TASKS,
    UNKNOWN_TOKEN_PRICE,
    UNKNOWN_UNIT_PRICE,
    AiModel,
    AiProvider,
    AiTask,
    ProviderSpec,
)

__all__ = [
    "AUDIO_TASKS",
    "CHAT_TASKS",
    "CLAUDE_MAX_OUTPUT_TOKENS",
    "DEEPSEEK_MAX_OUTPUT_TOKENS",
    "DEFAULT_ROUTES",
    "GEMINI_MAX_OUTPUT_TOKENS",
    "GEMINI_TTS_MAX_OUTPUT_TOKENS",
    "MEDIA_TASKS",
    "OPENAI_MAX_OUTPUT_TOKENS",
    "PRICES_CHECKED_ON",
    "PROVIDERS",
    "PUBLIC_TEXT_TASKS",
    "RESEARCH_TEXT_TASKS",
    "ROUTABLE_TASKS",
    "TASK_LABELS",
    "TEXT_AND_VISION",
    "TEXT_TASKS",
    "UNKNOWN_TOKEN_PRICE",
    "UNKNOWN_UNIT_PRICE",
    "AiModel",
    "AiProvider",
    "AiTask",
    "ProviderSpec",
    "allows_data",
    "catalogue",
    "default_model_for",
    "looks_like_key",
    "model_for",
    "models_for",
    "output_limit",
    "provider_of",
    "spec_for",
    "supports",
    "task_of",
]

DEFAULT_ROUTES: dict[AiTask, tuple[tuple[AiProvider, str], ...]] = {
    AiTask.PLAN: (
        (AiProvider.GEMINI, "gemini-3.5-flash-lite"),
        (AiProvider.ANTHROPIC, "claude-haiku-5-5"),
        (AiProvider.OPENAI, "gpt-6-luna"),
    ),
    AiTask.WEB_READ: (
        (AiProvider.GEMINI, "gemini-3.5-flash-lite"),
        (AiProvider.DEEPSEEK, "deepseek-flash"),
        (AiProvider.ANTHROPIC, "claude-haiku-5-5"),
    ),
    AiTask.COMPOSE: (
        (AiProvider.ANTHROPIC, "claude-sonnet-5-5"),
        (AiProvider.GEMINI, "gemini-3.8-flash"),
        (AiProvider.OPENAI, "gpt-6.1-terra"),
    ),
    AiTask.VOICE_TURN: (
        (AiProvider.GEMINI, "gemini-3.8-flash"),
        (AiProvider.ANTHROPIC, "claude-haiku-5-5"),
        (AiProvider.OPENAI, "gpt-6-luna"),
    ),
    AiTask.INTERVIEW: (
        (AiProvider.GEMINI, "gemini-3.8-flash"),
        (AiProvider.ANTHROPIC, "claude-haiku-5-5"),
        (AiProvider.OPENAI, "gpt-6-luna"),
    ),
    AiTask.TESTIMONY: (
        (AiProvider.ANTHROPIC, "claude-sonnet-5-5"),
        (AiProvider.GEMINI, "gemini-3.8-flash"),
        (AiProvider.OPENAI, "gpt-6.1-terra"),
    ),
    AiTask.TRANSLATE: (
        (AiProvider.GEMINI, "gemini-3.8-flash"),
        (AiProvider.ANTHROPIC, "claude-sonnet-5-5"),
        (AiProvider.OPENAI, "gpt-6.1-terra"),
    ),
    AiTask.EXTRACT: (
        (AiProvider.ANTHROPIC, "claude-sonnet-5-5"),
        (AiProvider.GEMINI, "gemini-3.8-flash"),
        (AiProvider.DEEPSEEK, "deepseek-v4-pro"),
    ),
    AiTask.SUMMARISE: (
        (AiProvider.GEMINI, "gemini-3.5-flash-lite"),
        (AiProvider.ANTHROPIC, "claude-haiku-5-5"),
        (AiProvider.OPENAI, "gpt-6-luna"),
    ),
    AiTask.EMBED: ((AiProvider.GEMINI, "gemini-embedding-2"),),
    AiTask.EVAL_JUDGE: ((AiProvider.ANTHROPIC, "claude-opus-5-5"), (AiProvider.GEMINI, "gemini-4-argon")),
    AiTask.IMAGE: (
        (AiProvider.GEMINI, "gemini-3.1-flash-image"),
        (AiProvider.GEMINI, "gemini-nano-banana-2.1"),
    ),
    AiTask.VIDEO: ((AiProvider.GEMINI, "gemini-omni-1.2-flash"),),
    AiTask.MUSIC: ((AiProvider.ELEVENLABS, "music_v2_5"),),
    AiTask.SOUND_EFFECT: ((AiProvider.ELEVENLABS, "eleven_text_to_sound_v3"),),
    AiTask.RERANK: ((AiProvider.VOYAGE, "rerank-3"),),
}

ROUTABLE_TASKS: tuple[AiTask, ...] = tuple(DEFAULT_ROUTES)


def provider_of(provider: AiProvider | str) -> AiProvider | None:
    try:
        return provider if isinstance(provider, AiProvider) else AiProvider(str(provider).strip().upper())
    except ValueError:
        return None


def task_of(task: AiTask | str) -> AiTask | None:
    try:
        return task if isinstance(task, AiTask) else AiTask(str(task).strip().upper())
    except ValueError:
        return None


def spec_for(provider: AiProvider | str) -> ProviderSpec | None:
    key = provider_of(provider)
    return PROVIDERS.get(key) if key else None


def models_for(provider: AiProvider | str, task: AiTask | None = None) -> tuple[AiModel, ...]:
    spec = spec_for(provider)
    if spec is None:
        return ()
    if task is None:
        return spec.models
    return tuple(model for model in spec.models if task in model.tasks)


def model_for(provider: AiProvider | str, model_id: str) -> AiModel | None:
    spec = spec_for(provider)
    return spec.model(model_id) if spec else None


def output_limit(provider: AiProvider | str, model_id: str) -> int | None:
    model = model_for(provider, model_id)
    return model.max_output_tokens if model else None


def allows_data(provider: AiProvider | str, task: AiTask | str) -> bool:
    spec = spec_for(provider)
    resolved = task_of(task)
    if spec is None or resolved is None:
        return False
    return spec.data_class != "PUBLIC_TEXT_ONLY" or resolved in PUBLIC_TEXT_TASKS


def supports(provider: AiProvider | str, model_id: str, task: AiTask | str) -> bool:
    model = model_for(provider, model_id)
    resolved = task_of(task)
    if model is None or resolved is None or resolved not in model.tasks:
        return False
    return allows_data(provider, resolved)


def default_model_for(provider: AiProvider | str) -> str | None:
    spec = spec_for(provider)
    return spec.default_model if spec else None


def looks_like_key(provider: AiProvider | str, value: str) -> bool:
    spec = spec_for(provider)
    candidate = (value or "").strip()
    if spec is None or not candidate:
        return False
    return spec.key_prefix is None or candidate.startswith(spec.key_prefix)


def catalogue() -> list[dict]:
    return [
        {
            "provider": spec.provider.value,
            "label": spec.label,
            "managedKey": spec.managed_key,
            "consoleUrl": spec.console_url,
            "pricingUrl": spec.pricing_url,
            "dataClass": spec.data_class,
            "defaultModel": spec.default_model,
            "models": [
                {
                    "id": model.id,
                    "label": model.label,
                    "note": model.note,
                    "pricePerMTok": list(model.price_per_mtok) if model.price_per_mtok else None,
                    "pricePerUnit": model.price_per_unit,
                    "unit": model.unit,
                    "priceVerified": model.price_verified,
                    "maxOutputTokens": model.max_output_tokens,
                    "tasks": sorted(task.value for task in model.tasks if allows_data(spec.provider, task)),
                }
                for model in spec.models
            ],
        }
        for spec in PROVIDERS.values()
    ]
