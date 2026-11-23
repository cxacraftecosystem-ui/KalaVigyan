import base64
import io
import json
import wave
from pathlib import Path
from typing import Any

import httpx
import pytest

from app.core.errors import ExternalFailure, InvalidInput
from app.providers.base import ProviderError
from app.providers.catalogue import AiProvider, model_for
from app.providers.gemini_media import (
    SPEECH_LANGUAGES,
    SPEECH_MODEL,
    SPEECH_VOICE,
    GeminiMediaWire,
    speech_audio,
    speech_body,
)
from app.scripts.paid_check_steps import SPEECH_TEXT
from app.voice.listen_voices import GeminiVoice
from app.voice.narration import CHARACTERS_PER_MINUTE, NarrationPart, SpokenSentence
from app.voice.read_aloud import wav_frames

KEY = "test-only-gemini-key"
API = "https://generativelanguage.googleapis.com/v1beta"
WAV = b"RIFF" + bytes(4) + b"WAVEfmt "
FIXTURES = Path(__file__).parent / "fixtures"
RECORDED_RATE, RECORDED_SECONDS, RECORDED_CHARACTERS, RECORDED_FRAMES = 24_000, 5.44, 81, 1514


def recorded() -> dict[str, Any]:
    return json.loads((FIXTURES / "speech_completed.json").read_text(encoding="utf-8"))


def recorded_wire() -> GeminiMediaWire:
    reply = recorded()
    client = httpx.AsyncClient(transport=httpx.MockTransport(lambda _: httpx.Response(200, json=reply)))
    return GeminiMediaWire(api_key=KEY, client=client)


def answered(status: str = "completed", content: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    blocks = [{"type": "audio", "data": base64.b64encode(WAV).decode()}] if content is None else content
    return {"id": "speech-1", "status": status, "steps": [{"type": "model_output", "content": blocks}]}


def test_a_sentence_is_read_aloud_by_the_documented_interaction() -> None:
    assert speech_body("Alum fixes the red.", voice="Kore") == {
        "model": "gemini-3.8-flash-tts",
        "input": [{"type": "user_input", "content": [{"type": "text", "text": "Alum fixes the red."}]}],
        "response_format": {"type": "audio"},
        "generation_config": {"speech_config": [{"voice": "Kore"}]},
    }
    assert (SPEECH_MODEL, SPEECH_VOICE) == ("gemini-3.8-flash-tts", "Kore")
    assert model_for(AiProvider.GEMINI, SPEECH_MODEL) is not None


def test_the_read_aloud_languages_are_the_answer_languages_the_documented_table_lists() -> None:
    assert sorted(SPEECH_LANGUAGES) == sorted(
        ["en", "hi", "bn", "ta", "te", "mr", "gu", "kn", "ml", "or", "pa", "as"]
    )
    assert "ur" not in SPEECH_LANGUAGES


async def test_the_wire_posts_the_interaction_and_returns_its_wav() -> None:
    sent: list[httpx.Request] = []

    def answer(request: httpx.Request) -> httpx.Response:
        sent.append(request)
        return httpx.Response(200, json=answered())

    wire = GeminiMediaWire(api_key=KEY, client=httpx.AsyncClient(transport=httpx.MockTransport(answer)))
    assert await wire.read_aloud("Alum fixes the red.") == WAV
    (request,) = sent
    assert (request.method, str(request.url)) == ("POST", f"{API}/interactions")
    assert request.headers["x-goog-api-key"] == KEY
    assert json.loads(request.content) == speech_body("Alum fixes the red.", voice="Kore")
    with pytest.raises(InvalidInput):
        await wire.read_aloud("   ")


async def test_the_recorded_speech_is_the_documented_24_khz_mono_16_bit_wav_in_the_last_audio_block() -> None:
    reply = recorded()
    assert (reply["model"], reply["status"], reply["steps"][-1]["type"]) == (
        SPEECH_MODEL,
        "completed",
        "model_output",
    )
    audio = await recorded_wire().read_aloud(SPEECH_TEXT)
    with wave.open(io.BytesIO(audio), "rb") as read:
        shape = (read.getnchannels(), read.getsampwidth(), read.getframerate())
        declared = read.getnframes() / read.getframerate()
    assert (shape, declared) == ((1, 2, RECORDED_RATE), RECORDED_SECONDS)
    pcm = wav_frames(audio)
    assert (pcm.rate, pcm.count) == (RECORDED_RATE, RECORDED_FRAMES)


async def test_the_listen_voice_times_the_recorded_sentence_from_its_samples() -> None:
    part = NarrationPart(language="en", sentences=(SpokenSentence("lede.1", SPEECH_TEXT, "en"),))
    spoken = await GeminiVoice(reader=recorded_wire()).spoken([part], 0)
    [sentence] = spoken.sentences
    assert (sentence.sentence_id, sentence.start, sentence.end) == ("lede.1", 0.0, 0.063)
    assert spoken.words == [] and spoken.billed_seconds == 1


def test_gemini_read_the_recorded_sentence_slower_than_the_hold_assumes() -> None:
    assert len(SPEECH_TEXT) == RECORDED_CHARACTERS
    assert round(RECORDED_CHARACTERS * 60 / RECORDED_SECONDS) == 893 < CHARACTERS_PER_MINUTE


async def test_a_refusal_or_an_outage_is_a_gemini_failure_the_fallback_can_name() -> None:
    def refused(_: httpx.Request) -> httpx.Response:
        return httpx.Response(400, json={"error": {"message": "The text was blocked by a safety filter."}})

    wire = GeminiMediaWire(api_key=KEY, client=httpx.AsyncClient(transport=httpx.MockTransport(refused)))
    with pytest.raises(ProviderError) as failure:
        await wire.read_aloud("Alum fixes the red.")
    assert (failure.value.kind, failure.value.service) == ("refusal", "gemini")


@pytest.mark.parametrize(
    ("body", "kind"),
    [
        (answered("failed") | {"errors": [{"message": "blocked by policy"}]}, "refusal"),
        (answered(content=[{"type": "text", "text": "I cannot read that."}]), "refusal"),
        (answered("in_progress"), "error"),
        (answered(content=[{"type": "audio", "data": base64.b64encode(b"ID3 mp3").decode()}]), "error"),
        (answered(content=[{"type": "audio", "data": "not base64!"}]), "error"),
    ],
    ids=["stopped by policy", "no speech", "left open", "not a WAV", "not base64"],
)
def test_speech_off_its_documented_shape_fails_loudly(body: dict[str, Any], kind: str) -> None:
    with pytest.raises(ExternalFailure) as failure:
        speech_audio(body)
    assert (failure.value.kind, failure.value.service) == (kind, "gemini")
