from __future__ import annotations

import logging
import uuid
from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass, field
from datetime import datetime
from typing import Protocol

from app.core.errors import AppError, ExternalFailure
from app.core.shielded import ShieldedWork
from app.providers.elevenlabs import ElevenLabs, HeardSpeech, audio_seconds, speech_seconds
from app.providers.quota import LedgerEntry, remaining_today, seconds_until_next_day
from app.research.evidence import personal_data_in
from app.research.untrusted import clean_untrusted_text
from app.schemas.artisan import TranscriptTurn, artisan_frame, artisan_speech_path
from app.schemas.voice import MAX_TURNS, RELAY_MAX_TURN_SECONDS
from app.services.naming import artisan_audio_file_name, artisan_audio_key

from .artisan_records import AudioWrite, ConversationRecord, TurnWrite
from .artisan_reply import ArtisanTools, KalaVigyanTurn, kalavigyan_turn, transcript_turn
from .artisan_session import ArtisanRefused, ConversationDeps, end_conversation
from .artisan_transcript import open_transcript, sealed_merge, words_from
from .audio import upload_seconds
from .audio_decode import Measure
from .privacy import heard_text
from .records import SessionRecord, TurnClaim, TurnHold
from .relay import SPEECH_GRACE
from .seconds import (
    VOICE_SECONDS,
    capped_seconds,
    ledger_entry,
    relay_audio_key,
    relay_refund_key,
    relay_replay_key,
    relay_speech_key,
)

__all__ = ["ArtisanUpload", "AudioBucket", "RelayTurnDeps", "artisan_turn_events", "conversation_speech"]

logger = logging.getLogger(__name__)

NOT_HEARD = "Couldn't hear that. Try again."
TOO_LONG = "Keep each part under a minute."
TURN_FAILED = "That reply could not be prepared. Try again."
CLAIM_REFUSALS = {"ended": "This conversation has ended.", "quota": "Not enough voice time is left today."}
MS = 1000


class AudioBucket(Protocol):
    async def put(self, key: str, body: bytes, *, content_type: str) -> None: ...


@dataclass(frozen=True)
class ArtisanUpload:
    content: bytes
    content_type: str
    least_seconds: int
    continued: bool

    @classmethod
    async def measured(
        cls, content: bytes, content_type: str, measure: Measure, *, continued: bool
    ) -> ArtisanUpload:
        return cls(content, content_type, await upload_seconds(content, content_type, measure), continued)


@dataclass(frozen=True)
class RelayTurnDeps:
    conversation: ConversationDeps
    tools: ArtisanTools
    elevenlabs: ElevenLabs
    bucket: AudioBucket | None
    on_end: Callable[[ConversationRecord], None]
    shield: ShieldedWork = field(default_factory=ShieldedWork)


async def artisan_turn_events(
    conversation: ConversationRecord, upload: ArtisanUpload, deps: RelayTurnDeps
) -> AsyncIterator[str]:
    turn = _ArtisanTurn(conversation, deps)
    try:
        async for frame in turn.frames(upload):
            yield frame
    except AppError as error:
        logger.warning("artisan relay turn stopped: %s", error)
        yield artisan_frame("error", {"message": TURN_FAILED})
        yield await turn.done()
    except Exception:
        logger.exception("artisan relay turn failed")
        yield artisan_frame("error", {"message": TURN_FAILED})
        yield await turn.done()


async def conversation_speech(
    conversation: ConversationRecord, record: SessionRecord, turn_id: uuid.UUID, deps: ConversationDeps
) -> bytes:
    now = deps.clock()
    if not (record.live_at(now) or (record.ended_at is not None and now < record.ended_at + SPEECH_GRACE)):
        raise ArtisanRefused("speech_gone")
    cached = await deps.speech.get(record.id, turn_id)
    if cached is not None:
        return cached
    turn = open_transcript(deps.cipher, conversation.transcript).turn(turn_id)
    if turn is None or turn.speaker != "KALAVIGYAN":
        raise ArtisanRefused("not_found")
    used = await deps.store.seconds_used(record.user_id, now)
    remaining = remaining_today(record.role, VOICE_SECONDS, used)
    if remaining == 0:
        raise ArtisanRefused("quota", retry_after=seconds_until_next_day(now))
    audio = await deps.runtime.elevenlabs(deps.voice).speech(
        turn.text, voice_id=deps.voice.voice_id, language=record.language
    )
    units = capped_seconds(speech_seconds(len(audio)), remaining)
    key = relay_replay_key(record.id, turn_id, deps.ids())
    await deps.store.reserve(record.id, ledger_entry(record, units=units, key=key))
    await deps.speech.put(record.id, turn_id, audio)
    return audio


class _ArtisanTurn:
    def __init__(self, conversation: ConversationRecord, deps: RelayTurnDeps) -> None:
        self.conversation = conversation
        self.deps = deps
        self.base = deps.conversation
        self.turn_id = self.base.ids()
        self.session: SessionRecord | None = None
        self.billed = 0
        self.ended = False

    async def frames(self, upload: ArtisanUpload) -> AsyncIterator[str]:
        claim = await self._claimed(upload)
        if claim.session is None:
            yield artisan_frame("error", {"message": CLAIM_REFUSALS[claim.refusal or "ended"]})
            yield await self.done()
            return
        yield artisan_frame("status", {"step": "transcribing"})
        heard = await self.deps.shield.run(
            self._heard_and_settled(upload, claim.held), name="artisan turn audio"
        )
        text = heard_text(heard.text) if heard else ""
        if heard is None or heard.seconds > RELAY_MAX_TURN_SECONDS or not text:
            problem = TOO_LONG if heard and heard.seconds > RELAY_MAX_TURN_SECONDS else NOT_HEARD
            yield artisan_frame("error", {"message": problem})
            yield await self.done()
            return
        await self._kept_turn(upload, heard, text)
        heard_event = {"turnId": str(self.turn_id), "text": text, "language": self.conversation.language}
        yield artisan_frame("heard", heard_event | {"continued": upload.continued})
        if not upload.continued:
            yield artisan_frame("status", {"step": "thinking"})
            reply = await self._reply()
            yield artisan_frame("status", {"step": "speaking"})
            for frame in await self._spoken(reply):
                yield frame
        yield await self.done()

    async def done(self) -> str:
        now = self.base.clock()
        remaining = await self._remaining(now)
        turns = self.session.turn_count if self.session else 0
        if not self.ended and (remaining == 0 or turns >= MAX_TURNS):
            await self._end(now)
        payload = {
            "turnId": str(self.turn_id),
            "billedSeconds": max(0, self.billed),
            "remainingSeconds": remaining,
            "sessionEnded": self.ended,
        }
        return artisan_frame("done", payload)

    async def _claimed(self, upload: ArtisanUpload) -> TurnClaim:
        session_id = self.conversation.voice_session_id or uuid.uuid4()
        record = await self.base.store.by_id(session_id)
        if record is None:
            return TurnClaim(None, refusal="ended")
        cap = ledger_entry(record, units=RELAY_MAX_TURN_SECONDS, key=relay_audio_key(record.id, self.turn_id))
        claim = await self.base.store.claim_turn(
            record.id, self.base.clock(), TurnHold(entry=cap, least=upload.least_seconds)
        )
        if claim.session is None:
            self.ended = claim.refusal == "ended"
            self.session = record
        else:
            self.session = claim.session
            self.billed += claim.held
        return claim

    async def _heard_and_settled(self, upload: ArtisanUpload, held: int) -> HeardSpeech | None:
        heard: HeardSpeech | None = None
        try:
            heard = await self.deps.elevenlabs.speech_to_text(
                upload.content,
                content_type=upload.content_type,
                language=self.conversation.language,
                keyterms=[self.conversation.craft.name],
            )
        except ExternalFailure as error:
            logger.warning("artisan speech to text failed: %s", error)
        finally:
            await self._refund(held, max(upload.least_seconds, heard.seconds if heard else 0))
        return heard

    async def _refund(self, held: int, used: int) -> None:
        unused = held - min(held, used)
        if unused > 0 and self.session is not None:
            key = relay_refund_key(self.session.id, self.turn_id)
            await self.base.store.reserve(self.session.id, ledger_entry(self.session, units=-unused, key=key))
            self.billed -= unused

    async def _kept_turn(self, upload: ArtisanUpload, heard: HeardSpeech, text: str) -> None:
        session = self._live()
        transcript = open_transcript(self.base.cipher, self.conversation.transcript)
        previous_end = transcript.turns[-1].end_ms if transcript.turns else 0
        received = self.base.clock()
        duration_ms = max(heard.seconds, upload.least_seconds) * MS
        offset = max(previous_end, round((received - session.started_at).total_seconds() * MS) - duration_ms)
        scrubbed = bool(personal_data_in(clean_untrusted_text(heard.text)))
        words = None if scrubbed or not heard.words else words_from(heard.words, offset)
        end_ms = offset + (round(heard.words[-1].end * MS) if heard.words else duration_ms)
        audio = (
            None
            if scrubbed
            else await self._stored_audio(upload, session, len(transcript.turns), offset, duration_ms)
        )
        turn = TranscriptTurn(
            id=self.turn_id,
            ordinal=len(transcript.turns),
            speaker="ARTISAN",
            text=text,
            start_ms=offset,
            end_ms=max(offset, end_ms),
            words=words,
            audio_id=uuid.uuid4() if audio else None,
            scrubbed=scrubbed,
            continued=upload.continued,
        )
        await self.base.artisans.save_turn(
            self.conversation.id, TurnWrite(merge=sealed_merge(self.base.cipher, turn), audio=audio)
        )

    async def _stored_audio(
        self, upload: ArtisanUpload, session: SessionRecord, ordinal: int, offset: int, duration_ms: int
    ) -> AudioWrite | None:
        if self.deps.bucket is None:
            return None
        leaf = artisan_audio_file_name(
            recorded_at=self.base.clock(),
            district=self.conversation.district,
            craft=self.conversation.craft.name,
            ordinal=min(session.turn_count, 99) or 1,
            mime_type=upload.content_type,
        )
        key = artisan_audio_key(self.conversation.user_id, leaf)
        try:
            await self.deps.bucket.put(key, upload.content, content_type=upload.content_type)
        except AppError as error:
            logger.warning("an artisan recording was not kept: %s", error)
            return None
        return AudioWrite(
            turn_id=self.turn_id,
            ordinal=ordinal,
            object_key=key,
            mime_type=upload.content_type,
            byte_count=len(upload.content),
            duration_ms=duration_ms,
            start_ms=offset,
        )

    async def _reply(self) -> KalaVigyanTurn:
        fresh = await self.base.artisans.by_id(self.conversation.id) or self.conversation
        self.conversation = fresh
        transcript = open_transcript(self.base.cipher, fresh.transcript)
        ids = (self.base.ids(), self.base.ids())
        return await kalavigyan_turn(
            fresh, self._live(), transcript, tools=self.deps.tools, ids=ids, now=self.base.clock()
        )

    async def _spoken(self, reply: KalaVigyanTurn) -> list[str]:
        session = self._live()
        audio = await self._speech(reply.text)
        seconds: tuple[LedgerEntry, ...] = ()
        if audio is not None:
            units = capped_seconds(speech_seconds(len(audio)), await self._remaining(self.base.clock()))
            seconds = (ledger_entry(session, units=units, key=relay_speech_key(session.id, reply.turn_id)),)
            self.billed += units
            await self.base.speech.put(session.id, reply.turn_id, audio)
        start = round((self.base.clock() - session.started_at).total_seconds() * MS)
        spoken_ms = round(audio_seconds(len(audio)) * MS) if audio else 0
        turn = transcript_turn(reply, start_ms=start, end_ms=start + spoken_ms)
        topics = tuple(
            dict.fromkeys([*self.conversation.topics_asked, *([turn.topic] if turn.topic else [])])
        )
        answer = reply.answer.answer(0) if reply.answer else None
        write = TurnWrite(
            merge=sealed_merge(self.base.cipher, turn), topics_asked=topics, answer=answer, seconds=seconds
        )
        await self.base.artisans.save_turn(self.conversation.id, write)
        frames = _reply_frames(self.conversation, reply)
        if reply.closing:
            await self._end(self.base.clock())
        return frames

    async def _speech(self, text: str) -> bytes | None:
        try:
            return await self.deps.elevenlabs.speech(
                text, voice_id=self.base.voice.voice_id, language=self.conversation.language
            )
        except ExternalFailure as error:
            logger.warning("artisan reply speech failed, the speech route will retry: %s", error)
            return None

    async def _end(self, now: datetime) -> None:
        fresh = await self.base.artisans.by_id(self.conversation.id) or self.conversation
        _, finished = await end_conversation(fresh, self.base, now=now)
        self.ended = True
        self.deps.on_end(finished)

    async def _remaining(self, now: datetime) -> int | None:
        used = await self.base.store.seconds_used(self.conversation.user_id, now)
        role = self.session.role if self.session else ""
        return remaining_today(role, VOICE_SECONDS, used)

    def _live(self) -> SessionRecord:
        if self.session is None:
            raise ArtisanRefused("not_found")
        return self.session


def _reply_frames(conversation: ConversationRecord, reply: KalaVigyanTurn) -> list[str]:
    path = artisan_speech_path(conversation.id, reply.turn_id)
    if reply.closing:
        return [
            artisan_frame("closing", {"turnId": str(reply.turn_id), "text": reply.text, "speechPath": path})
        ]
    answer = reply.answer
    frames = [artisan_frame("source", source) for source in (answer.sources if answer else ())]
    payload = {
        "turnId": str(reply.turn_id),
        "answerId": str(answer.answer_id) if answer and answer.answer_id else None,
        "sentences": list(answer.sentences) if answer else [],
        "question": reply.question.spoken,
        "english": reply.english,
        "topic": reply.question.topic,
        "text": reply.text,
        "speechPath": path,
    }
    frames.append(artisan_frame("reply", payload))
    return frames
