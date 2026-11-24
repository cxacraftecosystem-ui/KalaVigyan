import asyncio
import json
import uuid
from collections.abc import Callable
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx
import pytest

from app.core.shielded import ShieldedWork
from app.providers.budget import day_start
from app.providers.elevenlabs import ElevenLabs
from app.voice.relay import NOT_HEARD, SPEECH_GRACE, RelayAudio, RelayDeps, relay_turn_events, turn_speech
from app.voice.reply_audio import ReplyAudio
from app.voice.sessions import VoiceRefused
from app.voice.transcript import stored_transcript

from ..contracts.golden import golden_text
from .fakes import (
    ALUM,
    ANSWER_ID,
    SESSION_ID,
    START,
    TURN_ID,
    FakeModel,
    MemoryStore,
    cipher,
    ids,
    session,
    tools,
    translation,
    translation_reply,
)
from .listen_fakes import MemoryObjects

FIXTURES = Path(__file__).parent / "fixtures"
REPLY_AUDIO = b"\xff\xfb" * 48_000
NOW = START + timedelta(seconds=30)
SILENCE = {"text": "", "words": []}


def elevenlabs(stt: Callable[[httpx.Request], httpx.Response] | None = None) -> tuple[ElevenLabs, list[str]]:
    paths: list[str] = []

    def answer(request: httpx.Request) -> httpx.Response:
        paths.append(request.url.path)
        if request.url.path == "/v1/speech-to-text":
            if stt is not None:
                return stt(request)
            return httpx.Response(200, content=(FIXTURES / "speech_to_text.json").read_bytes())
        return httpx.Response(200, content=REPLY_AUDIO)

    client = httpx.AsyncClient(transport=httpx.MockTransport(answer))
    return ElevenLabs(api_key="test-only-elevenlabs-key", client=client), paths


def deps(store: MemoryStore, voice: ElevenLabs, *, values: list[uuid.UUID] | None = None) -> RelayDeps:
    return RelayDeps(
        store=store,
        tools=tools(),
        elevenlabs=voice,
        cipher=cipher(),
        speech=ReplyAudio(MemoryObjects()),
        voice_id="voice_1",
        clock=lambda: NOW,
        ids=ids(*(values or [TURN_ID, ANSWER_ID])),
    )


def answering(heard: dict[str, object]) -> Callable[[httpx.Request], httpx.Response]:
    return lambda request: httpx.Response(200, json=heard)


def live_store(used_before: int = 60, **changes: object) -> MemoryStore:
    store = MemoryStore(used_before=used_before)
    store.sessions[SESSION_ID] = session(**changes)
    return store


async def turn_text(
    store: MemoryStore, relay: RelayDeps, content: bytes = b"recorded", *, seconds: int = 1
) -> str:
    audio = RelayAudio(content, "audio/webm", least_seconds=seconds)
    return "".join([frame async for frame in relay_turn_events(store.sessions[SESSION_ID], audio, relay)])


def events(text: str) -> list[tuple[str, dict[str, object]]]:
    found = []
    for block in text.split("\n\n")[:-1]:
        name, data = block.split("\n")
        found.append((name.removeprefix("event: "), json.loads(data.removeprefix("data: "))))
    return found


@pytest.mark.usefixtures("allowances_an_owner_might_set")
async def test_a_relay_turn_streams_the_golden_turn() -> None:
    store = live_store()
    voice, paths = elevenlabs()
    assert await turn_text(store, deps(store, voice)) == golden_text("voice.turn.golden.sse")
    assert paths == ["/v1/speech-to-text", "/v1/text-to-speech/voice_1/stream"]


async def test_a_relay_turn_holds_a_minute_then_keeps_heard_and_spoken_seconds_and_the_audio() -> None:
    store = live_store()
    relay = deps(store, elevenlabs()[0])
    await turn_text(store, relay)
    assert store.ledger[f"voice:{SESSION_ID}:{TURN_ID}"].units == 60
    assert store.ledger[f"voice-refund:{SESSION_ID}:{TURN_ID}"].units == -(60 - 3)
    assert store.ledger[f"voice:{SESSION_ID}:{TURN_ID}:speech"].units == 6
    record = store.sessions[SESSION_ID]
    assert record.reserved_seconds == 9 and record.turn_count == 1
    assert await relay.speech.get(SESSION_ID, TURN_ID) == REPLY_AUDIO
    [turn] = stored_transcript(cipher(), record.transcript).turns
    assert turn["turnId"] == str(TURN_ID)


async def test_a_cached_reply_plays_free_and_a_new_synthesis_is_billed_under_its_own_key() -> None:
    store = live_store()
    voice, paths = elevenlabs()
    relay = deps(store, voice)
    await turn_text(store, relay)
    assert await turn_speech(store.sessions[SESSION_ID], TURN_ID, relay) == REPLY_AUDIO
    assert store.sessions[SESSION_ID].reserved_seconds == 9 and len(paths) == 2
    replay = uuid.UUID("0f1e2d3c-4b5a-4968-8776-655443322110")
    fresh = deps(store, voice, values=[replay])
    assert await turn_speech(store.sessions[SESSION_ID], TURN_ID, fresh) == REPLY_AUDIO
    assert paths[-1] == "/v1/text-to-speech/voice_1/stream"
    assert store.ledger[f"voice:{SESSION_ID}:{TURN_ID}:speech:{replay.hex}"].units == 6
    assert store.sessions[SESSION_ID].reserved_seconds == 9 + 6
    with pytest.raises(VoiceRefused):
        await turn_speech(store.sessions[SESSION_ID], ANSWER_ID, deps(store, voice))


async def test_a_reply_kept_in_the_bucket_plays_from_another_process_without_speech() -> None:
    store = live_store()
    voice, paths = elevenlabs()
    bucket = MemoryObjects()
    await turn_text(store, replace(deps(store, voice), speech=ReplyAudio(bucket)))
    other = replace(deps(store, voice, values=[uuid.uuid4()]), speech=ReplyAudio(bucket))
    assert await turn_speech(store.sessions[SESSION_ID], TURN_ID, other) == REPLY_AUDIO
    assert (len(paths), store.sessions[SESSION_ID].reserved_seconds) == (2, 9)
    assert list(bucket.stored) == [f"media/voice-replies/{SESSION_ID}/{TURN_ID}/reply.mp3"]
    assert bucket.stored[f"media/voice-replies/{SESSION_ID}/{TURN_ID}/reply.mp3"][1] == "audio/mpeg"


async def test_a_reply_is_not_synthesised_again_after_the_call_and_its_grace() -> None:
    store = live_store()
    voice, paths = elevenlabs()
    await turn_text(store, deps(store, voice))
    ended = replace(store.sessions[SESSION_ID], ended_at=NOW)
    late = replace(deps(store, voice), clock=lambda: NOW + SPEECH_GRACE)
    with pytest.raises(VoiceRefused) as gone:
        await turn_speech(ended, TURN_ID, late)
    assert gone.value.reason == "speech_gone" and len(paths) == 2
    soon = replace(deps(store, voice, values=[uuid.uuid4()]), clock=lambda: NOW + timedelta(seconds=30))
    assert await turn_speech(ended, TURN_ID, soon) == REPLY_AUDIO


@pytest.mark.usefixtures("allowances_an_owner_might_set")
async def test_a_replay_with_no_time_left_is_refused_before_any_synthesis() -> None:
    store = live_store()
    voice, paths = elevenlabs()
    await turn_text(store, deps(store, voice))
    store.used_before = 600
    with pytest.raises(VoiceRefused) as refused:
        await turn_speech(store.sessions[SESSION_ID], TURN_ID, deps(store, voice))
    assert refused.value.reason == "quota" and len(paths) == 2


async def test_by_default_a_reply_is_spoken_whatever_the_day_has_used() -> None:
    store = live_store()
    voice, paths = elevenlabs()
    await turn_text(store, deps(store, voice))
    store.used_before = 100_000
    audio = await turn_speech(store.sessions[SESSION_ID], TURN_ID, deps(store, voice))
    assert audio and len(paths) == 3


async def test_a_hindi_relay_turn_hears_and_speaks_hindi() -> None:
    hindi_question = "अजरख छापने वाले फिटकरी का उपयोग क्यों करते हैं?"
    hindi_alum = "फिटकरी का उपयोग रंगों को पक्का करने के लिए मॉर्डेंट के रूप में किया जाता है।"
    seen: list[httpx.Request] = []

    def answer(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        if request.url.path == "/v1/speech-to-text":
            heard = {
                "text": hindi_question,
                "words": [{"text": "x", "start": 0.0, "end": 2.4, "type": "word"}],
            }
            return httpx.Response(200, json=heard)
        return httpx.Response(200, content=REPLY_AUDIO)

    client = httpx.AsyncClient(transport=httpx.MockTransport(answer))
    voice = ElevenLabs(api_key="test-only-elevenlabs-key", client=client)
    store = live_store(language="hi")
    translator = FakeModel(
        [
            translation_reply(question="Why do Ajrakh printers use alum?"),
            translation_reply(**{"s1.1": hindi_alum}),
        ]
    )
    relay = replace(deps(store, voice), tools=tools(translated=translation(translator)))
    found = events(await turn_text(store, relay))
    assert 'name="language_code"\r\n\r\nhin\r\n' in seen[0].content.decode("utf-8")
    assert json.loads(seen[1].content)["language_code"] == "hi"
    assert json.loads(seen[1].content)["text"] == f"{hindi_alum} स्रोत: GI Journal 188."
    assert found[0] == ("heard", {"text": hindi_question, "language": "hi"})
    sentence = next(data["sentence"] for name, data in found if name == "sentence")
    assert (sentence["text"], sentence["original"], sentence["translated"]) == (hindi_alum, ALUM, True)
    spoken = next(data for name, data in found if name == "spoken")
    assert spoken["text"] == f"{hindi_alum} स्रोत: GI Journal 188."
    assert found[-1][1]["billedSeconds"] == 3 + 6


async def test_unheard_audio_is_one_error_then_done_and_still_costs_its_floor() -> None:
    store = live_store()
    voice, _ = elevenlabs(lambda request: httpx.Response(503))
    found = events(await turn_text(store, deps(store, voice)))
    assert found[0] == ("error", {"message": NOT_HEARD})
    assert found[1][0] == "done" and found[1][1]["billedSeconds"] == 1
    assert store.sessions[SESSION_ID].turn_count == 1


async def test_a_silent_upload_is_billed_by_its_decoded_length_and_uses_a_turn() -> None:
    store = live_store()
    voice, paths = elevenlabs(answering(SILENCE))
    found = events(await turn_text(store, deps(store, voice), b"\x00" * 50_000, seconds=10))
    assert found[0] == ("error", {"message": NOT_HEARD})
    assert found[1][1]["billedSeconds"] == 10
    record = store.sessions[SESSION_ID]
    assert record.turn_count == 1 and record.reserved_seconds == 10
    assert paths == ["/v1/speech-to-text"]


async def test_every_upload_takes_one_of_the_forty_turns() -> None:
    store = live_store(turn_count=39)
    voice, _ = elevenlabs(answering(SILENCE))
    found = events(await turn_text(store, deps(store, voice)))
    assert found[-1][1]["sessionEnded"] is True
    assert store.sessions[SESSION_ID].turn_count == 40


@pytest.mark.usefixtures("allowances_an_owner_might_set")
async def test_an_upload_bigger_than_the_time_left_is_refused_before_speech_to_text() -> None:
    store = live_store(used_before=600 - 5)
    voice, paths = elevenlabs()
    found = events(await turn_text(store, deps(store, voice), b"\x00" * 30_000, seconds=6))
    assert found[0] == ("error", {"message": "Not enough voice time is left today."})
    assert found[1][1]["billedSeconds"] == 0 and found[1][1]["sessionEnded"] is False
    assert paths == [] and store.ledger == {} and store.sessions[SESSION_ID].turn_count == 0


async def test_a_turn_heard_past_a_minute_is_refused_and_billed_its_whole_hold() -> None:
    long = {"text": "a long ramble", "words": [{"text": "ramble", "start": 0.0, "end": 61.2, "type": "word"}]}
    store = live_store()
    voice, _ = elevenlabs(answering(long))
    found = events(await turn_text(store, deps(store, voice)))
    assert found[0] == ("error", {"message": "Keep each turn under a minute."})
    assert found[1][1]["billedSeconds"] == 60


@pytest.mark.usefixtures("allowances_an_owner_might_set")
async def test_the_last_seconds_end_the_call() -> None:
    store = live_store(used_before=600 - 5)
    found = events(await turn_text(store, deps(store, elevenlabs()[0])))
    done = found[-1][1]
    assert done["remainingSeconds"] == 0 and done["sessionEnded"] is True and done["billedSeconds"] == 5
    assert store.sessions[SESSION_ID].ended_at is not None


async def test_an_ended_call_takes_no_more_turns() -> None:
    store = live_store(turn_count=40)
    found = events(await turn_text(store, deps(store, elevenlabs()[0])))
    assert found[0] == ("error", {"message": "This call has ended."})
    assert found[-1][1]["sessionEnded"] is True


async def test_a_caller_who_leaves_during_speech_to_text_still_gets_the_unheard_part_back() -> None:
    store = live_store()
    asked, gate = asyncio.Event(), asyncio.Event()

    async def answer(request: httpx.Request) -> httpx.Response:
        asked.set()
        await gate.wait()
        return httpx.Response(200, json=SILENCE)

    voice = ElevenLabs(
        api_key="test-only-elevenlabs-key", client=httpx.AsyncClient(transport=httpx.MockTransport(answer))
    )
    relay = replace(deps(store, voice), shield=ShieldedWork())
    consumer = asyncio.create_task(turn_text(store, relay, b"\x00" * 25_000, seconds=5))
    await asyncio.wait_for(asked.wait(), timeout=5)
    consumer.cancel()
    with pytest.raises(asyncio.CancelledError):
        await consumer
    gate.set()
    assert await relay.shield.drain() == 0
    assert store.ledger[f"voice-refund:{SESSION_ID}:{TURN_ID}"].units == -(60 - 5)
    assert store.sessions[SESSION_ID].reserved_seconds == 5


async def test_the_unheard_part_of_a_turn_is_refunded_to_the_day_its_hold_was_taken() -> None:
    claimed = datetime(2026, 11, 16, 18, 29, 30, tzinfo=UTC)
    later = claimed + timedelta(minutes=2)
    assert day_start(later) - day_start(claimed) == timedelta(days=1)
    store = live_store(
        started_at=claimed - timedelta(seconds=20), expires_at=claimed + timedelta(seconds=100)
    )
    moments = iter([claimed])
    relay = replace(deps(store, elevenlabs()[0]), clock=lambda: next(moments, later))
    await turn_text(store, relay)
    hold = store.ledger[f"voice:{SESSION_ID}:{TURN_ID}"]
    refund = store.ledger[f"voice-refund:{SESSION_ID}:{TURN_ID}"]
    assert (hold.counted_at, refund.counted_at, refund.units) == (claimed, claimed, -(60 - 3))
