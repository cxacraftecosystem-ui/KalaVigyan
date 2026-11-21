from __future__ import annotations

import uuid
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import date
from typing import Any

from sqlalchemy import Select, func, literal, select, union_all
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clock import INDIA_TZ
from app.models import FieldImage, FieldRecording, FieldSegment, MediaRef, Source
from app.research.citations import SourceRef
from app.research.field_voices import (
    FieldVoicesTotals,
    PageFieldPhoto,
    PageVoice,
    PhotoGroup,
    VoiceStage,
)
from app.research.voices import VoiceSpeaker
from app.retrieval.field_scope import shown_recordings
from app.services.field_photo_scope import shown_field_photos, shown_size
from app.services.field_voices_credit import Credited, citation_line, month_year, person_line, span_locator
from app.services.field_voices_items import FeedPerson
from app.services.field_voices_records import sentences_within

from . import knowledge_view, testimony_store

__all__ = [
    "FieldVoicesPart",
    "craft_field_photos",
    "craft_name_of",
    "craft_voices",
    "field_voice",
    "quote_order",
    "recording_stage",
    "speaker_of",
    "voices_part",
    "workshop_of",
]

ENGLISH_MAX_CHARS = 1200
QUOTE_MAX_CHARS = 600
QUOTED_KINDS = ("ARTISAN", "DESIGNER")
FIELD_RANK = 0
TESTIMONY_RANK = 1
KALAVIGYAN = "KALAVIGYAN"
KALAVIGYAN_PUBLISHER = "KalaVigyan"
FALLBACK_CRAFT = "the craft"
FALLBACK_ALT = "Photograph from a craft workshop"


@dataclass(frozen=True)
class FieldVoicesPart:
    voices: tuple[PageVoice, ...] = ()
    photos: tuple[PageFieldPhoto, ...] = ()
    totals: FieldVoicesTotals = field(default_factory=lambda: FieldVoicesTotals(quotes=0, images=0))
    sources: Mapping[str, SourceRef] = field(default_factory=dict)


@dataclass(frozen=True)
class _Voices:
    voices: list[PageVoice]
    sources: dict[str, SourceRef]
    total: int


async def voices_part(
    session: AsyncSession, craft_id: uuid.UUID, *, voices: int, photos: int
) -> FieldVoicesPart:
    shown = await _merged_voices(session, craft_id, limit=voices, offset=0)
    pictures, image_total = await craft_field_photos(session, craft_id, limit=photos, offset=0)
    return FieldVoicesPart(
        voices=tuple(shown.voices),
        photos=tuple(pictures),
        totals=FieldVoicesTotals(quotes=shown.total, images=image_total),
        sources=shown.sources,
    )


async def craft_voices(
    session: AsyncSession, craft_id: uuid.UUID, *, limit: int, offset: int
) -> tuple[list[PageVoice], int]:
    shown = await _merged_voices(session, craft_id, limit=limit, offset=offset)
    return shown.voices, shown.total


async def craft_field_photos(
    session: AsyncSession, craft_id: uuid.UUID, *, limit: int, offset: int
) -> tuple[list[PageFieldPhoto], int]:
    shown = shown_field_photos(craft_id)
    rows = await session.execute(
        select(FieldImage, MediaRef.imageUrl, *shown_size())
        .join(MediaRef, MediaRef.id == FieldImage.mediaRefId)
        .where(*shown)
        .order_by(FieldImage.takenAt.desc().nulls_last(), FieldImage.id)
        .offset(offset)
        .limit(limit)
    )
    photos = [_photo(row, url, (width, height)) for row, url, width, height in rows]
    total = await session.scalar(select(func.count()).select_from(FieldImage).where(*shown))
    return photos, int(total or 0)


def craft_name_of(context: Mapping[str, Any]) -> str:
    crafts = context.get("crafts") or []
    return (crafts[0].get("name") if crafts else None) or FALLBACK_CRAFT


def workshop_of(context: Mapping[str, Any]) -> str | None:
    return context.get("workshopLine") or None


def speaker_of(person: FeedPerson, craft: str) -> VoiceSpeaker:
    area = person.area
    return VoiceSpeaker(
        name=person.name,
        line=person_line(Credited(person, craft, None)),
        role=person.kind,
        years_in_craft=person.years_in_craft,
        district=area.district if area else None,
        state=area.state if area else None,
    )


def recording_stage(context: Mapping[str, Any]) -> VoiceStage | None:
    stage = context.get("stage")
    if stage:
        parts = (stage.get("title"), stage.get("entityLabel"), stage.get("rowLabel"))
        return VoiceStage(kind="DESIGN_STAGE", key=stage.get("key"), label=" · ".join(p for p in parts if p))
    topic = next((t for t in context.get("topics") or [] if t.get("question") or t.get("sectionTitle")), None)
    if topic:
        label = topic.get("question") or topic.get("sectionTitle")
        return VoiceStage(
            kind="QUESTION", key=topic.get("questionCode") or topic.get("sectionCode"), label=label
        )
    record = context.get("record")
    if record and record.get("name"):
        return VoiceStage(kind="RECORD", key=record.get("kind"), label=record["name"])
    return None


def field_voice(segment: FieldSegment, recording: FieldRecording) -> PageVoice | None:
    people = {person["id"]: FeedPerson.model_validate(person) for person in recording.people}
    person = people.get(segment.personId or "")
    if person is None or person.kind not in QUOTED_KINDS:
        return None
    context = recording.context or {}
    speaker = speaker_of(person, craft_name_of(context))
    position = segment.position + 1
    locator = span_locator(segment.startMs, segment.endMs, first=position, last=position)
    day = recording.recordedAt.astimezone(INDIA_TZ).date()
    workshop = workshop_of(context)
    return PageVoice(
        item_id=f"{recording.portal}:{recording.portalMediaId}:{segment.portalSegmentId}",
        origin=recording.portal,
        speaker=speaker,
        quote=sentences_within(segment.text, QUOTE_MAX_CHARS)[0],
        language=segment.language,
        english=sentences_within(segment.english, ENGLISH_MAX_CHARS)[0] if segment.english else None,
        english_source=segment.englishSource if segment.english else None,
        source_id=str(recording.sourceId),
        locator=locator,
        workshop=workshop,
        recorded_on=day.isoformat(),
        stage=recording_stage(context),
        citation=citation_line(
            speaker.line, day=day, workshop=workshop, portal=recording.portal, locator=locator
        ),
        recording_id=recording.id,
    )


async def _merged_voices(session: AsyncSession, craft_id: uuid.UUID, *, limit: int, offset: int) -> _Voices:
    rows = (await session.execute(quote_order(craft_id).offset(offset).limit(limit))).all()
    field_ids = [row.item for row in rows if row.origin == FIELD_RANK]
    told_ids = [row.item for row in rows if row.origin == TESTIMONY_RANK]
    field_voices, known = await _field_quotes(session, field_ids)
    told = await testimony_store.quote_states(session, told_ids)
    known |= {
        str(quote.source_id): SourceRef.model_validate(quote.source)
        for quote in told.values()
        if quote.source
    }
    voices = {**field_voices, **{key: _testimony_voice(quote) for key, quote in told.items()}}
    ordered = [voices[row.item] for row in rows if row.item in voices]
    shown = [voice for voice in ordered if voice.source_id in known]
    total = await _field_quote_count(session, craft_id)
    total += await testimony_store.approved_quote_count(session, craft_id)
    return _Voices(
        voices=shown, sources={voice.source_id: known[voice.source_id] for voice in shown}, total=total
    )


def quote_order(craft_id: uuid.UUID) -> Select[Any]:
    field = (
        select(
            FieldRecording.recordedAt.label("moment"),
            literal(FIELD_RANK).label("origin"),
            FieldRecording.recordedAt.label("settled"),
            FieldRecording.id.label("holder"),
            FieldSegment.position.label("turn"),
            FieldSegment.id.label("item"),
        )
        .select_from(FieldSegment)
        .join(FieldRecording, FieldRecording.id == FieldSegment.recordingId)
        .where(FieldSegment.quotable, *shown_recordings(craft_id))
    )
    told = testimony_store.approved_quote_order(craft_id).subquery()
    testimony = select(
        told.c.moment,
        literal(TESTIMONY_RANK).label("origin"),
        told.c.settled,
        told.c.item.label("holder"),
        literal(0).label("turn"),
        told.c.item,
    )
    merged = union_all(field, testimony).subquery()
    return select(merged.c.origin, merged.c.item).order_by(
        merged.c.moment.desc(),
        merged.c.origin,
        merged.c.settled.desc(),
        merged.c.holder,
        merged.c.turn,
        merged.c.item,
    )


async def _field_quote_count(session: AsyncSession, craft_id: uuid.UUID) -> int:
    total = await session.scalar(
        select(func.count())
        .select_from(FieldSegment)
        .join(FieldRecording, FieldRecording.id == FieldSegment.recordingId)
        .where(FieldSegment.quotable, *shown_recordings(craft_id))
    )
    return int(total or 0)


async def _field_quotes(
    session: AsyncSession, segment_ids: list[uuid.UUID]
) -> tuple[dict[uuid.UUID, PageVoice], dict[str, SourceRef]]:
    if not segment_ids:
        return {}, {}
    rows = (
        await session.execute(
            select(FieldSegment, FieldRecording, Source)
            .join(FieldRecording, FieldRecording.id == FieldSegment.recordingId)
            .join(Source, Source.id == FieldRecording.sourceId)
            .where(FieldSegment.id.in_(segment_ids))
        )
    ).all()
    voices = {
        segment.id: voice for segment, recording, _ in rows if (voice := field_voice(segment, recording))
    }
    sources = {
        str(source.id): SourceRef.model_validate(knowledge_view.source_ref(source)) for *_, source in rows
    }
    return voices, sources


def _testimony_voice(quote: testimony_store.TestimonyQuote) -> PageVoice:
    speaker = quote.speaker
    return PageVoice(
        item_id=quote.item_id,
        origin=KALAVIGYAN,
        speaker=VoiceSpeaker(
            name=speaker.name,
            line=speaker.line,
            role=speaker.role,
            district=speaker.district or None,
            state=speaker.state or None,
        ),
        quote=quote.quote,
        language=quote.language,
        english=quote.english,
        english_source=quote.english_source if quote.english else None,
        source_id=str(quote.source_id),
        locator=quote.locator,
        workshop=None,
        recorded_on=quote.recorded_on,
        stage=None,
        citation=f"{speaker.line}, recorded {_month(quote.recorded_on)}, {KALAVIGYAN_PUBLISHER}, {quote.locator}",
        recording_id=None,
    )


def _month(recorded_on: str) -> str:
    year, _, rest = recorded_on.partition("-")
    month = rest[:2]
    if not (year.isdigit() and month.isdigit()):
        return recorded_on
    return month_year(date(int(year), int(month), 1))


def _photo(row: FieldImage, url: str, size: tuple[int, int]) -> PageFieldPhoto:
    context = row.context or {}
    people = {person["id"]: person for person in row.people}
    credited = [people[c["personId"]].get("name") for c in row.credits if c["personId"] in people]
    return PageFieldPhoto(
        item_id=f"{row.portal}:{row.portalMediaId}",
        origin=row.portal,
        image_url=url,
        width=size[0],
        height=size[1],
        caption=row.caption,
        alt=context.get("alt") or FALLBACK_ALT,
        credit=context.get("credit") or row.rightsHolder,
        credited=[name for name in credited if name],
        workshop=workshop_of(context),
        taken_on=row.takenAt.astimezone(INDIA_TZ).date() if row.takenAt else None,
        groups=[PhotoGroup.model_validate(group) for group in context.get("groups") or []],
        statement=row.statement,
        rights_holder=row.rightsHolder,
        licence=None,
    )
