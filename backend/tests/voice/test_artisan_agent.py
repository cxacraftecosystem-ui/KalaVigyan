import json
import uuid
from dataclasses import replace
from datetime import timedelta
from typing import Any

import pytest

from app.schemas.voice_llm import LlmChatRequest
from app.voice.agent_turn import AgentCall
from app.voice.artisan_agent import artisan_agent_reply, authorised_artisan_session, heard_message
from app.voice.artisan_reply import ArtisanTools
from app.voice.artisan_session import ArtisanRefused, ConversationDeps
from app.voice.artisan_transcript import open_transcript
from app.voice.binding import ARTISAN_NONCE_CONTEXT, nonce_hash, session_nonce
from app.voice.reply_audio import ReplyAudio

from .artisan_fakes import CONVERSATION_ID, MemoryArtisanStore, conversation, kalavigyan_turn as asked, sealed
from .fakes import (
    BEARER,
    CONVERSATION_ID as EL_CONVERSATION,
    HMAC_KEY,
    SESSION_ID,
    START,
    FakeModel,
    MemoryStore,
    cipher,
    ids,
    session,
    tools,
)
from .listen_fakes import MemoryObjects
from .test_artisan_session import runtime, voice

NOW = START + timedelta(seconds=150)


def bound(context: str = ARTISAN_NONCE_CONTEXT, **changes: Any) -> Any:
    record = session(
        transport="AGENT",
        conversation_id=EL_CONVERSATION,
        purpose="ARTISAN",
        role="ARTISAN",
        mode="VERIFIED",
        **changes,
    )
    return replace(
        record, nonce_hash=nonce_hash(session_nonce(HMAC_KEY, record, EL_CONVERSATION, context=context))
    )


def deps(record: Any, ended: bool = False) -> ConversationDeps:
    store = MemoryStore()
    store.sessions[record.id] = record
    artisans = MemoryArtisanStore(voice=store)
    artisans.conversations[CONVERSATION_ID] = conversation(
        voice_session_id=record.id,
        transport="AGENT",
        transcript=sealed(asked(0, "Please walk me through how you make your work?")),
        topics_asked=("PROCESS",),
        ended_at=NOW if ended else None,
    )
    return ConversationDeps(
        store=store,
        artisans=artisans,
        runtime=runtime(),
        voice=voice("AGENT"),
        cipher=cipher(),
        speech=ReplyAudio(MemoryObjects()),
        clock=lambda: NOW,
        ids=ids(*[uuid.UUID(int=n) for n in range(301, 330)]),
    )


CALL = AgentCall(f"Bearer {BEARER}", EL_CONVERSATION)


async def test_a_bound_artisan_session_is_authorised() -> None:
    chosen = deps(bound())
    record, found = await authorised_artisan_session(chosen, CALL, now=NOW)
    assert record.id == SESSION_ID and found.id == CONVERSATION_ID


@pytest.mark.parametrize(
    "record",
    [
        bound(context="kalavigyan-voice/v1"),
        replace(bound(), purpose="ASK"),
        replace(bound(), transport="RELAY"),
    ],
)
async def test_a_voice_session_or_a_relay_one_is_refused(record: Any) -> None:
    with pytest.raises(ArtisanRefused):
        await authorised_artisan_session(deps(record), CALL, now=NOW)


async def test_a_wrong_bearer_or_an_ended_conversation_is_refused() -> None:
    with pytest.raises(ArtisanRefused):
        await authorised_artisan_session(deps(bound()), AgentCall("Bearer wrong", EL_CONVERSATION), now=NOW)
    with pytest.raises(ArtisanRefused):
        await authorised_artisan_session(deps(bound(), ended=True), CALL, now=NOW)


def test_the_heard_message_is_scrubbed_and_marked() -> None:
    chat = LlmChatRequest.model_validate(
        {
            "model": "kalavigyan",
            "stream": True,
            "messages": [{"role": "user", "content": "Ring 98765 43210 please"}],
        }
    )
    heard = heard_message(chat)
    assert "98765" not in heard.text and heard.scrubbed


async def test_an_agent_turn_keeps_both_turns_and_speaks_the_question() -> None:
    record = bound()
    chosen = deps(record)
    interview = json.dumps(
        {"asked": False, "topic": "MATERIALS", "question": "Where does your clay come from?", "close": False}
    )
    artisan_tools = ArtisanTools(interview=FakeModel([interview]), turns=tools())
    ended: list[Any] = []
    heard = heard_message(
        LlmChatRequest.model_validate(
            {"model": "m", "stream": True, "messages": [{"role": "user", "content": "I use river clay."}]}
        )
    )
    conversation_record = chosen.artisans.conversations[CONVERSATION_ID]
    reply = await artisan_agent_reply(
        record, conversation_record, heard, deps=chosen, tools=artisan_tools, on_end=ended.append
    )
    assert reply.parts == ("Where does your clay come from?",) and reply.end_call is None
    turns = open_transcript(cipher(), chosen.artisans.conversations[CONVERSATION_ID].transcript).turns
    assert [(t.speaker, t.topic) for t in turns] == [
        ("KALAVIGYAN", "PROCESS"),
        ("ARTISAN", None),
        ("KALAVIGYAN", "MATERIALS"),
    ]
    assert turns[1].words is None and turns[1].end_ms == 150_000
    assert chosen.artisans.conversations[CONVERSATION_ID].topics_asked == ("PROCESS", "MATERIALS")
    assert ended == []


async def test_the_closing_ends_the_call_with_end_call() -> None:
    record = bound(expires_at=START, max_duration_seconds=170)
    chosen = deps(record)
    ended: list[Any] = []
    heard = heard_message(
        LlmChatRequest.model_validate(
            {"model": "m", "stream": True, "messages": [{"role": "user", "content": "That is all."}]}
        )
    )
    conversation_record = chosen.artisans.conversations[CONVERSATION_ID]
    artisan_tools = ArtisanTools(interview=FakeModel([]), turns=tools())
    reply = await artisan_agent_reply(
        record, conversation_record, heard, deps=chosen, tools=artisan_tools, on_end=ended.append
    )
    assert reply.end_call is not None and reply.end_call.message.startswith("Thank you.")
    assert [c.extraction for c in ended] == ["PENDING"]
