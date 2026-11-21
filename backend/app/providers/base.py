from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from collections.abc import Sequence
from dataclasses import dataclass, field

from app.core.errors import ExternalFailure

logger = logging.getLogger(__name__)

FORMAT_REFUSAL_KIND = "error"


@dataclass
class ChatRequest:
    model: str
    system: str
    user: str
    max_tokens: int = 2048
    temperature: float | None = None
    reasoning: bool = False
    reasoning_effort: str | None = None
    reasoning_budget: int | None = None
    json_schema: dict | None = None


@dataclass
class ChatResult:
    text: str
    input_tokens: int | None = None
    output_tokens: int | None = None
    latency_ms: int = 0
    meta: dict = field(default_factory=dict)
    cached_input_tokens: int | None = None
    cache_write_tokens: int | None = None


class ProviderError(ExternalFailure):
    pass


def names_the_format(message: str, needles: Sequence[str]) -> bool:
    low = message.lower()
    return any(needle in low for needle in needles)


def format_refused(service: str, model: str) -> ProviderError:
    logger.warning("%s refused the structured output format for %s; the next route answers", service, model)
    return ProviderError(
        f"{service} refused the structured output format for {model}", status=400, kind=FORMAT_REFUSAL_KIND
    )


@dataclass(frozen=True)
class RerankRequest:
    model: str
    query: str
    documents: tuple[str, ...]


@dataclass(frozen=True)
class RerankResult:
    scores: tuple[tuple[int, float], ...]
    total_tokens: int | None
    latency_ms: int = 0


@dataclass(frozen=True)
class MediaRequest:
    model: str
    prompt: str
    kind: str
    output: dict[str, str]


@dataclass(frozen=True)
class MediaResult:
    data: bytes
    mime: str
    input_tokens: int | None
    output_tokens: int | None
    media_tokens: int | None
    provider_ref: str | None
    served_model: str | None


@dataclass(frozen=True)
class MediaPoll:
    done: bool
    result: MediaResult | None = None


class Adapter(ABC):
    learned: dict[str, list[str]]
    video_poll_seconds: float = 0.0

    def __init__(self, *, api_key: str | None, base_url: str | None, preset: str, extra: dict, learned: dict):
        self.api_key = api_key
        self.base_url = base_url
        self.preset = preset
        self.extra = extra or {}
        self.learned = {k: list(v) for k, v in (learned or {}).items()}
        self.learned_changed = False

    def rejects(self, model: str, param: str) -> bool:
        return param in self.learned.get(model, [])

    def learn(self, model: str, param: str) -> None:
        lst = self.learned.setdefault(model, [])
        if param not in lst:
            lst.append(param)
            self.learned_changed = True

    @abstractmethod
    async def chat(self, req: ChatRequest) -> ChatResult: ...

    @abstractmethod
    async def list_models(self) -> list[dict]: ...

    async def embed(self, texts: list[str], model: str, dimensions: int | None = None) -> list[list[float]]:
        raise ProviderError(
            f"{self.preset} does not provide embeddings through this adapter", kind="unavailable"
        )

    async def rerank(self, req: RerankRequest) -> RerankResult:
        raise ProviderError(f"{self.preset} does not rerank through this adapter", kind="unavailable")

    async def generate_image(self, req: MediaRequest) -> MediaResult:
        raise ProviderError(f"{self.preset} does not make images through this adapter", kind="unavailable")

    async def generate_audio(self, req: MediaRequest) -> MediaResult:
        raise ProviderError(f"{self.preset} does not make audio through this adapter", kind="unavailable")

    async def start_video(self, req: MediaRequest) -> str:
        raise ProviderError(f"{self.preset} does not make video through this adapter", kind="unavailable")

    async def poll_video(self, ref: str) -> MediaPoll:
        raise ProviderError(f"{self.preset} does not make video through this adapter", kind="unavailable")

    async def forget_media(self, ref: str) -> None:
        return None

    async def aclose(self) -> None:
        return None
