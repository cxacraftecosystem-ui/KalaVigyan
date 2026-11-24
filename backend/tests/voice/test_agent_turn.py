import asyncio
import json
import logging
from dataclasses import dataclass, field, replace
from datetime import timedelta
from typing import Any

import pytest

from app.research.structured import StructuredReply
from app.schemas.voice_llm import LlmChatRequest
from app.voice import llm
from app.voice.agent_turn import REFUSAL_CHECKS, AgentCall, agent_reply, authorised_session, last_question
from app.voice.llm import reply_stream
from app.voice.runtime import VoiceSettings
from app.voice.sessions import VoiceRefused
from app.voice.transcript import stored_transcript

from ..contracts.golden import golden_json
from .fakes import (
    ALUM,
    ANSWER_ID,
    BEARER,
    CLAIM_ID,
    CONVERSATION_ID,
    HMAC_KEY,
    QUESTION,
    SESSION_ID,
    START,
    TURN_ID,
    MemoryStore,
    agent_session,
    alum_pack,
    cipher,
    ids,
    tools,
    translation,
    translation_reply,
)

NOW = START + timedelta(seconds=40)


def settings() -> VoiceSettings:
    return VoiceSettings(
        transport="AGENT",
        max_live_sessions=5,
        voice_id="voice_1",
        api_key="test-only-elevenlabs-key",
        agent_id="agent_test",
        llm_bearer=BEARER,
        hmac_key=HMAC_KEY,
        cipher=cipher(),
    )


def store_with(**changes: object) -> MemoryStore:
    store = MemoryStore()
    record = agent_session(**changes)
    store.sessions[record.id] = record
    return store


def call(conversation_id: str | None = CONVERSATION_ID, bearer: str | None = BEARER) -> AgentCall:
    return AgentCall(
        authorization=None if bearer is None else f"Bearer {bearer}", conversation_id=conversation_id
    )


async def test_the_bound_conversation_reaches_its_session() -> None:
    record = await authorised_session(store_with(), settings(), call(), now=NOW)
    assert record.id == SESSION_ID


@pytest.mark.parametrize(
    ("case", "check"),
    [
        ("forged conversation id", "session record"),
        ("forged nonce", "binding"),
        ("reused nonce", "binding"),
        ("ended", "session record"),
        ("missing bearer", "bearer"),
        ("wrong bearer", "bearer"),
        ("expired", "session record"),
        ("no conversation header", "conversation header"),
    ],
)
async def test_every_unbound_request_is_refused_alike_and_the_log_names_the_check(
    case: str, check: str, caplog: pytest.LogCaptureFixture
) -> None:
    store = store_with()
    record = store.sessions[SESSION_ID]
    request, now = call(), NOW
    if case == "forged conversation id":
        request = call("conv_forged")
    elif case == "forged nonce":
        store.sessions[SESSION_ID] = replace(record, nonce_hash="f" * 64)
    elif case == "reused nonce":
        store.sessions[SESSION_ID] = replace(record, conversation_id="conv_second")
        request = call("conv_second")
    elif case == "ended":
        await store.end(SESSION_ID, NOW)
    elif case == "missing bearer":
        request = call(bearer=None)
    elif case == "wrong bearer":
        request = call(bearer=BEARER + "x")
    elif case == "no conversation header":
        request = call(None)
    else:
        now = record.hard_end
    with (
        caplog.at_level(logging.WARNING, logger="app.voice.agent_turn"),
        pytest.raises(VoiceRefused) as refused,
    ):
        await authorised_session(store, settings(), request, now=now, sleep=Sleeps())
    assert (refused.value.reason, refused.value.message) == ("unauthorized", "unauthorized")
    (logged,) = caplog.records
    assert logged.getMessage().startswith(f"a voice agent turn was refused at the {check} check: ")
    assert check in REFUSAL_CHECKS and BEARER not in logged.getMessage()
    assert not request.conversation_id or request.conversation_id not in logged.getMessage()


@dataclass
class Sleeps:
    taken: list[float] = field(default_factory=list)

    async def __call__(self, seconds: float) -> None:
        self.taken.append(seconds)


@dataclass
class LateBinding(MemoryStore):
    bound_after: int | None = None
    reads: int = 0

    async def by_conversation(self, conversation_id: str) -> Any:
        self.reads += 1
        if self.bound_after is None or self.reads <= self.bound_after:
            return None
        return await super().by_conversation(conversation_id)


def late_store(bound_after: int | None) -> LateBinding:
    store = LateBinding(bound_after=bound_after)
    store.sessions[SESSION_ID] = agent_session()
    return store


async def test_a_call_that_races_the_bind_finds_its_session_within_the_wait() -> None:
    store, sleeps = late_store(bound_after=1), Sleeps()
    record = await authorised_session(store, settings(), call(), now=NOW, sleep=sleeps)
    assert record.id == SESSION_ID
    assert (store.reads, sleeps.taken) == (2, [0.5])


async def test_a_conversation_never_bound_is_refused_after_two_seconds_and_logs_its_shape(
    caplog: pytest.LogCaptureFixture,
) -> None:
    store, sleeps = late_store(bound_after=None), Sleeps()
    with (
        caplog.at_level(logging.WARNING, logger="app.voice.agent_turn"),
        pytest.raises(VoiceRefused),
    ):
        await authorised_session(store, settings(), call(), now=NOW, sleep=sleeps)
    assert (store.reads, sleeps.taken, sum(sleeps.taken)) == (5, [0.5] * 4, 2.0)
    (logged,) = caplog.records
    assert logged.getMessage() == (
        "a voice agent turn was refused at the session record check: no session held this conversation "
        "within 2 s (21 characters, starts with conv_)"
    )
    assert CONVERSATION_ID not in logged.getMessage() and len(CONVERSATION_ID) == 21


async def test_an_unsubstituted_header_is_refused_at_once_and_logs_its_shape(
    caplog: pytest.LogCaptureFixture,
) -> None:
    store, sleeps = late_store(bound_after=0), Sleeps()
    template = "{{system__conversation_id}}"
    with (
        caplog.at_level(logging.WARNING, logger="app.voice.agent_turn"),
        pytest.raises(VoiceRefused),
    ):
        await authorised_session(store, settings(), call(template), now=NOW, sleep=sleeps)
    assert (store.reads, sleeps.taken) == (1, [])
    (logged,) = caplog.records
    assert logged.getMessage() == (
        "a voice agent turn was refused at the session record check: no session holds this conversation "
        "(27 characters, does not start with conv_)"
    )


def test_the_question_is_the_last_user_message_scrubbed() -> None:
    body = golden_json("voice.llm-request.golden.json")
    body["messages"].append({"role": "assistant", "content": "Earlier reply."})
    body["messages"].append({"role": "user", "content": "Mail me at asha@example.com about alum"})
    assert last_question(LlmChatRequest.model_validate(body)) == "Mail me at [email] about alum"


async def test_a_turn_rides_the_call_s_hold_and_keeps_an_encrypted_transcript() -> None:
    store = store_with(reserved_seconds=540)
    reply = await agent_reply(
        store.sessions[SESSION_ID],
        QUESTION,
        store=store,
        tools=tools(),
        cipher=cipher(),
        clock=lambda: NOW,
        ids=ids(TURN_ID, ANSWER_ID),
    )
    assert reply.parts == (ALUM, " Source: GI Journal 188.") and reply.end_call is None
    record = store.sessions[SESSION_ID]
    assert record.turn_count == 1 and record.reserved_seconds == 540 and store.ledger == {}
    assert "alum" not in (record.transcript or "")
    [turn] = stored_transcript(cipher(), record.transcript).turns
    assert (turn["heard"], turn["answerId"], turn["ordinal"]) == (QUESTION, str(ANSWER_ID), 1)
    [answer] = store.answers
    assert answer.id == ANSWER_ID and answer.claim_ids


async def test_a_call_shortened_by_the_day_s_time_ends_with_the_quota_message() -> None:
    store = store_with(max_duration_seconds=30, reserved_seconds=30)
    reply = await agent_reply(
        store.sessions[SESSION_ID], QUESTION, store=store, tools=tools(), cipher=cipher(), clock=lambda: NOW
    )
    assert reply.end_call is not None and reply.end_call.reason == "quota"
    assert reply.end_call.message == "That is all the voice time for today."
    record = store.sessions[SESSION_ID]
    assert record.ended_at == NOW and record.nonce_hash is None and record.turn_count == 0
    assert store.ledger == {}


async def test_a_full_length_call_ends_at_ten_minutes() -> None:
    store = store_with(max_duration_seconds=600, reserved_seconds=600)
    at_end = START + timedelta(seconds=600)
    reply = await agent_reply(
        store.sessions[SESSION_ID],
        QUESTION,
        store=store,
        tools=tools(),
        cipher=cipher(),
        clock=lambda: at_end,
    )
    assert reply.end_call is not None and reply.end_call.reason == "turns"


async def test_the_fortieth_turn_is_the_last() -> None:
    store = store_with(turn_count=40)
    reply = await agent_reply(
        store.sessions[SESSION_ID], QUESTION, store=store, tools=tools(), cipher=cipher(), clock=lambda: NOW
    )
    assert reply.end_call is not None and reply.end_call.reason == "turns"


async def test_an_empty_user_turn_says_nothing_and_counts_nothing() -> None:
    store = store_with()
    reply = await agent_reply(
        store.sessions[SESSION_ID], "", store=store, tools=tools(), cipher=cipher(), clock=lambda: NOW
    )
    assert reply.parts == () and reply.end_call is None
    assert store.sessions[SESSION_ID].turn_count == 0 and store.ledger == {}


@dataclass
class GatedTranslator:
    replies: list[str]
    gate: asyncio.Event = field(default_factory=asyncio.Event)
    calls: list[str] = field(default_factory=list)

    async def __call__(self, *, system: str, user: str, schema: Any) -> StructuredReply:
        self.calls.append(user)
        if "Target language: Hindi" in user:
            await self.gate.wait()
        return StructuredReply(text=self.replies[len(self.calls) - 1], degraded=False)


async def test_the_filler_fires_in_hindi_while_the_reply_is_being_translated(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(llm, "FILLER_AFTER_SECONDS", 0.01)
    hindi_alum = "फिटकरी का उपयोग रंगों को पक्का करने के लिए मॉर्डेंट के रूप में किया जाता है।"
    store = store_with(language="hi", mode="VERIFIED")
    translator = GatedTranslator(
        [
            translation_reply(question="Why do Ajrakh printers use alum?"),
            translation_reply(**{str(CLAIM_ID): hindi_alum}),
        ]
    )
    turn_tools = tools(alum_pack(mode="VERIFIED"), translated=translation(translator))
    reply = agent_reply(
        store.sessions[SESSION_ID],
        "अजरख छापने वाले फिटकरी का उपयोग क्यों करते हैं?",
        store=store,
        tools=turn_tools,
        cipher=cipher(),
        clock=lambda: NOW,
    )
    stream = reply_stream(reply, turn_id=TURN_ID, created=1794825000, language="hi")
    filler = json.loads((await anext(stream)).removeprefix("data: "))
    assert filler["choices"][0]["delta"]["content"] == "एक पल, स्रोत देखते हैं... "
    assert len(translator.calls) == 2 and "Target language: Hindi" in translator.calls[1]
    translator.gate.set()
    rest = [frame async for frame in stream]
    said = json.loads(rest[0].removeprefix("data: "))["choices"][0]["delta"]["content"]
    assert said == hindi_alum
    assert rest[-1] == "data: [DONE]\n\n"
    [answer] = store.answers
    assert answer.sentences[0]["text"] == hindi_alum and answer.latency_ms >= 0


async def test_master_admins_are_never_out_of_seconds() -> None:
    store = store_with(role="MASTER_ADMIN")
    store.used_before = 1_000_000
    reply = await agent_reply(
        store.sessions[SESSION_ID], QUESTION, store=store, tools=tools(), cipher=cipher(), clock=lambda: NOW
    )
    assert reply.end_call is None and reply.parts
