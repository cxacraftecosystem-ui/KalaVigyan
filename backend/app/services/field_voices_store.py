from __future__ import annotations

import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy import delete, or_, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.data.craft_master_loader import ID_NAMESPACE
from app.models import (
    Chunk,
    Claim,
    ClaimSource,
    Craft,
    FieldRecording,
    FieldRecordingCraft,
    FieldSegment,
    FieldVoiceStream,
    Source,
)
from app.research.quotes import quote_occurs
from app.research.retrieval import PASSAGE_CHUNK_KIND
from app.retrieval.indexing import replace_planned_chunks
from app.services.field_voices_feed import TRANSCRIPTS, Live, stream_digest
from app.services.field_voices_items import FeedCraft, TranscriptItem
from app.services.field_voices_records import RecordingPlan, recording_plan, source_values

__all__ = [
    "CRAFT_CHAIN_MAX",
    "STREAM_ROWS",
    "ApplyContext",
    "ResolvedCrafts",
    "apply_transcript",
    "field_recording_id",
    "field_source_id",
    "hide_stored",
    "reading_url",
    "recheck_quoted_claims",
    "resolve_crafts",
    "stored_digest",
    "stream_row",
    "withdraw_recording",
    "withdraw_source_claims",
]

CRAFT_CHAIN_MAX = 10
SOURCES_KEY = "portalSources"
STREAM_ROWS = {TRANSCRIPTS: "TRANSCRIPTS", "images": "IMAGES"}
READING_PATH = "/voices/{id}"


@dataclass(frozen=True)
class ApplyContext:
    now: datetime
    web_base: str | None
    api_base: str | None


@dataclass(frozen=True)
class ResolvedCrafts:
    craft_ids: tuple[uuid.UUID, ...]
    unresolved: tuple[dict[str, str], ...]


def field_recording_id(portal: str, media_id: str) -> uuid.UUID:
    return uuid.uuid5(ID_NAMESPACE, f"field-recording:{portal}:{media_id}")


def field_source_id(portal: str, media_id: str) -> uuid.UUID:
    return uuid.uuid5(ID_NAMESPACE, f"field-source:{portal}:{media_id}")


def field_segment_id(recording_id: uuid.UUID, segment_id: str) -> uuid.UUID:
    return uuid.uuid5(ID_NAMESPACE, f"field-segment:{recording_id}:{segment_id}")


async def stream_row(session: AsyncSession, portal: str, stream: str) -> FieldVoiceStream:
    key = (portal, STREAM_ROWS[stream])
    await session.execute(
        insert(FieldVoiceStream).values(portal=key[0], stream=key[1]).on_conflict_do_nothing()
    )
    row = await session.get(FieldVoiceStream, key, populate_existing=True)
    if row is None:
        raise RuntimeError(f"the {stream} stream row of {portal} could not be stored")
    return row


async def resolve_crafts(session: AsyncSession, portal: str, crafts: Sequence[FeedCraft]) -> ResolvedCrafts:
    portal_id = Craft.extraMetadata[SOURCES_KEY][portal]["id"].astext
    ids = [craft.id for craft in crafts]
    slugs = [craft.slug for craft in crafts]
    rows = (
        await session.execute(
            select(Craft.id, Craft.slug, Craft.mergedIntoId, portal_id.label("portal_id")).where(
                or_(portal_id.in_(ids), Craft.slug.in_(slugs))
            )
        )
    ).all()
    by_portal = {row.portal_id: row for row in rows if row.portal_id}
    by_slug = {row.slug: row for row in rows}
    found: list[uuid.UUID] = []
    unresolved: list[dict[str, str]] = []
    for craft in crafts:
        row = by_portal.get(craft.id) or by_slug.get(craft.slug)
        if row is None:
            unresolved.append({"id": craft.id, "slug": craft.slug, "name": craft.name})
            continue
        found.append(await _end_of_chain(session, row.id, row.mergedIntoId))
    return ResolvedCrafts(tuple(dict.fromkeys(found)), tuple(unresolved))


async def apply_transcript(
    session: AsyncSession, change: Live, *, portal: str, context: ApplyContext
) -> uuid.UUID | None:
    item = change.item
    if not isinstance(item, TranscriptItem):
        raise TypeError(f"transcript change {change.id} carries an image")
    recording_id = field_recording_id(portal, item.id)
    existing = await session.get(FieldRecording, recording_id)
    if existing is not None and existing.revision == change.revision:
        existing.seenAt = context.now
        existing.hiddenAt = None
        return None
    plan = recording_plan(item, portal=portal)
    source_id = await _upsert_source(session, plan, change, portal=portal, context=context)
    crafts = await resolve_crafts(session, portal, item.crafts)
    await _upsert_recording(session, change, plan, portal=portal, context=context, crafts=crafts)
    await _replace_segments(session, recording_id, plan)
    if existing is not None:
        await session.execute(delete(Chunk).where(Chunk.sourceId == source_id))
    await replace_planned_chunks(session, source_id, plan.chunks)
    if existing is not None:
        await recheck_quoted_claims(session, source_id)
    await _relink(session, recording_id, crafts.craft_ids)
    return source_id


async def withdraw_recording(session: AsyncSession, portal: str, media_id: str) -> bool:
    source_id = await session.scalar(
        select(FieldRecording.sourceId).where(
            FieldRecording.portal == portal, FieldRecording.portalMediaId == media_id
        )
    )
    if source_id is None:
        return False
    await withdraw_source_claims(session, source_id)
    await session.execute(delete(Source).where(Source.id == source_id))
    return True


async def withdraw_source_claims(session: AsyncSession, source_id: uuid.UUID) -> None:
    cited = select(ClaimSource.claimId).where(ClaimSource.sourceId == source_id)
    elsewhere = select(ClaimSource.claimId).where(
        ClaimSource.claimId.in_(cited), ClaimSource.sourceId != source_id
    )
    await session.execute(delete(Claim).where(Claim.id.in_(cited), Claim.id.not_in(elsewhere)))
    await session.execute(delete(ClaimSource).where(ClaimSource.sourceId == source_id))


async def recheck_quoted_claims(session: AsyncSession, source_id: uuid.UUID) -> None:
    quotes = (
        await session.execute(
            select(Chunk.id, Chunk.locator, Chunk.text)
            .where(Chunk.sourceId == source_id, Chunk.kind == PASSAGE_CHUNK_KIND)
            .order_by(Chunk.ordinal)
        )
    ).all()
    cites = list(
        await session.scalars(
            select(ClaimSource)
            .where(ClaimSource.sourceId == source_id)
            .execution_options(populate_existing=True)
        )
    )
    dropped: set[uuid.UUID] = set()
    for cite in cites:
        chunk = next((row for row in quotes if cite.quote and quote_occurs(cite.quote, row.text)), None)
        if chunk is None:
            dropped.add(cite.claimId)
            await session.delete(cite)
            continue
        cite.chunkId, cite.locator = chunk.id, chunk.locator
    await session.flush()
    if dropped:
        claims = sorted(dropped)
        cited = select(ClaimSource.claimId).where(ClaimSource.claimId.in_(claims))
        await session.execute(delete(Claim).where(Claim.id.in_(claims), Claim.id.not_in(cited)))


async def stored_digest(session: AsyncSession, model: Any, portal: str) -> tuple[int, str]:
    rows = (
        await session.execute(select(model.portalMediaId, model.revision).where(model.portal == portal))
    ).all()
    return len(rows), stream_digest((row.portalMediaId, row.revision) for row in rows)


async def hide_stored(session: AsyncSession, model: Any, portal: str, now: datetime) -> None:
    await session.execute(
        update(model).where(model.portal == portal, model.hiddenAt.is_(None)).values(hiddenAt=now)
    )


def reading_url(context: ApplyContext, recording_id: uuid.UUID) -> str | None:
    base = (context.web_base or "").rstrip("/")
    return f"{base}{READING_PATH.format(id=recording_id)}" if base.startswith("https://") else None


async def _end_of_chain(
    session: AsyncSession, craft_id: uuid.UUID, merged_into: uuid.UUID | None
) -> uuid.UUID:
    current, target = craft_id, merged_into
    for _ in range(CRAFT_CHAIN_MAX):
        if target is None:
            return current
        current = target
        target = await session.scalar(select(Craft.mergedIntoId).where(Craft.id == current))
    return current


async def _upsert_source(
    session: AsyncSession, plan: RecordingPlan, change: Live, *, portal: str, context: ApplyContext
) -> uuid.UUID:
    item = change.item
    source_id = field_source_id(portal, item.id)
    values = source_values(
        plan,
        item,
        portal=portal,
        url=reading_url(context, field_recording_id(portal, item.id)),
        revision=change.revision,
        retrieved_at=context.now,
    )
    statement = insert(Source).values(id=source_id, **values)
    await session.execute(statement.on_conflict_do_update(index_elements=[Source.id], set_=values))
    return source_id


async def _upsert_recording(
    session: AsyncSession,
    change: Live,
    plan: RecordingPlan,
    *,
    portal: str,
    context: ApplyContext,
    crafts: ResolvedCrafts,
) -> None:
    item = change.item
    values = _recording_values(item, plan, crafts)
    values |= {"revision": change.revision, "portalUpdatedAt": change.updated_at, "seenAt": context.now}
    row_id = field_recording_id(portal, item.id)
    keys = {
        "id": row_id,
        "portal": portal,
        "portalMediaId": item.id,
        "sourceId": field_source_id(portal, item.id),
    }
    statement = insert(FieldRecording).values(**keys, **values)
    await session.execute(statement.on_conflict_do_update(index_elements=[FieldRecording.id], set_=values))


def _recording_values(item: TranscriptItem, plan: RecordingPlan, crafts: ResolvedCrafts) -> dict[str, Any]:
    transcript = item.transcript
    context = {key: _dumped(getattr(item, key)) for key in ("workshop", "session", "stage", "record", "area")}
    return {
        "portalRecordingId": item.recording_id,
        "mediaType": item.media_type,
        "recordedAt": item.recorded_at,
        "durationMs": item.duration_ms,
        "context": context
        | {
            "topics": [topic.model_dump(mode="json") for topic in item.topics],
            "crafts": [craft.model_dump(mode="json") for craft in item.crafts],
            "workshopLine": plan.workshop_line,
            "credit": plan.credit,
            "title": plan.title,
        },
        "people": [person.model_dump(mode="json") for person in item.people],
        "speakers": [speaker.model_dump(mode="json") for speaker in item.speakers],
        "transcriptSource": transcript.source,
        "languages": list(transcript.languages),
        "english": _dumped(transcript.english),
        "scrubbing": item.scrubbing.model_dump(mode="json"),
        "unresolvedCrafts": list(crafts.unresolved),
        "hiddenAt": None,
    }


def _dumped(value: Any) -> Any:
    return value.model_dump(mode="json") if value is not None else None


async def _replace_segments(session: AsyncSession, recording_id: uuid.UUID, plan: RecordingPlan) -> None:
    await session.execute(delete(FieldSegment).where(FieldSegment.recordingId == recording_id))
    rows = [
        {
            "id": field_segment_id(recording_id, segment.portal_segment_id),
            "recordingId": recording_id,
            "portalSegmentId": segment.portal_segment_id,
            "position": segment.position,
            "speakerKey": segment.speaker_key,
            "personId": segment.person_id,
            "role": segment.role,
            "startMs": segment.start_ms,
            "endMs": segment.end_ms,
            "language": segment.language,
            "text": segment.text,
            "textSource": segment.text_source,
            "english": segment.english,
            "englishSource": segment.english_source,
            "quotable": segment.quotable,
        }
        for segment in plan.segments
    ]
    await session.execute(insert(FieldSegment), rows)


async def _relink(session: AsyncSession, recording_id: uuid.UUID, craft_ids: Sequence[uuid.UUID]) -> None:
    await session.execute(delete(FieldRecordingCraft).where(FieldRecordingCraft.recordingId == recording_id))
    if craft_ids:
        rows = [{"recordingId": recording_id, "craftId": craft_id} for craft_id in craft_ids]
        await session.execute(insert(FieldRecordingCraft), rows)
