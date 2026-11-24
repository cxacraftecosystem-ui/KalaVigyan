import asyncio
import json
import uuid
from dataclasses import dataclass, field, replace
from datetime import datetime, timedelta
from typing import Any

import httpx
import pytest

from app.core.shielded import ShieldedWork
from app.providers.elevenlabs import ElevenLabs
from app.schemas.artisan import parse_artisan_event
from app.voice.artisan_records import ConversationRecord
from app.voice.artisan_relay import ArtisanUpload, RelayTurnDeps, artisan_turn_events, conversation_speech
from app.voice.artisan_reply import ArtisanTools
from app.voice.artisan_session import ArtisanRefused, ConversationDeps
from app.voice.artisan_transcript import open_transcript
from app.voice.relay import SPEECH_GRACE
from app.voice.reply_audio import ReplyAudio

from .artisan_fakes import CONVERSATION_ID, MemoryArtisanStore, conversation, kalavigyan_turn as asked, sealed
from .fakes import (
    SESSION_ID,
    START,
    USER_ID,
    FakeModel,
    MemoryStore,
    cipher,
    compose_reply,
    ids,
    session,
    tools,
)
from .listen_fakes import MemoryObjects
from .test_artisan_session import runtime, voice

SPEECH = b"\xff\xfb" * 24_000
HEARD = "We soak the cloth in camel dung and castor oil for three days."
NEW_IDS = [uuid.UUID(int=n) for n in range(201, 240)]


def parse_sse(frame: str) -> tuple[str, Any]:
    name, data = frame.strip("\n").split("\n")
    return name.removeprefix("event: "), json.loads(data.removeprefix("data: "))


def heard_json(text: str = HEARD) -> dict[str, Any]:
    words, at = [], 0.2
    for word in text.split():
        words.append({"text": word, "start": at, "end": at + 0.3, "type": "word"})
        at += 0.4
    return {"language_code": "en", "text": text, "words": words}


def elevenlabs(heard: dict[str, Any]) -> ElevenLabs:
    def answer(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/v1/speech-to-text":
            return httpx.Response(200, json=heard)
        return httpx.Response(200, content=SPEECH)

    return ElevenLabs(
        api_key="test-only-elevenlabs-key", client=httpx.AsyncClient(transport=httpx.MockTransport(answer))
    )


@dataclass
class Bucket:
    objects: dict[str, bytes] = field(default_factory=dict)

    async def put(self, key: str, body: bytes, *, content_type: str) -> None:
        self.objects[key] = body

    async def delete(self, key: str) -> None:
        self.objects.pop(key, None)


@dataclass
class GatedBucket(Bucket):
    entered: asyncio.Event = field(default_factory=asyncio.Event)
    gate: asyncio.Event = field(default_factory=asyncio.Event)

    async def put(self, key: str, body: bytes, *, content_type: str) -> None:
        self.entered.set()
        await self.gate.wait()
        await super().put(key, body, content_type=content_type)


def interview(**fields: Any) -> str:
    body = {
        "asked": False,
        "topic": "PROCESS",
        "question": "Why do you soak the cloth first?",
        "close": False,
    }
    return json.dumps(body | fields)


@dataclass
class Setup:
    store: MemoryStore
    artisans: MemoryArtisanStore
    bucket: Bucket
    ended: list[ConversationRecord]
    model: FakeModel
    deps: RelayTurnDeps


def setup(
    *replies: str, heard: dict[str, Any] | None = None, now: datetime | None = None, **session_changes: Any
) -> Setup:
    store = MemoryStore()
    store.sessions[SESSION_ID] = session(
        role="ARTISAN", mode="VERIFIED", purpose="ARTISAN", **session_changes
    )
    artisans = MemoryArtisanStore(voice=store)
    opening = asked(0, "Namaste. Please walk me through how you make your work?")
    artisans.conversations[CONVERSATION_ID] = conversation(
        voice_session_id=SESSION_ID, transcript=sealed(opening), topics_asked=("PROCESS",)
    )
    model = FakeModel(list(replies or (interview(),)))
    base = ConversationDeps(
        store=store,
        artisans=artisans,
        runtime=runtime(),
        voice=voice(),
        cipher=cipher(),
        speech=ReplyAudio(MemoryObjects()),
        clock=lambda: now or START + timedelta(seconds=40),
        ids=ids(*NEW_IDS),
    )
    ended: list[ConversationRecord] = []
    bucket = Bucket()
    turn_deps = RelayTurnDeps(
        conversation=base,
        tools=ArtisanTools(interview=model, turns=tools(model=FakeModel([compose_reply("x", "x")]))),
        elevenlabs=elevenlabs(heard or heard_json()),
        bucket=bucket,
        on_end=ended.append,
    )
    return Setup(store, artisans, bucket, ended, model, turn_deps)


async def events(chosen: Setup, *, continued: bool = False) -> list[tuple[str, Any]]:
    record = chosen.artisans.conversations[CONVERSATION_ID]
    upload = ArtisanUpload(
        content=b"recorded", content_type="audio/webm", least_seconds=1, continued=continued
    )
    frames = [frame async for frame in artisan_turn_events(record, upload, chosen.deps)]
    parsed = [parse_sse(frame) for frame in frames]
    return [(name, parse_artisan_event(name, data)) for name, data in parsed]


async def test_a_turn_is_heard_kept_with_its_recording_and_answered_with_one_question() -> None:
    chosen = setup()
    seen = await events(chosen)
    assert [name for name, _ in seen] == ["status", "heard", "status", "status", "reply", "done"]
    reply = seen[4][1]
    assert reply.question == "Why do you soak the cloth first?" and reply.topic == "PROCESS"
    assert reply.text == reply.question and reply.answer_id is None
    assert not seen[-1][1].session_ended
    turns = open_transcript(cipher(), chosen.artisans.conversations[CONVERSATION_ID].transcript).turns
    assert [(t.ordinal, t.speaker) for t in turns] == [(0, "KALAVIGYAN"), (1, "ARTISAN"), (2, "KALAVIGYAN")]
    artisan = turns[1]
    assert artisan.text == HEARD and artisan.words and artisan.audio_id is not None and not artisan.scrubbed
    [key] = chosen.bucket.objects
    assert key.startswith(f"media/{USER_ID}/") and "_Artisan-Conversation_" in key and key.endswith(".webm")
    assert [a.object_key for a in chosen.artisans.audio] == [key]
    assert '<untrusted_source ref="t1" label="the artisan">' in chosen.model.calls[0]["user"]


async def test_a_continued_part_is_kept_and_not_answered() -> None:
    chosen = setup()
    seen = await events(chosen, continued=True)
    assert [name for name, _ in seen] == ["status", "heard", "done"]
    assert seen[1][1].continued
    assert chosen.model.calls == []


async def test_a_turn_that_lost_a_number_to_scrubbing_keeps_no_recording_and_no_word_times() -> None:
    chosen = setup(heard=heard_json("Call me on 98765 43210 about the dyes."))
    seen = await events(chosen)
    heard = seen[1][1]
    assert "98765" not in heard.text and "[number]" in heard.text
    turn = open_transcript(cipher(), chosen.artisans.conversations[CONVERSATION_ID].transcript).turns[1]
    assert turn.scrubbed and turn.words is None and turn.audio_id is None
    assert chosen.bucket.objects == {} and chosen.artisans.audio == []


async def test_the_artisan_s_question_is_answered_from_stored_claims_then_the_interview_goes_on() -> None:
    chosen = setup(interview(asked=True), heard=heard_json("Why do Ajrakh printers use alum?"))
    seen = await events(chosen)
    reply = next(event for name, event in seen if name == "reply")
    assert reply.answer_id is not None and reply.sentences
    assert reply.text.startswith(reply.sentences[0].text) and reply.text.endswith(reply.question)
    assert [name for name, _ in seen].count("source") == 1
    assert chosen.artisans.answers and chosen.artisans.answers[0].id == reply.answer_id


async def test_near_the_end_the_closing_is_spoken_and_the_conversation_ends() -> None:
    chosen = setup(now=START + timedelta(seconds=120 + 540 - 30))
    seen = await events(chosen)
    names = [name for name, _ in seen]
    assert "closing" in names and "reply" not in names
    assert seen[-1][1].session_ended
    assert chosen.model.calls == []
    [ended] = chosen.ended
    assert ended.extraction == "PENDING"


async def test_an_ended_conversation_refuses_the_upload() -> None:
    chosen = setup(ended_at=START + timedelta(seconds=10))
    seen = await events(chosen)
    assert [name for name, _ in seen] == ["error", "done"]


async def test_a_reply_is_replayed_from_the_transcript_and_gone_after_the_grace() -> None:
    chosen = setup()
    await events(chosen)
    record = chosen.artisans.conversations[CONVERSATION_ID]
    turn_id = open_transcript(cipher(), record.transcript).turns[2].id
    base = chosen.deps.conversation
    fresh = replace(base, speech=ReplyAudio(MemoryObjects()))
    assert await conversation_speech(record, chosen.store.sessions[SESSION_ID], turn_id, fresh) == SPEECH
    ended = replace(chosen.store.sessions[SESSION_ID], ended_at=START)
    late = replace(fresh, clock=lambda: START + SPEECH_GRACE + timedelta(seconds=1))
    with pytest.raises(ArtisanRefused) as refused:
        await conversation_speech(record, ended, turn_id, late)
    assert refused.value.reason == "speech_gone"


async def test_a_recording_whose_turn_cannot_be_saved_is_deleted_again(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    chosen = setup()

    async def gone(conversation_id: uuid.UUID, write: Any) -> None:
        raise LookupError(f"Artisan conversation {conversation_id} is gone")

    monkeypatch.setattr(chosen.artisans, "save_turn", gone)
    seen = await events(chosen)
    assert [name for name, _ in seen] == ["status", "error", "done"]
    assert chosen.bucket.objects == {} and chosen.artisans.audio == []


async def test_a_caller_who_leaves_while_the_recording_is_stored_still_gets_its_row() -> None:
    chosen = setup()
    bucket = GatedBucket()
    left = replace(chosen, bucket=bucket, deps=replace(chosen.deps, bucket=bucket, shield=ShieldedWork()))
    consumer = asyncio.create_task(events(left, continued=True))
    await asyncio.wait_for(bucket.entered.wait(), timeout=5)
    consumer.cancel()
    with pytest.raises(asyncio.CancelledError):
        await consumer
    bucket.gate.set()
    assert await left.deps.shield.drain() == 0
    [key] = bucket.objects
    assert [audio.object_key for audio in left.artisans.audio] == [key]
    turns = open_transcript(cipher(), left.artisans.conversations[CONVERSATION_ID].transcript).turns
    assert [(turn.speaker, turn.audio_id is not None) for turn in turns[1:]] == [("ARTISAN", True)]


async def test_the_unheard_part_of_an_artisan_turn_is_refunded_to_the_time_of_its_claim() -> None:
    chosen = setup()
    claimed, later = START + timedelta(seconds=40), START + timedelta(seconds=95)
    moments = iter([claimed])
    base = replace(chosen.deps.conversation, clock=lambda: next(moments, later))
    await events(replace(chosen, deps=replace(chosen.deps, conversation=base)), continued=True)
    rows = chosen.store.ledger
    [refund] = [row for key, row in rows.items() if key.startswith("voice-refund:")]
    hold = rows[refund.key.replace("voice-refund:", "voice:")]
    assert (hold.units, hold.counted_at, refund.counted_at) == (60, claimed, claimed)
