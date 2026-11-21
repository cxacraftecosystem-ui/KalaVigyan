from __future__ import annotations

import uuid
from datetime import date
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import InvalidInput
from app.models import Craft, FieldImage, FieldRecording, FieldRecordingCraft, FieldSegment
from app.research.crafts import CraftRef
from app.research.field_voices import (
    FIELD_LIST_PAGE_SIZE,
    FIELD_LIST_SCHEMA_VERSION,
    FIELD_TRANSCRIPT_SCHEMA_VERSION,
    PORTAL_PUBLISHERS,
    FieldTranscript,
    FieldVoicesList,
    TranscriptLine,
    TranscriptSpeaker,
)
from app.retrieval.field_scope import shown_recordings
from app.services.field_photo_scope import shown_field_photos
from app.services.field_voices_credit import Credited, citation_line, long_date, person_line, span_locator
from app.services.field_voices_items import FeedPerson
from app.services.field_voices_view import (
    craft_field_photos,
    craft_name_of,
    craft_voices,
    recording_stage,
    workshop_of,
)

__all__ = ["CURSOR_MAX_OFFSET", "field_list", "field_transcript", "list_offset", "shown_image"]

CURSOR_MAX_OFFSET = 100_000
WHOLE_RECORDING = "whole recording"


def list_offset(cursor: str | None) -> int:
    if cursor is None:
        return 0
    if not cursor.isdigit() or int(cursor) > CURSOR_MAX_OFFSET or int(cursor) % FIELD_LIST_PAGE_SIZE:
        raise InvalidInput("Unknown cursor.")
    return int(cursor)


async def field_list(
    session: AsyncSession, craft: Craft, *, kind: str, cursor: str | None
) -> FieldVoicesList:
    offset = list_offset(cursor)
    if kind == "quotes":
        quotes, total = await craft_voices(session, craft.id, limit=FIELD_LIST_PAGE_SIZE, offset=offset)
        images: list[Any] = []
    else:
        images, total = await craft_field_photos(session, craft.id, limit=FIELD_LIST_PAGE_SIZE, offset=offset)
        quotes = []
    following = offset + FIELD_LIST_PAGE_SIZE
    return FieldVoicesList(
        schema_version=FIELD_LIST_SCHEMA_VERSION,
        craft=CraftRef(slug=craft.slug, name=craft.name, path=f"/crafts/{craft.slug}"),
        kind=kind,
        total=total,
        cursor=cursor,
        next_cursor=str(following) if following < total else None,
        quotes=quotes,
        images=images,
    )


async def shown_image(session: AsyncSession, image_id: uuid.UUID) -> FieldImage | None:
    return await session.scalar(select(FieldImage).where(FieldImage.id == image_id, *shown_field_photos()))


async def field_transcript(session: AsyncSession, recording_id: uuid.UUID) -> FieldTranscript | None:
    recording = await session.scalar(
        select(FieldRecording).where(FieldRecording.id == recording_id, *shown_recordings())
    )
    if recording is None:
        return None
    segments = list(
        await session.scalars(
            select(FieldSegment)
            .where(FieldSegment.recordingId == recording.id)
            .order_by(FieldSegment.position)
        )
    )
    crafts = (
        await session.execute(
            select(Craft.slug, Craft.name)
            .join(FieldRecordingCraft, FieldRecordingCraft.craftId == Craft.id)
            .where(FieldRecordingCraft.recordingId == recording.id)
            .order_by(Craft.name)
        )
    ).all()
    return _transcript(
        recording, segments, [CraftRef(slug=c.slug, name=c.name, path=f"/crafts/{c.slug}") for c in crafts]
    )


def _transcript(
    recording: FieldRecording, segments: list[FieldSegment], crafts: list[CraftRef]
) -> FieldTranscript:
    context = recording.context
    workshop = workshop_of(context)
    english = recording.english or {}
    return FieldTranscript(
        schema_version=FIELD_TRANSCRIPT_SCHEMA_VERSION,
        id=recording.id,
        origin=recording.portal,
        publisher=PORTAL_PUBLISHERS[recording.portal],
        title=context.get("title") or "Field recording",
        media_type=recording.mediaType,
        recorded_at=recording.recordedAt,
        duration_ms=recording.durationMs,
        crafts=crafts,
        workshop=workshop,
        context=_context_lines(context),
        stage=recording_stage(context),
        speakers=_speakers(recording),
        lines=[_line(segment) for segment in segments],
        english=english.get("text"),
        english_source=english.get("source"),
        source_id=recording.sourceId,
        citation=citation_line(
            _speaking(recording),
            day=recording.recordedAt.date(),
            workshop=workshop,
            portal=recording.portal,
            locator=WHOLE_RECORDING,
        ),
    )


def _speakers(recording: FieldRecording) -> list[TranscriptSpeaker]:
    people = {person["id"]: FeedPerson.model_validate(person) for person in recording.people}
    craft = craft_name_of(recording.context)
    shown: list[TranscriptSpeaker] = []
    for speaker in recording.speakers:
        person = people.get(speaker.get("personId") or "")
        label = person_line(Credited(person, craft, None)) if person else speaker["label"]
        shown.append(
            TranscriptSpeaker(
                key=speaker["key"], label=label, role=person.kind if person else speaker.get("role")
            )
        )
    return shown


def _line(segment: FieldSegment) -> TranscriptLine:
    return TranscriptLine(
        id=segment.portalSegmentId,
        position=segment.position,
        speaker_key=segment.speakerKey,
        locator=span_locator(
            segment.startMs, segment.endMs, first=segment.position + 1, last=segment.position + 1
        ),
        language=segment.language,
        text=segment.text,
        english=segment.english,
        english_source=segment.englishSource,
        quotable=segment.quotable,
    )


def _context_lines(context: dict[str, Any]) -> list[str]:
    lines: list[str] = []
    session = context.get("session") or {}
    questionnaire = session.get("questionnaire") or {}
    if questionnaire.get("title"):
        lines.append(f"Questionnaire: {questionnaire['title']}")
    if session.get("date"):
        lines.append(f"Session of {long_date(date.fromisoformat(session['date']))}")
    area = context.get("area") or {}
    place = ", ".join(part for part in (area.get("district"), area.get("state")) if part)
    if place:
        lines.append(f"Recorded in {place}")
    record = context.get("record") or {}
    if record.get("name"):
        lines.append(f"About {record['name']}")
    return lines


def _speaking(recording: FieldRecording) -> str:
    craft = craft_name_of(recording.context)
    people = [FeedPerson.model_validate(person) for person in recording.people]
    named = [person_line(Credited(person, craft, None)) for person in people if person.kind != "RESEARCHER"]
    return ", ".join(dict.fromkeys(named)) or "Field recording"
