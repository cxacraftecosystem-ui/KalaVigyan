import uuid
from dataclasses import replace
from datetime import timedelta
from pathlib import Path
from typing import Any

import httpx
import pytest

from app.research.testimony import RECORDING_NOTICE_VERSION
from app.schemas.artisan import AgentConversationStarted, RelayConversationStarted
from app.schemas.voice import MAX_SESSION_SECONDS
from app.voice import artisan_session
from app.voice.agent_turn import AgentCall, authorised_session
from app.voice.artisan_guide import guide_question
from app.voice.artisan_session import (
    ArtisanRefused,
    ConversationDeps,
    StartConversation,
    artisan_voice,
    end_conversation,
    start_conversation,
)
from app.voice.artisan_transcript import open_transcript, sealed_merge
from app.voice.binding import ARTISAN_NONCE_CONTEXT, session_is_bound
from app.voice.reply_audio import ReplyAudio
from app.voice.runtime import VoiceRuntime, VoiceSettings
from app.voice.sessions import VoiceRefused

from .artisan_fakes import OTHER_CRAFT, MemoryArtisanStore, artisan_turn as said, artisan_user, facts
from .fakes import BEARER, CONVERSATION_ID, CRAFT, HMAC_KEY, START, MemoryStore, cipher, ids, session
from .listen_fakes import MemoryObjects

FIXTURES = Path(__file__).parent / "fixtures"
SPEECH = b"\xff\xfb" * 24_000
NEW_IDS = [uuid.UUID(int=n) for n in range(101, 120)]


def voice(transport: str = "RELAY", **changes: Any) -> VoiceSettings:
    base = VoiceSettings(
        transport=transport,
        max_live_sessions=5,
        voice_id="voice_1",
        api_key="test-only-elevenlabs-key",
        agent_id="artisan_agent_test",
        llm_bearer=BEARER,
        hmac_key=HMAC_KEY,
        cipher=cipher(),
    )
    return replace(base, **changes)


def runtime(*, reachable: bool = True) -> VoiceRuntime:
    def answer(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/v1/user":
            return httpx.Response(200 if reachable else 401, json={})
        if request.url.path.startswith("/v1/text-to-speech/"):
            return httpx.Response(200, content=SPEECH)
        return httpx.Response(200, content=(FIXTURES / "conversation_token.json").read_bytes())

    return VoiceRuntime(client=httpx.AsyncClient(transport=httpx.MockTransport(answer)))


def deps(
    store: MemoryStore | None = None,
    artisans: MemoryArtisanStore | None = None,
    settings: VoiceSettings | None = None,
    *,
    reachable: bool = True,
) -> ConversationDeps:
    store = store or MemoryStore()
    artisans = artisans or MemoryArtisanStore()
    artisans.voice = store
    return ConversationDeps(
        store=store,
        artisans=artisans,
        runtime=runtime(reachable=reachable),
        voice=settings or voice(),
        cipher=cipher(),
        speech=ReplyAudio(MemoryObjects()),
        clock=lambda: START,
        ids=ids(*NEW_IDS),
    )


def ask(**changes: Any) -> StartConversation:
    base = StartConversation(artisan_user(), CRAFT.slug, "en", RECORDING_NOTICE_VERSION)
    return replace(base, **changes)


async def test_a_relay_conversation_opens_by_naming_the_craft_and_asking_how_the_work_is_done() -> None:
    chosen = deps()
    started = RelayConversationStarted.model_validate(await start_conversation(ask(), chosen))
    assert started.craft == CRAFT and started.max_turns == 40
    assert started.opening.text.startswith("Namaste. I will record what you tell me about Kutch Ajrakh")
    assert started.opening.text.endswith(guide_question("PROCESS", "en"))
    assert str(started.opening.speech_path).endswith(f"/turns/{started.opening.turn_id}/speech")
    [new] = chosen.artisans.started
    assert new.session.purpose == "ARTISAN" and new.session.mode == "VERIFIED"
    assert new.topics_asked == ("PROCESS",)
    opened = open_transcript(cipher(), new.transcript)
    assert [(t.ordinal, t.speaker, t.topic) for t in opened.turns] == [(0, "KALAVIGYAN", "PROCESS")]
    assert await chosen.speech.get(new.session.id, started.opening.turn_id) == SPEECH
    assert sum(e.units for e in chosen.store.ledger.values()) > 0


async def test_the_next_conversation_on_a_craft_starts_from_a_topic_not_yet_asked() -> None:
    artisans = MemoryArtisanStore(earlier_topics=("PROCESS",))
    started = RelayConversationStarted.model_validate(
        await start_conversation(ask(), deps(artisans=artisans))
    )
    assert started.opening.text.endswith(guide_question("MATERIALS", "en"))
    assert artisans.started[0].topics_asked == ("PROCESS", "MATERIALS")


@pytest.mark.parametrize(
    ("changes", "setup", "reason"),
    [
        ({"user": artisan_user(role="STUDENT")}, {}, "capability"),
        ({"user": artisan_user(emailVerifiedAt=None)}, {}, "unverified_email"),
        ({}, {"facts": facts(consent=False)}, "consent"),
        ({"notice_version": "2026-01-01"}, {}, "consent"),
        ({"language": "xx"}, {}, "language"),
        ({"craft_slug": OTHER_CRAFT.slug}, {}, "craft"),
        ({"craft_slug": "no-such-craft"}, {}, "craft"),
        ({}, {"voice": voice(api_key=None)}, "not_configured"),
        ({}, {"reachable": False}, "not_configured"),
        ({}, {"live": True}, "live_session"),
        ({}, {"voice": voice(max_live_sessions=0)}, "busy"),
    ],
)
async def test_each_start_check_refuses_with_its_reason(
    changes: dict[str, Any], setup: dict[str, Any], reason: str
) -> None:
    store = MemoryStore(used_before=setup.get("used", 0))
    if setup.get("live"):
        store.sessions[uuid.uuid4()] = session(user_id=artisan_user().id, role="ARTISAN", started_at=START)
    artisans = MemoryArtisanStore(known=setup.get("facts", facts()))
    chosen = deps(store, artisans, setup.get("voice"), reachable=setup.get("reachable", True))
    with pytest.raises(ArtisanRefused) as refused:
        await start_conversation(ask(**changes), chosen)
    assert refused.value.reason == reason
    assert artisans.started == []


async def test_no_conversation_is_refused_for_voice_time(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(artisan_session, "remaining_today", lambda *_: 29)
    artisans = MemoryArtisanStore()
    await start_conversation(ask(), deps(artisans=artisans))
    assert len(artisans.started) == 1
    assert artisans.started[0].session.max_duration_seconds == MAX_SESSION_SECONDS


async def test_the_capability_is_checked_before_anything_else_is_read() -> None:
    artisans = MemoryArtisanStore(known=facts(consent=False))
    with pytest.raises(ArtisanRefused) as refused:
        await start_conversation(
            ask(user=artisan_user(role="MASTER_ADMIN"), language="xx"), deps(artisans=artisans)
        )
    assert refused.value.reason == "capability"


async def test_an_agent_conversation_binds_with_the_artisan_nonce_context_only() -> None:
    chosen = deps(settings=voice("AGENT"))
    started = AgentConversationStarted.model_validate(await start_conversation(ask(), chosen))
    record = chosen.store.sessions[started.voice_session_id]
    assert record.purpose == "ARTISAN" and record.agent_id == "artisan_agent_test"
    assert session_is_bound(HMAC_KEY, record, record.conversation_id or "", context=ARTISAN_NONCE_CONTEXT)
    assert not session_is_bound(HMAC_KEY, record, record.conversation_id or "")
    assert (
        open_transcript(cipher(), chosen.artisans.started[0].transcript)
        .turns[0]
        .text.endswith(guide_question("PROCESS", "en"))
    )


async def test_the_call_s_custom_llm_refuses_an_artisan_session() -> None:
    store = MemoryStore()
    record = session(
        transport="AGENT",
        conversation_id=CONVERSATION_ID,
        purpose="ARTISAN",
        started_at=START,
        expires_at=START,
    )
    store.sessions[record.id] = record
    call = AgentCall(f"Bearer {BEARER}", CONVERSATION_ID)
    with pytest.raises(VoiceRefused):
        await authorised_session(store, voice("AGENT"), call, now=START + timedelta(seconds=5))


def test_an_agent_transport_without_the_artisan_agent_runs_relay() -> None:
    assert artisan_voice(voice("AGENT"), None).transport == "RELAY"
    assert artisan_voice(voice("AGENT"), " agent_x ").agent_id == "agent_x"
    assert artisan_voice(voice("RELAY"), None).agent_id is None


async def test_ending_reports_nothing_to_draw_when_the_artisan_never_spoke_and_the_same_twice() -> None:
    chosen = deps()
    started = RelayConversationStarted.model_validate(await start_conversation(ask(), chosen))
    record = chosen.artisans.conversations[started.conversation_id]
    first, _ = await end_conversation(record, chosen, now=START + timedelta(minutes=1))
    again, _ = await end_conversation(
        chosen.artisans.conversations[record.id], chosen, now=START + timedelta(minutes=2)
    )
    assert first["extraction"] == "NONE" and again == first
    assert chosen.store.sessions[started.voice_session_id].ended_at is not None


async def test_ending_after_the_artisan_spoke_leaves_the_extraction_pending() -> None:
    chosen = deps()
    started = RelayConversationStarted.model_validate(await start_conversation(ask(), chosen))
    record = chosen.artisans.conversations[started.conversation_id]
    merged = sealed_merge(cipher(), said(1, "We soak the cloth first."))(record.transcript)
    record = replace(record, transcript=merged)
    chosen.artisans.conversations[record.id] = record
    ended, finished = await end_conversation(record, chosen, now=START + timedelta(minutes=1))
    assert ended["extraction"] == "PENDING" and finished.extraction == "PENDING"
