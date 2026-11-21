from __future__ import annotations

from typing import Any

from .base import Adapter, ProviderError
from .presets import ALLOWED_KEY_NAMES, BY_PRESET


def key_name_refusal(name: str | None, preset_key_env: str | None) -> str | None:
    if name and (name == preset_key_env or name in ALLOWED_KEY_NAMES):
        return None
    return (
        f"apiKeySecretKey {str(name)[:100]!r} is not allowed: a provider reads its key only from "
        f"{', '.join(sorted(ALLOWED_KEY_NAMES))}"
    )


def build_adapter(
    *,
    preset: str,
    kind: str,
    api_key: str | None,
    api_key_name: str | None,
    base_url: str | None = None,
    extra: dict[str, Any] | None = None,
    learned: dict[str, list[str]] | None = None,
) -> Adapter:
    spec = BY_PRESET.get(preset)
    if spec is None:
        raise ProviderError(f"Unknown provider preset '{preset}'", kind="unavailable")
    refused = key_name_refusal(api_key_name, spec.get("key_env"))
    if refused:
        raise ProviderError(refused, kind="auth")
    if spec.get("needs_key") and not api_key:
        raise ProviderError(f"{spec['label']} has no API key configured", kind="auth")
    base = base_url if base_url is not None else spec.get("base_url")
    kw: dict[str, Any] = {
        "api_key": api_key,
        "base_url": base,
        "preset": preset,
        "extra": extra or {},
        "learned": learned or {},
    }
    if kind == "anthropic":
        from .anthropic_p import AnthropicAdapter

        return AnthropicAdapter(**kw)
    if kind == "gemini":
        from .gemini_p import GeminiAdapter

        return GeminiAdapter(**kw)
    if kind in {"openai", "openai_compatible"}:
        from .openai_p import OpenAICompatAdapter

        if not base:
            raise ProviderError("This endpoint has no base URL configured", kind="unavailable")
        return OpenAICompatAdapter(native=kind == "openai", **kw)
    if kind == "elevenlabs":
        from .elevenlabs_media import ElevenLabsMediaAdapter

        return ElevenLabsMediaAdapter(**kw)
    if kind == "voyage":
        from .voyage_p import VoyageAdapter

        return VoyageAdapter(**kw)
    raise ProviderError(f"Unknown provider kind '{kind}'", kind="unavailable")


def merge_learned(current: dict | None, learned: dict) -> dict:
    merged = {k: list(v) for k, v in (current or {}).items()}
    for model, params in learned.items():
        existing = merged.setdefault(model, [])
        existing += [p for p in params if p not in existing]
    return merged
