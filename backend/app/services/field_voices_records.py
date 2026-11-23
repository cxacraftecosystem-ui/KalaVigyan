from __future__ import annotations

import hashlib
import re
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from app.research.field_voices import (
    FIELD_EVIDENCE_KIND,
    FIELD_SOURCE_KIND,
    PORTAL_EXTERNAL_KEYS,
    PORTAL_PUBLISHERS,
)
from app.research.retrieval import PUBLIC_CHUNK_ACL, WINDOW_CHUNK_KIND
from app.retrieval.indexing import SourceChunk
from app.services.field_voices_credit import (
    Credited,
    credit_line,
    person_line,
    recording_title,
    span_locator,
    workshop_line,
)
from app.services.field_voices_items import FeedPerson, Segment, TranscriptItem

__all__ = [
    "CHUNK_MAX_CHARS",
    "QUOTED_KINDS",
    "QUOTE_MIN_CHARS",
    "PlannedSegment",
    "RecordingPlan",
    "recording_plan",
    "sentences_within",
    "source_values",
]

QUOTE_MIN_CHARS = 40
CHUNK_MAX_CHARS = 1500
QUOTED_KINDS = frozenset({"ARTISAN", "DESIGNER"})
SENTENCE_END = re.compile(r"(?<=[.!?।॥])\s+")
ENGLISH = "en"
RELIABILITY = "A"
SENSITIVITY = "ATTRIBUTE_REQUIRED"
ORIGIN = "IMPORT"
STORAGE = "FULL_TEXT"


@dataclass(frozen=True)
class PlannedSegment:
    portal_segment_id: str
    position: int
    speaker_key: str | None
    person_id: str | None
    role: str | None
    start_ms: int | None
    end_ms: int | None
    language: str
    text: str
    text_source: str
    english: str | None
    english_source: str | None
    quotable: bool


@dataclass(frozen=True)
class RecordingPlan:
    title: str
    authors: tuple[str, ...]
    credit: str
    workshop_line: str | None
    segments: tuple[PlannedSegment, ...]
    chunks: tuple[SourceChunk, ...]
    text_sha256: str


@dataclass(frozen=True)
class _Line:
    first: PlannedSegment
    last: PlannedSegment
    text: str


def recording_plan(item: TranscriptItem, *, portal: str) -> RecordingPlan:
    segments = tuple(_segments(item))
    credited = _credited(item)
    day = item.recorded_at.date()
    unnamed = any(person.person.name is None for person in credited)
    workshop = workshop_line(item.workshop, any_unnamed=unnamed, fallback_day=day)
    named = tuple(dict.fromkeys(c.person.name for c in credited if c.person.name))
    labels = _speaker_labels(item)
    return RecordingPlan(
        title=recording_title(_title_lead(item), workshop, item.area, day),
        authors=named,
        credit=credit_line(named, workshop=workshop, day=day, portal=portal),
        workshop_line=workshop,
        segments=segments,
        chunks=(*_quote_chunks(segments), *_window_chunks(segments, labels)),
        text_sha256=hashlib.sha256("\n".join(s.text for s in segments).encode("utf-8")).hexdigest(),
    )


def source_values(
    plan: RecordingPlan,
    item: TranscriptItem,
    *,
    portal: str,
    url: str | None,
    revision: str,
    retrieved_at: datetime,
) -> dict[str, Any]:
    return {
        "kind": FIELD_SOURCE_KIND,
        "title": plan.title,
        "authors": list(plan.authors),
        "year": item.recorded_at.year,
        "url": url,
        "publisher": PORTAL_PUBLISHERS[portal],
        "reliability": RELIABILITY,
        "storage": STORAGE,
        "sha256": plan.text_sha256,
        "origin": ORIGIN,
        "sensitivity": SENSITIVITY,
        "attribution": plan.credit,
        "evidenceKind": FIELD_EVIDENCE_KIND,
        "externalIds": {
            PORTAL_EXTERNAL_KEYS[portal]: {
                "mediaId": item.id,
                "recordingId": item.recording_id,
                "revision": revision,
            }
        },
        "retrievedAt": retrieved_at,
    }


def sentences_within(text: str, limit: int = CHUNK_MAX_CHARS) -> list[str]:
    if len(text) <= limit:
        return [text]
    pieces: list[str] = []
    current = ""
    for sentence in SENTENCE_END.split(text):
        joined = f"{current} {sentence}".strip()
        if current and len(joined) > limit:
            pieces.append(current)
            current = sentence
        else:
            current = joined
    if current:
        pieces.append(current)
    return [chunk for piece in pieces for chunk in _hard_cut(piece, limit)]


def _hard_cut(text: str, limit: int) -> list[str]:
    return [text[start : start + limit] for start in range(0, len(text), limit)]


def _title_lead(item: TranscriptItem) -> str:
    if item.session is not None:
        return "session"
    return "stage" if item.stage is not None else "other"


def _people(item: TranscriptItem) -> dict[str, FeedPerson]:
    return {person.id: person for person in item.people}


def _credited(item: TranscriptItem) -> list[Credited]:
    craft = item.crafts[0].name
    return [Credited(person, craft, item.area) for person in item.people if person.kind in QUOTED_KINDS]


def _segments(item: TranscriptItem) -> list[PlannedSegment]:
    people = _people(item)
    speakers = {speaker.key: speaker for speaker in item.speakers}
    planned: list[PlannedSegment] = []
    for segment in item.transcript.segments:
        speaker = speakers.get(segment.speaker_key) if segment.speaker_key else None
        person = people.get(speaker.person_id) if speaker and speaker.person_id else None
        role = person.kind if person else (speaker.role if speaker else None)
        planned.append(_planned(segment, person, role, turns=item.transcript.source == "TURNS"))
    return planned


def _planned(segment: Segment, person: FeedPerson | None, role: str | None, *, turns: bool) -> PlannedSegment:
    quotable = turns and person is not None and person.kind in QUOTED_KINDS
    return PlannedSegment(
        portal_segment_id=segment.id,
        position=segment.position,
        speaker_key=segment.speaker_key,
        person_id=person.id if person else None,
        role=role,
        start_ms=segment.start_ms,
        end_ms=segment.end_ms,
        language=segment.language,
        text=segment.text,
        text_source=segment.text_source,
        english=segment.english,
        english_source=segment.english_source,
        quotable=quotable and len(segment.text.strip()) >= QUOTE_MIN_CHARS,
    )


def _speaker_labels(item: TranscriptItem) -> dict[str, str]:
    people = _people(item)
    craft = item.crafts[0].name
    labels: dict[str, str] = {}
    for speaker in item.speakers:
        person = people.get(speaker.person_id) if speaker.person_id else None
        named = person_line(Credited(person, craft, item.area)) if person else None
        labels[speaker.key] = named or speaker.label
    return labels


def _quote_chunks(segments: Sequence[PlannedSegment]) -> list[SourceChunk]:
    chunks: list[SourceChunk] = []
    for segment in segments:
        if not segment.quotable:
            continue
        locator = _locator(segment, segment)
        chunks += [
            SourceChunk(text, locator, segment.language, PUBLIC_CHUNK_ACL)
            for text in sentences_within(segment.text)
        ]
        if segment.english and segment.english != segment.text:
            chunks += [
                SourceChunk(text, locator, ENGLISH, PUBLIC_CHUNK_ACL)
                for text in sentences_within(segment.english)
            ]
    return chunks


def _window_chunks(segments: Sequence[PlannedSegment], labels: dict[str, str]) -> list[SourceChunk]:
    original = [_Line(s, s, _line(labels, s, s.text)) for s in segments]
    english = [_Line(s, s, _line(labels, s, s.english)) for s in segments if s.english]
    languages = {s.language for s in segments}
    lang = segments[0].language if len(languages) == 1 else "und"
    return [*_windows(original, lang), *_windows(english, ENGLISH)]


def _line(labels: dict[str, str], segment: PlannedSegment, text: str | None) -> str:
    speaker = labels.get(segment.speaker_key) if segment.speaker_key else None
    return f"{speaker}: {text}" if speaker else str(text)


def _windows(lines: Sequence[_Line], lang: str) -> list[SourceChunk]:
    chunks: list[SourceChunk] = []
    window: list[_Line] = []
    for line in [part for whole in lines for part in _parts(whole)]:
        if window and len("\n".join(each.text for each in [*window, line])) > CHUNK_MAX_CHARS:
            chunks.append(_window_chunk(window, lang))
            window = []
        window.append(line)
    if window:
        chunks.append(_window_chunk(window, lang))
    return chunks


def _parts(line: _Line) -> list[_Line]:
    return [_Line(line.first, line.last, text) for text in sentences_within(line.text)]


def _window_chunk(window: Sequence[_Line], lang: str) -> SourceChunk:
    text = "\n".join(line.text for line in window)
    locator = _locator(window[0].first, window[-1].last)
    return SourceChunk(text, locator, lang, PUBLIC_CHUNK_ACL, kind=WINDOW_CHUNK_KIND)


def _locator(first: PlannedSegment, last: PlannedSegment) -> str:
    return span_locator(first.start_ms, last.end_ms, first=first.position + 1, last=last.position + 1)
