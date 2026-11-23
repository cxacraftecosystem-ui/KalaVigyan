import base64
import json
from collections.abc import Callable
from pathlib import Path

import httpx
import pytest

from app.core.errors import ExternalFailure, InvalidInput, NotConfigured
from app.providers.elevenlabs import ElevenLabs, speech_seconds
from app.scripts.paid_check_steps import NARRATIONS

FIXTURES = Path(__file__).parent / "fixtures"
KEY = "test-only-elevenlabs-key-not-a-secret"


def recorded(name: str) -> bytes:
    return (FIXTURES / name).read_bytes()


def adapter(handler: Callable[[httpx.Request], httpx.Response]) -> tuple[ElevenLabs, list[httpx.Request]]:
    seen: list[httpx.Request] = []

    def record(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return handler(request)

    client = httpx.AsyncClient(transport=httpx.MockTransport(record))
    return ElevenLabs(api_key=KEY, client=client), seen


def replying(
    name: str, status: int = 200, headers: dict[str, str] | None = None
) -> Callable[..., httpx.Response]:
    return lambda request: httpx.Response(
        status, content=recorded(name), headers={"content-type": "application/json", **(headers or {})}
    )


async def test_the_conversation_token_carries_the_conversation_id() -> None:
    elevenlabs, seen = adapter(replying("conversation_token.json"))
    token = await elevenlabs.conversation_token("agent_test")
    assert (token.token, token.conversation_id) == (
        "fixture-conversation-token-not-a-credential",
        "conv_0123456789abcdef",
    )
    assert seen[0].method == "GET"
    assert seen[0].url.path == "/v1/convai/conversation/token"
    assert seen[0].url.params["agent_id"] == "agent_test"
    assert seen[0].headers["xi-api-key"] == KEY


async def test_a_finished_conversation_reports_whole_billed_seconds() -> None:
    elevenlabs, seen = adapter(replying("conversation_done.json"))
    record = await elevenlabs.conversation("conv_0123456789abcdef")
    assert (record.status, record.call_duration_seconds) == ("done", 212)
    assert seen[0].url.path == "/v1/convai/conversations/conv_0123456789abcdef"


async def test_a_conversation_still_processing_has_no_duration_yet() -> None:
    elevenlabs, _ = adapter(replying("conversation_processing.json"))
    record = await elevenlabs.conversation("conv_0123456789abcdef")
    assert (record.status, record.call_duration_seconds) == ("processing", None)


async def test_speech_to_text_bills_up_to_the_last_word() -> None:
    elevenlabs, seen = adapter(replying("speech_to_text.json"))
    heard = await elevenlabs.speech_to_text(
        b"RIFF-audio", content_type="audio/webm", language="en", keyterms=["Kutch Ajrakh"]
    )
    assert heard.text == "Why do Ajrakh printers use alum?"
    assert (heard.language, heard.seconds) == ("en", 3)
    body = seen[0].content.decode("latin-1")
    assert seen[0].url.path == "/v1/speech-to-text"
    assert 'name="model_id"\r\n\r\nscribe_v3' in body
    assert 'name="language_code"\r\n\r\neng\r\n' in body
    assert 'name="keyterms"\r\n\r\nKutch Ajrakh' in body
    assert "Content-Type: audio/webm" in body


async def test_speech_to_text_hears_hindi_and_urdu_by_scribe_s_own_codes() -> None:
    elevenlabs, seen = adapter(replying("speech_to_text.json"))
    await elevenlabs.speech_to_text(b"RIFF-audio", content_type="audio/webm", language="hi")
    await elevenlabs.speech_to_text(b"RIFF-audio", content_type="audio/webm", language="ur")
    assert 'name="language_code"\r\n\r\nhin\r\n' in seen[0].content.decode("latin-1")
    assert 'name="language_code"\r\n\r\nurd\r\n' in seen[1].content.decode("latin-1")


async def test_text_to_speech_returns_the_mp3_bytes() -> None:
    audio = b"\xff\xfb" * 8000
    elevenlabs, seen = adapter(lambda request: httpx.Response(200, content=audio))
    assert await elevenlabs.speech("Alum fastens colours.", voice_id="voice_1", language="en") == audio
    assert seen[0].url.path == "/v1/text-to-speech/voice_1/stream"
    assert seen[0].url.params["output_format"] == "mp3_44100_128"
    assert json.loads(seen[0].content) == {
        "text": "Alum fastens colours.",
        "model_id": "eleven_v4_turbo",
        "language_code": "en",
    }


async def test_text_to_speech_is_told_the_session_language() -> None:
    elevenlabs, seen = adapter(lambda request: httpx.Response(200, content=b"\xff\xfb"))
    await elevenlabs.speech("فٹکری رنگ پکا کرتی ہے۔", voice_id="voice_1", language="ur")
    assert json.loads(seen[0].content)["language_code"] == "ur"


async def test_a_language_the_models_were_not_checked_for_is_refused_before_any_request() -> None:
    elevenlabs, seen = adapter(lambda request: httpx.Response(200, content=b"\xff\xfb"))
    with pytest.raises(InvalidInput, match="eleven_v4_turbo"):
        await elevenlabs.speech("Hola.", voice_id="voice_1", language="es")
    with pytest.raises(InvalidInput, match="scribe_v3"):
        await elevenlabs.speech_to_text(b"RIFF-audio", content_type="audio/webm", language="es")
    assert seen == []


def test_reply_audio_seconds_are_bytes_at_128_kilobits() -> None:
    assert speech_seconds(16_000) == 1
    assert speech_seconds(16_001) == 2
    assert speech_seconds(96_000) == 6


async def test_a_refused_key_is_an_auth_failure_without_the_key_in_the_message() -> None:
    elevenlabs, _ = adapter(replying("error_unauthorized.json", 401))
    with pytest.raises(ExternalFailure) as failure:
        await elevenlabs.conversation_token("agent_test")
    assert failure.value.kind == "auth" and failure.value.service == "elevenlabs"
    assert KEY not in str(failure.value)


async def test_a_rate_limit_carries_its_wait() -> None:
    elevenlabs, _ = adapter(replying("error_unauthorized.json", 429, {"retry-after": "7"}))
    with pytest.raises(ExternalFailure) as failure:
        await elevenlabs.speech("x", voice_id="voice_1", language="en")
    assert (failure.value.kind, failure.value.retryable, failure.value.retry_after) == (
        "rate_limit",
        True,
        7.0,
    )


async def test_an_answer_off_its_documented_shape_fails_loudly() -> None:
    elevenlabs, _ = adapter(lambda request: httpx.Response(200, json={"token": "t"}))
    with pytest.raises(ExternalFailure, match="documented shape"):
        await elevenlabs.conversation_token("agent_test")


async def test_an_unreachable_service_is_unavailable() -> None:
    def broken(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused", request=request)

    elevenlabs, _ = adapter(broken)
    with pytest.raises(ExternalFailure) as failure:
        await elevenlabs.account()
    assert failure.value.kind == "unavailable"


async def test_agents_are_found_by_exact_name_across_pages() -> None:
    pages = {None: "agents_page_1.json", "cursor_2": "agents_page_2.json"}
    elevenlabs, seen = adapter(lambda request: replying(pages[request.url.params.get("cursor")])(request))
    assert await elevenlabs.agent_ids("KalaVigyan voice") == ["agent_test"]
    assert [r.url.params.get("search") for r in seen] == ["KalaVigyan voice", "KalaVigyan voice"]


async def test_client_tools_and_secrets_are_listed_by_name() -> None:
    files = {"/v1/convai/tools": "tools_list.json", "/v1/convai/secrets": "secrets_list.json"}
    elevenlabs, seen = adapter(lambda request: replying(files[request.url.path])(request))
    assert await elevenlabs.client_tool_ids() == {"show_on_map": "tool_map"}
    assert await elevenlabs.secret_ids("KALAVIGYAN_VOICE_LLM_BEARER") == ["secret_llm"]
    assert seen[0].url.params["types"] == "client"


def test_an_empty_key_is_not_configured() -> None:
    with pytest.raises(NotConfigured, match="ELEVENLABS_API_KEY"):
        ElevenLabs(api_key=" ", client=httpx.AsyncClient())


NARRATED = NARRATIONS["en"]


async def test_narration_asks_for_character_timings_from_the_narration_model() -> None:
    elevenlabs, seen = adapter(replying("narration_with_timestamps.json"))
    speech = await elevenlabs.narration(
        NARRATED, voice_id="voice_1", language="en", previous_text="Before.", next_text="After."
    )
    assert seen[0].method == "POST" and seen[0].url.path == "/v1/text-to-speech/voice_1/with-timestamps"
    assert seen[0].url.params["output_format"] == "mp3_44100_128"
    assert json.loads(seen[0].content) == {
        "text": NARRATED,
        "model_id": "eleven_v4",
        "language_code": "en",
        "previous_text": "Before.",
        "next_text": "After.",
    }
    kept = json.loads(recorded("narration_with_timestamps.json"))["audio_base64"]
    assert speech.audio == base64.b64decode(kept)
    assert (len(speech.starts), speech.starts[5], speech.ends[11], speech.ends[-1]) == (
        101,
        0.427,
        0.96,
        6.88,
    )


async def test_narration_without_neighbours_sends_no_context() -> None:
    elevenlabs, seen = adapter(replying("narration_with_timestamps.json"))
    await elevenlabs.narration(NARRATED, voice_id="voice_1", language="en")
    assert set(json.loads(seen[0].content)) == {"text", "model_id", "language_code"}


async def test_a_mark_of_several_code_points_times_each_of_them() -> None:
    alignment = {
        "characters": ["रं", "ग"],
        "character_start_times_seconds": [0.0, 0.2],
        "character_end_times_seconds": [0.2, 0.35],
    }
    body = {"audio_base64": "//s=", "alignment": alignment}
    elevenlabs, _ = adapter(lambda request: httpx.Response(200, json=body))
    speech = await elevenlabs.narration("रंग", voice_id="voice_1", language="hi")
    assert (speech.starts, speech.ends) == ((0.0, 0.0, 0.2), (0.2, 0.2, 0.35))


@pytest.mark.parametrize(
    "alignment",
    [
        {
            "characters": list("Alum"),
            "character_start_times_seconds": [0, 1, 2, 3],
            "character_end_times_seconds": [1, 2, 3, 4],
        },
        {
            "characters": list("Alum!"),
            "character_start_times_seconds": [0, 1],
            "character_end_times_seconds": [1, 2],
        },
        {
            "characters": list("Alum!"),
            "character_start_times_seconds": [0, 1, 2, 3, 4],
            "character_end_times_seconds": [1, 2, 1, 4, 5],
        },
        None,
    ],
    ids=["other text", "short timings", "ends before it starts", "no alignment"],
)
async def test_timings_off_the_documented_shape_fail_loudly(alignment: dict | None) -> None:
    body = {"audio_base64": "//s=", "alignment": alignment}
    elevenlabs, _ = adapter(lambda request: httpx.Response(200, json=body))
    with pytest.raises(ExternalFailure, match="documented shape"):
        await elevenlabs.narration("Alum!", voice_id="voice_1", language="en")


async def test_narration_audio_that_is_not_base64_fails_loudly() -> None:
    alignment = {
        "characters": ["A"],
        "character_start_times_seconds": [0],
        "character_end_times_seconds": [1],
    }
    elevenlabs, _ = adapter(
        lambda request: httpx.Response(200, json={"audio_base64": "%%%", "alignment": alignment})
    )
    with pytest.raises(ExternalFailure, match="documented shape"):
        await elevenlabs.narration("A", voice_id="voice_1", language="en")


async def test_narration_past_the_model_s_limit_or_in_an_unchecked_language_is_refused_before_any_request() -> (
    None
):
    elevenlabs, seen = adapter(replying("narration_with_timestamps.json"))
    with pytest.raises(InvalidInput, match="10000"):
        await elevenlabs.narration("a" * 10_001, voice_id="voice_1", language="en")
    with pytest.raises(InvalidInput, match="eleven_v4"):
        await elevenlabs.narration("Hola.", voice_id="voice_1", language="es")
    assert seen == []
