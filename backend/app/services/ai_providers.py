from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from enum import StrEnum

PRICES_CHECKED_ON = "2026-11-15"
CLAUDE_MAX_OUTPUT_TOKENS = 128_000
GEMINI_MAX_OUTPUT_TOKENS = 65_536
GEMINI_TTS_MAX_OUTPUT_TOKENS = 16_384
OPENAI_MAX_OUTPUT_TOKENS = 128_000
DEEPSEEK_MAX_OUTPUT_TOKENS = 384_000


class AiProvider(StrEnum):
    OPENAI = "OPENAI"
    GEMINI = "GEMINI"
    ANTHROPIC = "ANTHROPIC"
    DEEPSEEK = "DEEPSEEK"
    ELEVENLABS = "ELEVENLABS"
    VOYAGE = "VOYAGE"


class AiTask(StrEnum):
    PROOFREAD = "PROOFREAD"
    EXPAND = "EXPAND"
    SUMMARISE = "SUMMARISE"
    TRANSLATE = "TRANSLATE"
    TRANSCRIBE = "TRANSCRIBE"
    CAPTION = "CAPTION"
    PLAN = "PLAN"
    COMPOSE = "COMPOSE"
    WEB_READ = "WEB_READ"
    EXTRACT = "EXTRACT"
    EMBED = "EMBED"
    IMAGE = "IMAGE"
    VIDEO = "VIDEO"
    VOICE_TURN = "VOICE_TURN"
    EVAL_JUDGE = "EVAL_JUDGE"
    MUSIC = "MUSIC"
    SOUND_EFFECT = "SOUND_EFFECT"
    INTERVIEW = "INTERVIEW"
    TESTIMONY = "TESTIMONY"
    RERANK = "RERANK"


TEXT_TASKS = frozenset({AiTask.PROOFREAD, AiTask.EXPAND, AiTask.SUMMARISE, AiTask.TRANSLATE})
TEXT_AND_VISION = TEXT_TASKS | {AiTask.CAPTION}
RESEARCH_TEXT_TASKS = frozenset(
    {
        AiTask.PLAN,
        AiTask.COMPOSE,
        AiTask.WEB_READ,
        AiTask.EXTRACT,
        AiTask.VOICE_TURN,
        AiTask.EVAL_JUDGE,
        AiTask.INTERVIEW,
        AiTask.TESTIMONY,
    }
)
PUBLIC_TEXT_TASKS = frozenset({AiTask.WEB_READ, AiTask.EXTRACT})
MEDIA_TASKS = frozenset({AiTask.IMAGE, AiTask.VIDEO, AiTask.MUSIC, AiTask.SOUND_EFFECT})
AUDIO_TASKS = frozenset({AiTask.MUSIC, AiTask.SOUND_EFFECT})
CHAT_TASKS = TEXT_AND_VISION | RESEARCH_TEXT_TASKS

TASK_LABELS: dict[AiTask, str] = {
    AiTask.PROOFREAD: "Proofread",
    AiTask.EXPAND: "Expand",
    AiTask.SUMMARISE: "Summarise",
    AiTask.TRANSLATE: "Translate",
    AiTask.TRANSCRIBE: "Transcribe",
    AiTask.CAPTION: "Caption",
    AiTask.PLAN: "Plan and craft choice",
    AiTask.COMPOSE: "Compose answers",
    AiTask.WEB_READ: "Read web pages",
    AiTask.EXTRACT: "Extract claims",
    AiTask.EMBED: "Embeddings",
    AiTask.IMAGE: "Images",
    AiTask.VIDEO: "Video",
    AiTask.VOICE_TURN: "Voice turns",
    AiTask.EVAL_JUDGE: "Evaluation judge",
    AiTask.MUSIC: "Film music",
    AiTask.SOUND_EFFECT: "Film sound effects",
    AiTask.INTERVIEW: "Artisan conversations",
    AiTask.TESTIMONY: "Artisan testimony",
    AiTask.RERANK: "Rerank stored facts",
}

UNKNOWN_TOKEN_PRICE: tuple[float, float] = (5.0, 30.0)
UNKNOWN_UNIT_PRICE: dict[str, float] = {"image": 0.134, "second": 0.15}


@dataclass(frozen=True)
class AiModel:
    id: str
    label: str
    note: str
    price_per_mtok: tuple[float, float] | None
    tasks: frozenset[AiTask]
    price_per_unit: float | None = None
    unit: str | None = None
    price_changes: tuple[tuple[date, tuple[float, float]], ...] = field(default_factory=tuple)
    price_verified: bool = True
    max_output_tokens: int | None = None

    def token_price_on(self, day: date) -> tuple[float, float] | None:
        price = self.price_per_mtok
        for effective, changed in sorted(self.price_changes):
            if day >= effective:
                price = changed
        return price


@dataclass(frozen=True)
class ProviderSpec:
    provider: AiProvider
    label: str
    managed_key: str
    key_prefix: str | None
    console_url: str
    pricing_url: str
    preset: str
    kind: str
    base_url: str | None
    data_class: str
    models: tuple[AiModel, ...]
    default_model: str

    def model(self, model_id: str) -> AiModel | None:
        return next((m for m in self.models if m.id == model_id), None)


_OPENAI = ProviderSpec(
    provider=AiProvider.OPENAI,
    label="OpenAI",
    managed_key="OPENAI_API_KEY",
    key_prefix="sk-",
    console_url="https://platform.openai.com/api-keys",
    pricing_url="https://openai.com/api/pricing/",
    preset="openai",
    kind="openai",
    base_url="https://api.openai.com/v1",
    data_class="ANY",
    models=(
        AiModel(
            "gpt-6-luna",
            "GPT-6 Luna",
            "Cheapest fallback for planning and voice turns.",
            (0.10, 0.50),
            CHAT_TASKS,
            max_output_tokens=OPENAI_MAX_OUTPUT_TOKENS,
        ),
        AiModel(
            "gpt-6.1-terra",
            "GPT-6.1 Terra",
            "Composer fallback.",
            None,
            CHAT_TASKS,
            price_verified=False,
            max_output_tokens=OPENAI_MAX_OUTPUT_TOKENS,
        ),
        AiModel(
            "gpt-5.6-terra",
            "GPT-5.6 Terra",
            "Balanced previous generation.",
            (2.0, 12.0),
            CHAT_TASKS,
            max_output_tokens=OPENAI_MAX_OUTPUT_TOKENS,
        ),
        AiModel(
            "gpt-5.6-sol",
            "GPT-5.6 Sol",
            "Most capable previous generation.",
            (5.0, 30.0),
            CHAT_TASKS,
            max_output_tokens=OPENAI_MAX_OUTPUT_TOKENS,
        ),
        AiModel(
            "gpt-transcribe",
            "GPT Transcribe",
            "Transcription only.",
            None,
            frozenset({AiTask.TRANSCRIBE}),
            price_verified=False,
        ),
    ),
    default_model="gpt-6-luna",
)

_GEMINI = ProviderSpec(
    provider=AiProvider.GEMINI,
    label="Google Gemini",
    managed_key="GEMINI_API_KEY",
    key_prefix="AIza",
    console_url="https://aistudio.google.com/apikey",
    pricing_url="https://ai.google.dev/gemini-api/docs/pricing",
    preset="gemini",
    kind="gemini",
    base_url=None,
    data_class="ANY",
    models=(
        AiModel(
            "gemini-3.8-flash",
            "Gemini 3.8 Flash",
            "Fast default for voice turns and composer fallback.",
            (0.75, 3.75),
            CHAT_TASKS | {AiTask.TRANSCRIBE},
            price_changes=((date(2027, 1, 1), (1.50, 7.50)),),
            max_output_tokens=GEMINI_MAX_OUTPUT_TOKENS,
        ),
        AiModel(
            "gemini-3.7-flash",
            "Gemini 3.7 Flash",
            "Previous fast model.",
            (0.75, 3.75),
            CHAT_TASKS | {AiTask.TRANSCRIBE},
            max_output_tokens=GEMINI_MAX_OUTPUT_TOKENS,
        ),
        AiModel(
            "gemini-3.5-flash-lite",
            "Gemini 3.5 Flash-Lite",
            "Cheap planner and page reader.",
            (0.30, 2.50),
            CHAT_TASKS | {AiTask.TRANSCRIBE},
            max_output_tokens=GEMINI_MAX_OUTPUT_TOKENS,
        ),
        AiModel(
            "gemini-3.1-pro-preview",
            "Gemini 3.1 Pro (preview)",
            "Strong reasoning, preview.",
            (2.0, 12.0),
            CHAT_TASKS,
            max_output_tokens=GEMINI_MAX_OUTPUT_TOKENS,
        ),
        AiModel(
            "gemini-4-argon",
            "Gemini 4 Argon",
            "Second evaluation judge.",
            None,
            frozenset({AiTask.EVAL_JUDGE, AiTask.COMPOSE, AiTask.EXTRACT}),
            price_verified=False,
            max_output_tokens=GEMINI_MAX_OUTPUT_TOKENS,
        ),
        AiModel(
            "gemini-embedding-2",
            "Gemini Embedding 2",
            "1536-dimension embeddings.",
            (0.20, 0.0),
            frozenset({AiTask.EMBED}),
        ),
        AiModel(
            "gemini-3.1-flash-image",
            "Gemini 3.1 Flash Image",
            "Stage illustrations at 1K.",
            (0.50, 60.0),
            frozenset({AiTask.IMAGE}),
            price_per_unit=0.067,
            unit="image",
        ),
        AiModel(
            "gemini-nano-banana-2.1",
            "Nano Banana 2.1",
            "Draft illustrations.",
            (1.50, 30.0),
            frozenset({AiTask.IMAGE}),
            price_per_unit=0.0336,
            unit="image",
        ),
        AiModel(
            "gemini-omni-1.2-flash",
            "Gemini Omni 1.2 Flash",
            "Eight-second silent stage clips.",
            (1.50, 12.0),
            frozenset({AiTask.VIDEO}),
            price_per_unit=0.07,
            unit="second",
        ),
        AiModel(
            "gemini-3.8-flash-tts",
            "Gemini 3.8 Flash TTS",
            "Listen fallback when voice is down.",
            None,
            frozenset({AiTask.VOICE_TURN}),
            price_verified=False,
            max_output_tokens=GEMINI_TTS_MAX_OUTPUT_TOKENS,
        ),
    ),
    default_model="gemini-3.8-flash",
)

_ANTHROPIC = ProviderSpec(
    provider=AiProvider.ANTHROPIC,
    label="Anthropic Claude",
    managed_key="ANTHROPIC_API_KEY",
    key_prefix="sk-ant-",
    console_url="https://platform.claude.com/settings/keys",
    pricing_url="https://platform.claude.com/docs/en/pricing",
    preset="anthropic",
    kind="anthropic",
    base_url=None,
    data_class="ANY",
    models=(
        AiModel(
            "claude-sonnet-5-5",
            "Claude Sonnet 5.5",
            "Default composer and claim extractor.",
            (2.0, 10.0),
            CHAT_TASKS,
            max_output_tokens=CLAUDE_MAX_OUTPUT_TOKENS,
        ),
        AiModel(
            "claude-opus-5-5",
            "Claude Opus 5.5",
            "Evaluation judge.",
            (4.0, 20.0),
            CHAT_TASKS,
            max_output_tokens=CLAUDE_MAX_OUTPUT_TOKENS,
        ),
        AiModel(
            "claude-haiku-5-5",
            "Claude Haiku 5.5",
            "Cheap planner, reader and voice fallback.",
            (0.10, 0.50),
            CHAT_TASKS,
            max_output_tokens=CLAUDE_MAX_OUTPUT_TOKENS,
        ),
        AiModel(
            "claude-opus-5",
            "Claude Opus 5",
            "Previous Opus.",
            (5.0, 25.0),
            CHAT_TASKS,
            max_output_tokens=CLAUDE_MAX_OUTPUT_TOKENS,
        ),
        AiModel(
            "claude-sonnet-5",
            "Claude Sonnet 5",
            "Previous Sonnet.",
            (2.0, 10.0),
            CHAT_TASKS,
            max_output_tokens=CLAUDE_MAX_OUTPUT_TOKENS,
        ),
    ),
    default_model="claude-sonnet-5-5",
)

_DEEPSEEK = ProviderSpec(
    provider=AiProvider.DEEPSEEK,
    label="DeepSeek",
    managed_key="DEEPSEEK_API_KEY",
    key_prefix="sk-",
    console_url="https://platform.deepseek.com/api_keys",
    pricing_url="https://api-docs.deepseek.com/quick_start/pricing",
    preset="deepseek",
    kind="openai_compatible",
    base_url="https://api.deepseek.com",
    data_class="PUBLIC_TEXT_ONLY",
    models=(
        AiModel(
            "deepseek-flash",
            "DeepSeek Flash",
            "Public web page reading.",
            None,
            PUBLIC_TEXT_TASKS,
            price_verified=False,
            max_output_tokens=DEEPSEEK_MAX_OUTPUT_TOKENS,
        ),
        AiModel(
            "deepseek-v4-pro",
            "DeepSeek V4 Pro",
            "Public text claim extraction.",
            None,
            PUBLIC_TEXT_TASKS,
            price_verified=False,
            max_output_tokens=DEEPSEEK_MAX_OUTPUT_TOKENS,
        ),
    ),
    default_model="deepseek-flash",
)

_ELEVENLABS = ProviderSpec(
    provider=AiProvider.ELEVENLABS,
    label="ElevenLabs",
    managed_key="ELEVENLABS_API_KEY",
    key_prefix=None,
    console_url="https://elevenlabs.io/app/settings/api-keys",
    pricing_url="https://elevenlabs.io/pricing/api",
    preset="elevenlabs",
    kind="elevenlabs",
    base_url="https://api.elevenlabs.io",
    data_class="ANY",
    models=(
        AiModel(
            "music_v2_5",
            "Eleven Music v2.5",
            "Instrumental film beds.",
            None,
            frozenset({AiTask.MUSIC}),
            price_per_unit=0.275 / 60,
            unit="second",
            price_verified=False,
        ),
        AiModel(
            "music_v2",
            "Eleven Music v2",
            "Previous music model.",
            None,
            frozenset({AiTask.MUSIC}),
            price_per_unit=0.275 / 60,
            unit="second",
            price_verified=False,
        ),
        AiModel(
            "eleven_text_to_sound_v3",
            "Sound Effects v3",
            "Short film cues.",
            None,
            frozenset({AiTask.SOUND_EFFECT}),
            price_per_unit=0.12 / 60,
            unit="second",
            price_verified=False,
        ),
        AiModel(
            "gemini-3.1-flash-image",
            "Nano Banana 2 via ElevenLabs",
            "Stage illustrations at 1K through ElevenLabs.",
            None,
            frozenset({AiTask.IMAGE}),
            price_per_unit=0.07,
            unit="image",
            price_verified=False,
        ),
        AiModel(
            "veo-3.1-fast-generate-001",
            "Veo 3.1 Fast via ElevenLabs",
            "Eight-second silent stage clips through ElevenLabs.",
            None,
            frozenset({AiTask.VIDEO}),
            price_per_unit=0.10,
            unit="second",
            price_verified=False,
        ),
    ),
    default_model="music_v2_5",
)

_VOYAGE = ProviderSpec(
    provider=AiProvider.VOYAGE,
    label="Voyage AI",
    managed_key="VOYAGE_API_KEY",
    key_prefix=None,
    console_url="https://dash.voyageai.com",
    pricing_url="https://docs.voyageai.com/docs/pricing",
    preset="voyage",
    kind="voyage",
    base_url="https://api.voyageai.com/v1",
    data_class="ANY",
    models=(
        AiModel(
            "rerank-3",
            "Voyage Rerank 3",
            "Orders stored facts by their relevance to the question.",
            (0.05, 0.0),
            frozenset({AiTask.RERANK}),
        ),
    ),
    default_model="rerank-3",
)

PROVIDERS: dict[AiProvider, ProviderSpec] = {
    spec.provider: spec for spec in (_OPENAI, _GEMINI, _ANTHROPIC, _DEEPSEEK, _ELEVENLABS, _VOYAGE)
}

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


GEMINI_DECLINE_REASONS = frozenset(
    {"SAFETY", "PROHIBITED_CONTENT", "BLOCKLIST", "SPII", "RECITATION", "IMAGE_SAFETY"}
)


class ModelDeclined(RuntimeError):
    pass


def gemini_reply_text(payload: dict) -> str:
    candidates = payload.get("candidates") or []
    if not candidates:
        if (payload.get("promptFeedback") or {}).get("blockReason"):
            raise ModelDeclined("gemini")
        return ""
    first = candidates[0] or {}
    parts = (first.get("content") or {}).get("parts") or []
    text = "".join(str(part.get("text", "")) for part in parts if not part.get("thought")).strip()
    if not text and first.get("finishReason") in GEMINI_DECLINE_REASONS:
        raise ModelDeclined("gemini")
    return text
