from __future__ import annotations

import logging
import time
import uuid
from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from app.core.errors import AppError, ExternalFailure
from app.core.shielded import ShieldedWork
from app.providers.elevenlabs import ElevenLabs, HeardSpeech, speech_seconds
from app.providers.quota import LedgerEntry, remaining_today, seconds_until_next_day
from app.schemas.voice import MAX_TURNS, RELAY_MAX_TURN_SECONDS, relay_frame, speech_path
from app.services.interface_words import reviewed_words
from app.services.status_lines import status_message

from .audio import upload_seconds
from .audio_decode import Measure
from .privacy import TranscriptCipher, heard_text
from .records import SessionRecord, TurnClaim, TurnHold, TurnSave, VoiceStore
from .reply_audio import ReplyAudio
from .seconds import (
    VOICE_SECONDS,
    capped_seconds,
    ledger_entry,
    relay_audio_key,
    relay_refund_key,
    relay_replay_key,
    relay_speech_key,
)
from .sessions import VoiceRefused
from .transcript import stored_transcript, turn_merge
from .turns import SpokenTurn, TurnAsk, TurnTools, spoken_turn

__all__ = ["NOT_HEARD", "SPEECH_GRACE", "RelayAudio", "RelayDeps", "relay_turn_events", "turn_speech"]

logger = logging.getLogger(__name__)

NOT_HEARD = "Couldn't hear that. Try again."
TOO_LONG = "Keep each turn under a minute."
CALL_ENDED = "This call has ended."
NO_TIME_LEFT = "Not enough voice time is left today."
TURN_FAILED = "That answer could not be prepared. Try again."
CLAIM_REFUSALS = {"ended": CALL_ENDED, "quota": NO_TIME_LEFT}
SPEECH_GRACE = timedelta(minutes=2)
Clock = Callable[[], datetime]


@dataclass(frozen=True)
class RelayAudio:
    content: bytes
    content_type: str
    least_seconds: int

    @classmethod
    async def measured(cls, content: bytes, content_type: str, measure: Measure) -> RelayAudio:
        return cls(content, content_type, await upload_seconds(content, content_type, measure))


@dataclass(frozen=True)
class RelayDeps:
    store: VoiceStore
    tools: TurnTools
    elevenlabs: ElevenLabs
    cipher: TranscriptCipher
    speech: ReplyAudio
    voice_id: str
    clock: Clock
    ids: Callable[[], uuid.UUID] = uuid.uuid4
    shield: ShieldedWork = field(default_factory=ShieldedWork)


async def relay_turn_events(record: SessionRecord, audio: RelayAudio, deps: RelayDeps) -> AsyncIterator[str]:
    turn = _RelayTurn(record, deps.ids(), deps)
    try:
        async for frame in turn.frames(audio):
            yield frame
    except AppError as error:
        logger.warning("relay turn stopped: %s", error)
        yield relay_frame("error", {"message": TURN_FAILED})
        yield await turn.done(None)
    except Exception:
        logger.exception("relay turn failed")
        yield relay_frame("error", {"message": TURN_FAILED})
        yield await turn.done(None)


class _RelayTurn:
    def __init__(self, record: SessionRecord, turn_id: uuid.UUID, deps: RelayDeps) -> None:
        self.record = record
        self.turn_id = turn_id
        self.deps = deps
        self.billed = 0
        self.turn_count = record.turn_count
        self.ended = False
        self.claimed_at: datetime | None = None

    async def frames(self, audio: RelayAudio) -> AsyncIterator[str]:
        claim = await self._claimed(audio)
        if claim.session is None:
            yield relay_frame("error", {"message": CLAIM_REFUSALS[claim.refusal or "ended"]})
            yield await self.done(None)
            return
        heard = await self.deps.shield.run(
            self._heard_and_settled(audio, claim.held), name="relay turn audio"
        )
        problem = self._problem(heard)
        text = heard_text(heard.text) if heard else ""
        if problem or not text:
            yield relay_frame("error", {"message": problem or NOT_HEARD})
            yield await self.done(None)
            return
        yield relay_frame("heard", {"text": text, "language": self.record.language})
        language = self.record.language
        searching = status_message("SEARCHING_STORED", language=language, words=reviewed_words(language))
        yield relay_frame("status", {"step": "SEARCHING_STORED", "message": searching})
        saved, earlier = await self._answered(claim.session, text)
        for frame in self._answer_frames(saved, earlier):
            yield frame
        yield await self.done(saved)

    async def done(self, saved: SpokenTurn | None) -> str:
        now = self.deps.clock()
        remaining = await self.remaining(now)
        ended = self.ended or remaining == 0 or self.turn_count >= MAX_TURNS
        if ended:
            await self.deps.store.end(self.record.id, now)
        payload = {
            "turnId": str(saved.turn_id if saved else self.turn_id),
            "answerId": str(saved.answer_id) if saved and saved.answer_id else None,
            "billedSeconds": self.billed,
            "remainingSeconds": remaining,
            "sessionEnded": ended,
        }
        return relay_frame("done", payload)

    async def _claimed(self, audio: RelayAudio) -> TurnClaim:
        self.claimed_at = self.deps.clock()
        key = relay_audio_key(self.record.id, self.turn_id)
        cap = ledger_entry(self.record, units=RELAY_MAX_TURN_SECONDS, key=key, counted_at=self.claimed_at)
        hold = TurnHold(entry=cap, least=audio.least_seconds)
        claim = await self.deps.store.claim_turn(self.record.id, self.claimed_at, hold)
        if claim.session is None:
            self.ended = claim.refusal == "ended"
        else:
            self.turn_count = claim.session.turn_count
            self.billed += claim.held
        return claim

    async def _heard_and_settled(self, audio: RelayAudio, held: int) -> HeardSpeech | None:
        heard: HeardSpeech | None = None
        try:
            heard = await self._heard(audio)
        finally:
            await self._settle_audio(held, audio.least_seconds, heard)
        return heard

    async def _settle_audio(self, held: int, least: int, heard: HeardSpeech | None) -> None:
        charge = min(held, max(least, heard.seconds if heard else 0))
        unused = held - charge
        if unused > 0:
            key = relay_refund_key(self.record.id, self.turn_id)
            refund = ledger_entry(self.record, units=-unused, key=key, counted_at=self.claimed_at)
            await self.deps.store.reserve(self.record.id, refund)
            self.billed -= unused

    async def _heard(self, audio: RelayAudio) -> HeardSpeech | None:
        keyterms = [self.record.craft.name] if self.record.craft else []
        try:
            return await self.deps.elevenlabs.speech_to_text(
                audio.content,
                content_type=audio.content_type,
                language=self.record.language,
                keyterms=keyterms,
            )
        except ExternalFailure as error:
            logger.warning("relay speech to text failed: %s", error)
            return None

    def _problem(self, heard: HeardSpeech | None) -> str | None:
        if heard is None:
            return NOT_HEARD
        if heard.seconds > RELAY_MAX_TURN_SECONDS:
            return TOO_LONG
        return None

    async def _answered(self, begun: SessionRecord, text: str) -> tuple[SpokenTurn, set[str]]:
        started = time.perf_counter()
        ask = TurnAsk.begun(
            begun, text, turn_id=self.turn_id, answer_id=self.deps.ids(), now=self.deps.clock()
        )
        turn = await spoken_turn(ask, self.deps.tools)
        audio = await self._speech(turn.spoken)
        latency = round((time.perf_counter() - started) * 1000)
        merge, saved = turn_merge(self.deps.cipher, turn)
        seconds: tuple[LedgerEntry, ...] = ()
        if audio is not None:
            units = capped_seconds(speech_seconds(len(audio)), await self.remaining(self.deps.clock()))
            key = relay_speech_key(self.record.id, self.turn_id)
            seconds = (ledger_entry(self.record, units=units, key=key),)
            self.billed += units
            await self.deps.speech.put(self.record.id, self.turn_id, audio)
        await self.deps.store.save_turn(
            self.record.id, TurnSave(merge=merge, answer=turn.answer(latency), seconds=seconds)
        )
        return saved.turn or turn, saved.earlier_sources

    async def _speech(self, text: str) -> bytes | None:
        try:
            return await self.deps.elevenlabs.speech(
                text, voice_id=self.deps.voice_id, language=self.record.language
            )
        except ExternalFailure as error:
            logger.warning("relay text to speech failed, the speech route will retry: %s", error)
            return None

    def _answer_frames(self, turn: SpokenTurn, earlier: set[str]) -> list[str]:
        frames = [relay_frame("source", source) for source in turn.sources if source["id"] not in earlier]
        frames += [relay_frame("sentence", {"sentence": sentence}) for sentence in turn.sentences]
        frames += [relay_frame("action", action) for action in turn.actions]
        path = speech_path(self.record.id, turn.turn_id)
        frames.append(relay_frame("spoken", {"text": turn.spoken, "speechPath": path}))
        return frames

    async def bill(self, seconds: int, key: str) -> None:
        units = capped_seconds(seconds, await self.remaining(self.deps.clock()))
        await self.deps.store.reserve(self.record.id, ledger_entry(self.record, units=units, key=key))
        self.billed += units

    async def remaining(self, now: datetime) -> int | None:
        used = await self.deps.store.seconds_used(self.record.user_id, now)
        return remaining_today(self.record.role, VOICE_SECONDS, used)


async def turn_speech(record: SessionRecord, turn_id: uuid.UUID, deps: RelayDeps) -> bytes:
    now = deps.clock()
    if not _speakable(record, now):
        raise VoiceRefused("speech_gone")
    cached = await deps.speech.get(record.id, turn_id)
    if cached is not None:
        return cached
    spoken = stored_transcript(deps.cipher, record.transcript).spoken_of(turn_id)
    if spoken is None:
        raise VoiceRefused("not_found")
    turn = _RelayTurn(record, turn_id, deps)
    if await turn.remaining(now) == 0:
        raise VoiceRefused("quota", retry_after=seconds_until_next_day(now))
    audio = await deps.elevenlabs.speech(spoken, voice_id=deps.voice_id, language=record.language)
    await turn.bill(speech_seconds(len(audio)), relay_replay_key(record.id, turn_id, deps.ids()))
    await deps.speech.put(record.id, turn_id, audio)
    return audio


def _speakable(record: SessionRecord, now: datetime) -> bool:
    if record.live_at(now):
        return True
    return record.ended_at is not None and now < record.ended_at + SPEECH_GRACE
