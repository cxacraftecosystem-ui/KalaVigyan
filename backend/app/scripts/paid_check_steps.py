from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

from app.core.errors import AppError
from app.providers.base import MediaRequest
from app.providers.elevenlabs import NARRATION_MODEL, ElevenLabs, audio_seconds
from app.providers.gemini_media import GeminiMediaWire
from app.voice.score_prompts import SCORE_MUSIC_PROMPT

from .paid_check_ledger import Recorder

__all__ = [
    "IMAGE_MODEL",
    "MUSIC_MODEL",
    "MUSIC_SECONDS",
    "NARRATIONS",
    "CheckResult",
    "PaidCheck",
    "image_check",
    "music_check",
    "narration_check",
    "narration_estimate",
]

NARRATION_USD_PER_THOUSAND_CHARACTERS = Decimal("0.30")
MUSIC_MODEL = "music_v2_5"
MUSIC_SECONDS = 10.0
MUSIC_USD_PER_SECOND = Decimal("0.275") / 60
IMAGE_MODEL = "gemini-3.1-flash-image"
IMAGE_USD = Decimal("0.067")
IMAGE_OUTPUT_USD_PER_TOKEN = Decimal(60) / 1_000_000
IMAGE_OUTPUT = {"aspect_ratio": "1:1", "image_size": "1K"}
IMAGE_PROMPT = (
    "Draw one stage of an Indian craft process as a clear, neutral documentary illustration: a length of "
    "plain cotton cloth soaking in a shallow metal vat of water. Rules: no text, letters or numbers; no logos; "
    "no faces of real people; no maps, borders or flags."
)
NARRATIONS = {
    "en": "Ajrakh cloth is printed with carved wooden blocks [in several stages], and it is washed between them.",
    "hi": "अजरख का कपड़ा नक्काशीदार लकड़ी के ठप्पों से [कई चरणों में] छापा जाता है, और हर चरण के बीच धोया जाता है।",
}


@dataclass(frozen=True)
class CheckResult:
    findings: dict[str, Any]
    fixtures: dict[str, bytes] = field(default_factory=dict)
    actual_usd: Decimal | None = None


@dataclass(frozen=True)
class PaidCheck:
    name: str
    estimate_usd: Decimal
    run: Callable[[], Awaitable[CheckResult]]


def narration_estimate(language: str) -> Decimal:
    return Decimal(len(NARRATIONS[language])) * NARRATION_USD_PER_THOUSAND_CHARACTERS / 1000


async def narration_check(
    eleven: ElevenLabs, recorder: Recorder, *, voice_id: str, language: str
) -> CheckResult:
    text = NARRATIONS[language]
    try:
        speech = await eleven.narration(text, voice_id=voice_id, language=language)
    except AppError as error:
        return _refused(recorder, "/with-timestamps", f"narration_{language}_refused.json", error)
    seconds = audio_seconds(len(speech.audio))
    findings = {
        "model": NARRATION_MODEL,
        "characters": len(text),
        "audioSeconds": round(seconds, 3),
        "charactersPerMinute": round(len(text) * 60 / seconds) if seconds else None,
        "alignmentSpellsTheText": len(speech.starts) == len(text),
        "lastCharacterEndsAt": speech.ends[-1] if speech.ends else None,
    }
    return CheckResult(findings, _recorded(recorder, "/with-timestamps", f"narration_{language}.json"))


async def music_check(eleven: ElevenLabs, recorder: Recorder) -> CheckResult:
    try:
        audio = await eleven.music(SCORE_MUSIC_PROMPT, seconds=MUSIC_SECONDS, model=MUSIC_MODEL)
    except AppError as error:
        return _refused(recorder, "/v1/music", "music_bed_refused.json", error)
    findings = {
        "model": MUSIC_MODEL,
        "askedSeconds": MUSIC_SECONDS,
        "heardSeconds": round(audio_seconds(len(audio)), 3),
        "bytes": len(audio),
    }
    return CheckResult(findings, {"music_bed.mp3": audio}, MUSIC_USD_PER_SECOND * Decimal(str(MUSIC_SECONDS)))


async def image_check(gemini: GeminiMediaWire, recorder: Recorder) -> CheckResult:
    request = MediaRequest(model=IMAGE_MODEL, prompt=IMAGE_PROMPT, kind="IMAGE", output=dict(IMAGE_OUTPUT))
    try:
        result = await gemini.generate_image(request)
    except AppError as error:
        return _refused(recorder, "/interactions", "image_refused.json", error)
    findings = {
        "model": IMAGE_MODEL,
        "servedModel": result.served_model,
        "mime": result.mime,
        "bytes": len(result.data),
        "inputTokens": result.input_tokens,
        "outputTokens": result.output_tokens,
        "imageTokens": result.media_tokens,
    }
    actual = (
        None if result.output_tokens is None else Decimal(result.output_tokens) * IMAGE_OUTPUT_USD_PER_TOKEN
    )
    return CheckResult(
        findings, _recorded(recorder, "/interactions", "image_completed_recorded.json"), actual
    )


def _recorded(recorder: Recorder, path_end: str, name: str) -> dict[str, bytes]:
    reply = recorder.last(path_end)
    return {} if reply is None else {name: reply.fixture()}


def _refused(recorder: Recorder, path_end: str, name: str, error: AppError) -> CheckResult:
    return CheckResult({"refused": str(error)[:500]}, _recorded(recorder, path_end, name))
