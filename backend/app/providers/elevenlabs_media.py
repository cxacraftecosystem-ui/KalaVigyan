from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Mapping
from typing import Any

import httpx

from app.core.errors import ExternalFailure, InvalidInput

from .base import (
    Adapter,
    BilledFailure,
    ChatRequest,
    ChatResult,
    MediaPoll,
    MediaRequest,
    MediaResult,
    ProviderError,
    billed_on_failure,
)
from .elevenlabs import ELEVENLABS_API, ELEVENLABS_SERVICE, ElevenLabs, Generation

__all__ = [
    "AUDIO_MIME",
    "DOWNLOAD_MAX_BYTES",
    "IMAGE_POLLS_MAX",
    "IMAGE_POLL_SECONDS",
    "VIDEO_POLL_SECONDS",
    "ElevenLabsMediaAdapter",
    "image_body",
    "video_body",
]

AUDIO_MIME = "audio/mpeg"
IMAGE_POLL_SECONDS = 2.0
IMAGE_POLLS_MAX = 90
VIDEO_POLL_SECONDS = 10.0
DOWNLOAD_MAX_BYTES = 64 * 1024 * 1024
FAILURE_KINDS: Mapping[str, str] = {
    "moderated": "refusal",
    "invalid_parameters": "bad_request",
    "timeout": "unavailable",
    "dependency_failed": "unavailable",
    "internal_error": "unavailable",
}

Sleep = Callable[[float], Awaitable[None]]


class ElevenLabsMediaAdapter(Adapter):
    video_poll_seconds = VIDEO_POLL_SECONDS

    def __init__(
        self, *, client: httpx.AsyncClient | None = None, sleep: Sleep = asyncio.sleep, **kw: Any
    ) -> None:
        super().__init__(**kw)
        if not self.api_key:
            raise ProviderError("ElevenLabs requires an API key", kind="auth", service=ELEVENLABS_SERVICE)
        self._client = client
        self._owns_client = client is None
        self._sleep = sleep

    async def chat(self, req: ChatRequest) -> ChatResult:
        raise ProviderError(
            "ElevenLabs answers no chat through this adapter", kind="unavailable", service=ELEVENLABS_SERVICE
        )

    async def list_models(self) -> list[dict]:
        return []

    async def generate_audio(self, req: MediaRequest) -> MediaResult:
        seconds = _seconds(req)
        api = self._api()
        if req.kind == "MUSIC":
            audio = await _translated(api.music(req.prompt, seconds=seconds, model=req.model))
        elif req.kind == "SOUND_EFFECT":
            audio = await _translated(api.sound_effect(req.prompt, seconds=seconds, model=req.model))
        else:
            raise _bad_request(f"ElevenLabs makes no {req.kind!r} audio here")
        return MediaResult(audio, AUDIO_MIME, None, None, None, None, req.model)

    async def generate_image(self, req: MediaRequest) -> MediaResult:
        ref = await _translated(self._api().start_generation("image", image_body(req)))
        for _ in range(IMAGE_POLLS_MAX):
            poll = await self._poll("image", ref)
            if poll.result is not None:
                return poll.result
            await self._sleep(IMAGE_POLL_SECONDS)
        raise BilledFailure(
            f"ElevenLabs left image generation {ref} unfinished",
            kind="unavailable",
            retryable=True,
            service=ELEVENLABS_SERVICE,
        )

    async def start_video(self, req: MediaRequest) -> str:
        return await _translated(self._api().start_generation("video", video_body(req)))

    async def poll_video(self, ref: str) -> MediaPoll:
        return await self._poll("video", ref)

    async def aclose(self) -> None:
        if self._owns_client and self._client is not None:
            await self._client.aclose()
            self._client = None

    async def _poll(self, kind: str, ref: str) -> MediaPoll:
        api = self._api()
        with billed_on_failure():
            generation = await _translated(api.generation(kind, ref))
        if generation.open:
            return MediaPoll(done=False)
        if generation.status == "failed":
            raise _failed(generation)
        with billed_on_failure():
            data = await _translated(api.download(generation.content_url or "", limit=DOWNLOAD_MAX_BYTES))
        mime = generation.mime or ""
        return MediaPoll(done=True, result=MediaResult(data, mime, None, None, None, ref, None))

    def _api(self) -> ElevenLabs:
        if self._client is None:
            self._client = httpx.AsyncClient()
        return ElevenLabs(
            api_key=self.api_key or "", client=self._client, base_url=self.base_url or ELEVENLABS_API
        )


def image_body(req: MediaRequest) -> dict[str, Any]:
    return {
        "model_id": req.model,
        "prompt": req.prompt,
        "aspect_ratio": _output(req, "aspect_ratio"),
        "resolution": _output(req, "image_size"),
    }


def video_body(req: MediaRequest) -> dict[str, Any]:
    return {
        "model_id": req.model,
        "prompt": req.prompt,
        "aspect_ratio": _output(req, "aspect_ratio"),
        "resolution": _output(req, "resolution"),
        "duration_secs": _output(req, "duration").removesuffix("s"),
        "generate_audio": False,
        "enhance_prompt": False,
    }


async def _translated[T](call: Awaitable[T]) -> T:
    try:
        return await call
    except ProviderError:
        raise
    except ExternalFailure as failure:
        raise ProviderError(
            str(failure),
            kind=failure.kind,
            retryable=failure.retryable,
            status=failure.status,
            retry_after=failure.retry_after,
            service=ELEVENLABS_SERVICE,
        ) from None
    except InvalidInput as error:
        raise _bad_request(str(error)) from None


def _failed(generation: Generation) -> ProviderError:
    kind = FAILURE_KINDS.get(generation.failure_reason or "", "error")
    return ProviderError(
        f"ElevenLabs generation {generation.generation_id} failed ({generation.failure_reason})",
        kind=kind,
        retryable=kind == "unavailable",
        service=ELEVENLABS_SERVICE,
    )


def _seconds(req: MediaRequest) -> float:
    try:
        return float(_output(req, "seconds"))
    except ValueError:
        raise _bad_request(f"An ElevenLabs {req.kind} length is a number of seconds") from None


def _output(req: MediaRequest, name: str) -> str:
    value = req.output.get(name)
    if not value:
        raise _bad_request(f"An ElevenLabs {req.kind} request names its {name}")
    return value


def _bad_request(message: str) -> ProviderError:
    return ProviderError(message, kind="bad_request", service=ELEVENLABS_SERVICE)
