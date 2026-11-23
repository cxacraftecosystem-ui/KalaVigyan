from __future__ import annotations

import uuid
from collections.abc import Sequence
from dataclasses import dataclass

from app.models import FieldRecording, FieldSegment
from app.models.knowledge import QUOTE_MAX_CHARS
from app.research.field_voices import PageVoice
from app.research.quotes import quote_occurs, trivial_quote
from app.research.retrieval import ChunkHit

from .field_voices_records import SENTENCE_END
from .field_voices_view import field_voice

__all__ = [
    "ARTISAN_ROLE",
    "FieldTurn",
    "TurnCite",
    "UnquotedTurn",
    "artisan_turn",
    "backing_rank",
    "says",
    "spoken_quote",
    "unquoted_turns",
]

ARTISAN_ROLE = "ARTISAN"

TurnRow = tuple[FieldSegment, FieldRecording]


@dataclass(frozen=True)
class TurnCite:
    claim_id: uuid.UUID
    source_id: uuid.UUID
    chunk_id: uuid.UUID | None
    quote: str


@dataclass(frozen=True)
class FieldTurn:
    segment: FieldSegment
    recording: FieldRecording
    voice: PageVoice


@dataclass(frozen=True)
class UnquotedTurn:
    turn: FieldTurn
    hit: ChunkHit
    quote: str


def says(segment: FieldSegment, quote: str) -> bool:
    return quote_occurs(quote, segment.text) or bool(segment.english and quote_occurs(quote, segment.english))


def artisan_turn(segment: FieldSegment, recording: FieldRecording) -> FieldTurn | None:
    voice = field_voice(segment, recording)
    if voice is None or voice.speaker.role != ARTISAN_ROLE:
        return None
    return FieldTurn(segment, recording, voice)


def backing_rank(cite: TurnCite, hits: Sequence[ChunkHit]) -> int | None:
    for rank, hit in enumerate(hits):
        if hit.source_id == cite.source_id and (
            hit.chunk_id == cite.chunk_id or quote_occurs(cite.quote, hit.text)
        ):
            return rank
    return None


def spoken_quote(text: str) -> str | None:
    words = text.split()
    kept: list[str] = []
    length = -1
    for word in words:
        length += len(word) + 1
        if length > QUOTE_MAX_CHARS:
            break
        kept.append(word)
    quote = " ".join(kept)
    if len(kept) < len(words):
        sentences = SENTENCE_END.split(quote)
        if len(sentences) > 1:
            quote = " ".join(sentences[:-1])
    return quote if quote and not trivial_quote(quote) else None


def unquoted_turns(
    hits: Sequence[ChunkHit], cites: Sequence[TurnCite], rows: Sequence[TurnRow], *, limit: int
) -> list[UnquotedTurn]:
    cited = {cite.chunk_id for cite in cites}
    found: dict[uuid.UUID, UnquotedTurn] = {}
    for hit in hits:
        if len(found) >= limit:
            break
        if hit.chunk_id in cited:
            continue
        turn = _turn_holding(hit, rows)
        if turn is None or turn.segment.id in found or _quoted(turn, cites):
            continue
        quote = spoken_quote(hit.text)
        if quote is not None:
            found[turn.segment.id] = UnquotedTurn(turn, hit, quote)
    return list(found.values())


def _turn_holding(hit: ChunkHit, rows: Sequence[TurnRow]) -> FieldTurn | None:
    for segment, recording in rows:
        if recording.sourceId == hit.source_id and segment.quotable and says(segment, hit.text):
            return artisan_turn(segment, recording)
    return None


def _quoted(turn: FieldTurn, cites: Sequence[TurnCite]) -> bool:
    source_id = turn.recording.sourceId
    return any(cite.source_id == source_id and says(turn.segment, cite.quote) for cite in cites)
