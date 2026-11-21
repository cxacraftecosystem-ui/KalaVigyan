from __future__ import annotations

PRESETS: list[dict] = [
    {
        "preset": "anthropic",
        "kind": "anthropic",
        "label": "Anthropic (Claude)",
        "base_url": None,
        "needs_key": True,
        "key_env": "ANTHROPIC_API_KEY",
        "docs_url": "https://docs.claude.com/en/api/overview",
    },
    {
        "preset": "openai",
        "kind": "openai",
        "label": "OpenAI",
        "base_url": "https://api.openai.com/v1",
        "needs_key": True,
        "key_env": "OPENAI_API_KEY",
        "docs_url": "https://platform.openai.com/docs/api-reference",
    },
    {
        "preset": "gemini",
        "kind": "gemini",
        "label": "Google Gemini",
        "base_url": None,
        "needs_key": True,
        "key_env": "GEMINI_API_KEY",
        "docs_url": "https://ai.google.dev/gemini-api/docs",
    },
    {
        "preset": "deepseek",
        "kind": "openai_compatible",
        "label": "DeepSeek",
        "base_url": "https://api.deepseek.com",
        "needs_key": True,
        "key_env": "DEEPSEEK_API_KEY",
        "docs_url": "https://api-docs.deepseek.com/",
    },
    {
        "preset": "elevenlabs",
        "kind": "elevenlabs",
        "label": "ElevenLabs",
        "base_url": "https://api.elevenlabs.io",
        "needs_key": True,
        "key_env": "ELEVENLABS_API_KEY",
        "docs_url": "https://elevenlabs.io/docs/api-reference/introduction",
    },
    {
        "preset": "voyage",
        "kind": "voyage",
        "label": "Voyage AI",
        "base_url": "https://api.voyageai.com/v1",
        "needs_key": True,
        "key_env": "VOYAGE_API_KEY",
        "docs_url": "https://docs.voyageai.com/docs/reranker",
    },
]

BY_PRESET = {p["preset"]: p for p in PRESETS}

ALLOWED_KEY_NAMES = frozenset(p["key_env"] for p in PRESETS)
