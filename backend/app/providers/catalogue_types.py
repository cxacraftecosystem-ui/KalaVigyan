from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from enum import StrEnum

__all__ = [
    "AUDIO_TASKS",
    "CHAT_TASKS",
    "CLAUDE_MAX_OUTPUT_TOKENS",
    "DEEPSEEK_MAX_OUTPUT_TOKENS",
    "GEMINI_MAX_OUTPUT_TOKENS",
    "GEMINI_TTS_MAX_OUTPUT_TOKENS",
    "MEDIA_TASKS",
    "OPENAI_MAX_OUTPUT_TOKENS",
    "PRICES_CHECKED_ON",
    "PUBLIC_TEXT_TASKS",
    "RESEARCH_TEXT_TASKS",
    "TASK_LABELS",
    "TEXT_AND_VISION",
    "TEXT_TASKS",
    "UNKNOWN_TOKEN_PRICE",
    "UNKNOWN_UNIT_PRICE",
    "AiModel",
    "AiProvider",
    "AiTask",
    "ProviderSpec",
]


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
    UNDERSTAND = "UNDERSTAND"


TEXT_TASKS = frozenset({AiTask.PROOFREAD, AiTask.EXPAND, AiTask.SUMMARISE, AiTask.TRANSLATE})
TEXT_AND_VISION = TEXT_TASKS | {AiTask.CAPTION}
RESEARCH_TEXT_TASKS = frozenset(
    {
        AiTask.PLAN,
        AiTask.UNDERSTAND,
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
    AiTask.PLAN: "Plan research",
    AiTask.UNDERSTAND: "Understand the question",
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
