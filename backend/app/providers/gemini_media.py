from __future__ import annotations

import base64
import binascii
from collections.abc import Mapping
from dataclasses import replace
from typing import Any
from urllib.parse import quote

import httpx

from app.core.errors import RETRYABLE_KINDS, InvalidInput, failure_kind
from app.core.retry_after import parse_headers

from .base import (
    BilledFailure,
    MediaPoll,
    MediaRequest,
    MediaResult,
    ProviderError,
    billed_failure,
    billed_on_failure,
)

__all__ = [
    "API_REVISION",
    "GEMINI_API",
    "GEMINI_KEY_NAME",
    "SERVICE",
    "SPEECH_LANGUAGES",
    "SPEECH_MODEL",
    "SPEECH_VOICE",
    "GeminiMediaWire",
    "interaction_body",
    "interaction_poll",
    "speech_audio",
    "speech_body",
]

GEMINI_API = "https://generativelanguage.googleapis.com/v1beta"
API_REVISION = "2026-05-20"
SERVICE = "gemini"
GEMINI_KEY_NAME = "GEMINI_API_KEY"
KEY_HEADER = "x-goog-api-key"
REQUEST_TIMEOUT = httpx.Timeout(240.0, connect=10.0)
OPEN_STATUSES = frozenset({"in_progress"})
DONE_STATUSES = frozenset({"completed", "incomplete"})
STOPPED_STATUSES = frozenset({"failed", "cancelled", "requires_action", "requires_continuation"})
BLOCK_WORDS = ("safety", "policy", "policies", "blocked", "prohibited", "responsible ai", "filtered")
OUTPUT_TYPES = {"IMAGE": "image", "VIDEO": "video"}
SPEECH_MODEL = "gemini-3.8-flash-tts"
SPEECH_VOICE = "Kore"
SPEECH_LANGUAGES = frozenset({"en", "hi", "bn", "ta", "te", "mr", "gu", "kn", "ml", "or", "pa", "as"})
SPEECH_BLOCK = "audio"
WAV_MAGIC = b"RIFF"


class GeminiMediaWire:
    def __init__(self, *, api_key: str, client: httpx.AsyncClient, base_url: str = GEMINI_API) -> None:
        if not api_key:
            raise ProviderError("Gemini requires an API key", kind="auth", service=SERVICE)
        self._api_key = api_key
        self._client = client
        self._base = base_url.rstrip("/")

    async def generate_image(self, req: MediaRequest) -> MediaResult:
        body = await self._json("POST", "/interactions", json=interaction_body(req, background=False))
        poll = interaction_poll(body, req.kind)
        if not poll.done or poll.result is None:
            raise BilledFailure("Gemini left an image interaction open", kind="error", service=SERVICE)
        return await self._with_data(poll.result, body, req.kind)

    async def start_video(self, req: MediaRequest) -> str:
        body = await self._json("POST", "/interactions", json=interaction_body(req, background=True))
        ref = body.get("id")
        if not isinstance(ref, str) or not ref:
            raise _off_contract("a started interaction without an id")
        return ref

    async def poll_video(self, ref: str) -> MediaPoll:
        with billed_on_failure():
            body = await self._json("GET", f"/interactions/{_segment(ref)}")
        poll = interaction_poll(body, "VIDEO")
        if poll.result is None:
            return poll
        return MediaPoll(done=True, result=await self._with_data(poll.result, body, "VIDEO"))

    async def forget(self, ref: str) -> None:
        await self._send("DELETE", f"/interactions/{_segment(ref)}")

    async def read_aloud(self, text: str, *, voice: str = SPEECH_VOICE) -> bytes:
        if not text.strip():
            raise InvalidInput(f"{SPEECH_MODEL} reads aloud a text that is not blank")
        return speech_audio(await self._json("POST", "/interactions", json=speech_body(text, voice=voice)))

    async def _with_data(self, result: MediaResult, body: Mapping[str, Any], kind: str) -> MediaResult:
        if result.data:
            return result
        with billed_on_failure():
            uri = (_output_block(body, OUTPUT_TYPES[kind]) or {}).get("uri")
            if not isinstance(uri, str):
                raise _off_contract("a media block with neither data nor uri")
            data = (await self._send("GET", _download_path(self._base, uri), params={"alt": "media"})).content
            if not data:
                raise _off_contract("an empty media download")
        return replace(result, data=data)

    async def _json(self, method: str, path: str, **request: Any) -> dict[str, Any]:
        answer = await self._send(method, path, **request)
        try:
            body = answer.json()
        except ValueError:
            raise _off_contract(f"{method} {path} answered without JSON") from None
        if not isinstance(body, dict):
            raise _off_contract(f"{method} {path} answered a non-object")
        return body

    async def _send(self, method: str, path: str, **request: Any) -> httpx.Response:
        headers = {KEY_HEADER: self._api_key, "Api-Revision": API_REVISION}
        try:
            answer = await self._client.request(
                method, f"{self._base}{path}", headers=headers, timeout=REQUEST_TIMEOUT, **request
            )
        except httpx.HTTPError as error:
            raise ProviderError(
                f"Cannot reach Gemini ({type(error).__name__})",
                kind="unavailable",
                retryable=True,
                service=SERVICE,
            ) from None
        if answer.is_success:
            return answer
        raise _http_failure(answer)


def interaction_body(req: MediaRequest, *, background: bool) -> dict[str, Any]:
    output_type = OUTPUT_TYPES.get(req.kind)
    if output_type is None:
        raise ProviderError(f"Gemini makes no {req.kind!r} media here", kind="bad_request", service=SERVICE)
    body: dict[str, Any] = {
        "model": req.model,
        "input": req.prompt,
        "response_format": {"type": output_type, **req.output},
        "background": background,
    }
    if not background:
        body["store"] = False
    return body


def speech_body(text: str, *, voice: str) -> dict[str, Any]:
    return {
        "model": SPEECH_MODEL,
        "input": [{"type": "user_input", "content": [{"type": "text", "text": text}]}],
        "response_format": {"type": SPEECH_BLOCK},
        "generation_config": {"speech_config": [{"voice": voice}]},
    }


def speech_audio(body: Mapping[str, Any]) -> bytes:
    status = body.get("status")
    if status in STOPPED_STATUSES:
        raise _stopped(body, str(status))
    if status not in DONE_STATUSES:
        raise _off_contract(f"a speech interaction status {status!r}")
    block = _output_block(body, SPEECH_BLOCK)
    if block is None:
        raise ProviderError(f"Gemini finished without speech ({status})", kind="refusal", service=SERVICE)
    audio = _decoded(block.get("data"))
    if not audio.startswith(WAV_MAGIC):
        raise _off_contract("speech that is not a WAV file")
    return audio


def interaction_poll(body: Mapping[str, Any], kind: str) -> MediaPoll:
    status = body.get("status")
    if status in OPEN_STATUSES:
        return MediaPoll(done=False)
    if status in STOPPED_STATUSES:
        raise _stopped(body, str(status))
    if status not in DONE_STATUSES:
        raise billed_failure(_off_contract(f"an interaction status {status!r}"))
    block = _output_block(body, OUTPUT_TYPES[kind])
    if block is None:
        raise ProviderError(
            f"Gemini finished without {OUTPUT_TYPES[kind]} output ({status})", kind="refusal", service=SERVICE
        )
    with billed_on_failure():
        result = _result(body, block, kind)
    return MediaPoll(done=True, result=result)


def _result(body: Mapping[str, Any], block: Mapping[str, Any], kind: str) -> MediaResult:
    usage = body.get("usage") if isinstance(body.get("usage"), dict) else {}
    mime = block.get("mime_type")
    if not isinstance(mime, str) or not mime.startswith(f"{OUTPUT_TYPES[kind]}/"):
        raise _off_contract(f"a {OUTPUT_TYPES[kind]} block typed {mime!r}")
    return MediaResult(
        data=_decoded(block.get("data")),
        mime=mime,
        input_tokens=_count(usage.get("total_input_tokens")),
        output_tokens=_count(usage.get("total_output_tokens")),
        media_tokens=_modality_tokens(usage.get("output_tokens_by_modality"), OUTPUT_TYPES[kind]),
        provider_ref=body.get("id") if isinstance(body.get("id"), str) else None,
        served_model=body.get("model") if isinstance(body.get("model"), str) else None,
    )


def _output_block(body: Mapping[str, Any], block_type: str) -> Mapping[str, Any] | None:
    found: Mapping[str, Any] | None = None
    for step in body.get("steps") or []:
        if not isinstance(step, dict) or step.get("type") != "model_output":
            continue
        for block in step.get("content") or []:
            if isinstance(block, dict) and block.get("type") == block_type:
                found = block
    return found


def _decoded(data: Any) -> bytes:
    if data is None:
        return b""
    if not isinstance(data, str):
        raise _off_contract("media data that is not base64 text")
    try:
        return base64.b64decode(data, validate=True)
    except binascii.Error, ValueError:
        raise _off_contract("media data that is not base64") from None


def _modality_tokens(entries: Any, modality: str) -> int | None:
    if not isinstance(entries, list):
        return None
    counts = [
        _count(entry.get("tokens"))
        for entry in entries
        if isinstance(entry, dict) and str(entry.get("modality", "")).casefold() == modality
    ]
    known = [count for count in counts if count is not None]
    return sum(known) if known else None


def _count(value: Any) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) and value >= 0 else None


def _stopped(body: Mapping[str, Any], status: str) -> ProviderError:
    messages = " ".join(
        str(item.get("message", "")) for item in body.get("errors") or [] if isinstance(item, dict)
    )
    if _mentions_block(messages):
        return ProviderError(f"Gemini declined the media ({status})", kind="refusal", service=SERVICE)
    return ProviderError(
        f"Gemini stopped the media ({status})", kind="error", retryable=True, service=SERVICE
    )


def _http_failure(answer: httpx.Response) -> ProviderError:
    kind = failure_kind(answer.status_code)
    message = _error_message(answer)
    if kind == "bad_request" and _mentions_block(message):
        kind = "refusal"
    return ProviderError(
        f"Gemini answered {answer.status_code}: {message[:300]}",
        kind=kind,
        retryable=kind in RETRYABLE_KINDS,
        status=answer.status_code,
        retry_after=parse_headers(answer.headers),
        service=SERVICE,
    )


def _error_message(answer: httpx.Response) -> str:
    try:
        body = answer.json()
    except ValueError:
        return answer.reason_phrase or "no reason"
    error = body.get("error") if isinstance(body, dict) else None
    message = error.get("message") if isinstance(error, dict) else None
    return message if isinstance(message, str) and message else answer.reason_phrase or "no reason"


def _mentions_block(text: str) -> bool:
    lowered = text.casefold()
    return any(word in lowered for word in BLOCK_WORDS)


def _download_path(base: str, uri: str) -> str:
    prefix = f"{base}/files/"
    name = uri.removeprefix(prefix)
    if name == uri or not name or "/" in name:
        raise _off_contract("a media uri outside the Files API")
    return f"/files/{_segment(name.removesuffix(':download'))}:download"


def _segment(value: str) -> str:
    if not value:
        raise _off_contract("an empty interaction or file id")
    return quote(value, safe="")


def _off_contract(what: str) -> ProviderError:
    return ProviderError(f"Gemini answered off the documented shape: {what}", kind="error", service=SERVICE)
