import uuid
from typing import Any

import pytest
from sqlalchemy import select

from app.models import (
    Chunk,
    FieldImage,
    FieldPhotoReview,
    FieldRecording,
    FieldRecordingCraft,
    FieldSegment,
    MediaRef,
    Source,
)
from app.research.retrieval import OPEN_CHUNK_ACLS, SIGNED_IN_CHUNK_ACLS
from app.retrieval.statements import CraftScope, chunk_conditions
from app.services.field_voices_held import held_image_list, set_artisan_image_visibility
from app.services.field_voices_reader import field_voices_reader
from app.services.field_voices_reading import field_transcript, shown_image
from app.services.field_voices_store import field_recording_id
from app.services.field_voices_sync import sync_portal
from app.services.field_voices_view import craft_field_photos, voices_part
from tests.db.field_voices_rows import (
    API,
    WEB,
    KeptStore,
    ajrakh,
    count,
    gone_page,
    ledger_for,
    rolled_back,
    synced,
)
from tests.field_voices.fakes import FakeClock, FakeCopier
from tests.field_voices.fixtures import (
    FR,
    STATE,
    caught_up,
    enabled_settings,
    portal_transport,
    reference_digest,
    resigned,
)

pytestmark = pytest.mark.db


async def test_a_recording_is_stored_as_a_cited_field_interview_with_quote_and_signed_in_chunks() -> None:
    async with rolled_back() as session:
        report = await synced(session, KeptStore())
        assert report["ok"], report
        recording = await session.scalar(
            select(FieldRecording).where(FieldRecording.portalMediaId == "fr-media-1")
        )
        assert recording is not None and recording.id == field_recording_id(FR, "fr-media-1")
        source = await session.get(Source, recording.sourceId)
        assert source is not None
        assert (source.kind, source.reliability, source.sensitivity) == (
            "FIELD_TESTIMONY",
            "A",
            "ATTRIBUTE_REQUIRED",
        )
        assert (source.evidenceKind, source.publisher) == ("FIELD_INTERVIEW", "Field Repository")
        assert source.url == f"{WEB}/voices/{recording.id}"
        acls = set((await session.scalars(select(Chunk.acl).where(Chunk.sourceId == source.id))).all())
        assert acls == {"PUBLIC", "SIGNED_IN"}
        sensitivities = set(
            (await session.scalars(select(Chunk.sensitivity).where(Chunk.sourceId == source.id))).all()
        )
        assert sensitivities == {"ATTRIBUTE_REQUIRED"}
        craft = await ajrakh(session)
        assert await count(session, FieldRecordingCraft, FieldRecordingCraft.recordingId == recording.id) == 1
        assert await count(session, FieldRecordingCraft, FieldRecordingCraft.craftId == craft.id) >= 1
        assert await count(session, FieldSegment, FieldSegment.recordingId == recording.id) >= 1


async def test_a_second_run_changes_nothing() -> None:
    async with rolled_back() as session:
        await synced(session, KeptStore())
        chunks = sorted(
            map(
                str,
                (
                    await session.scalars(
                        select(Chunk.id).join(Source).where(Source.kind == "FIELD_TESTIMONY")
                    )
                ).all(),
            )
        )
        again = await synced(session, KeptStore())
        assert again["ok"], again
        assert all(stream["liveApplied"] == 0 for stream in again["streams"]), again
        kept = sorted(
            map(
                str,
                (
                    await session.scalars(
                        select(Chunk.id).join(Source).where(Source.kind == "FIELD_TESTIMONY")
                    )
                ).all(),
            )
        )
        assert kept == chunks


async def test_anonymous_retrieval_reads_quotes_only_and_a_signed_in_reader_reads_the_transcript() -> None:
    async with rolled_back() as session:
        await synced(session, KeptStore())
        craft = await ajrakh(session)
        scope = CraftScope(craft_id=craft.id, sub_category_id=craft.subCategoryId)

        async def readable(acls: tuple[str, ...]) -> set[str]:
            conditions = chunk_conditions(scope, mode="HYBRID", acls=acls)
            rows = await session.scalars(
                select(Chunk.acl).join(Source).where(*conditions, Source.kind == "FIELD_TESTIMONY")
            )
            return set(rows.all())

        assert await readable(OPEN_CHUNK_ACLS) == {"PUBLIC"}
        assert await readable(SIGNED_IN_CHUNK_ACLS) == {"PUBLIC", "SIGNED_IN"}


async def test_the_craft_page_shows_the_quotes_and_photographs_and_the_reading_view_the_whole_transcript() -> (
    None
):
    async with rolled_back() as session:
        await synced(session, KeptStore())
        craft = await ajrakh(session)
        part = await voices_part(session, craft.id, voices=6, photos=12)
        assert part.voices and part.photos
        assert part.totals.quotes >= len(part.voices) and part.totals.images >= len(part.photos)
        voice = part.voices[0]
        assert voice.origin == FR and voice.source_id in part.sources
        assert voice.recording_id is not None
        photo = part.photos[0]
        assert photo.image_url.startswith(f"{API}/api/field-voices/images/")
        assert photo.licence is None
        transcript = await field_transcript(session, voice.recording_id)
        assert transcript is not None and transcript.lines
        assert transcript.publisher == "Field Repository"


async def test_a_photograph_becomes_credited_media_with_its_stored_copy() -> None:
    async with rolled_back() as session:
        await synced(session, KeptStore())
        image = await session.scalar(select(FieldImage).where(FieldImage.portalMediaId == "fr-img-1"))
        assert image is not None and image.mediaRefId is not None
        media = await session.get(MediaRef, image.mediaRefId)
        assert media is not None
        assert (media.provider, media.display, media.licence) == ("field_repository", "INLINE", None)
        assert media.objectKey == image.objectKey
        assert media.credit and media.author


async def test_a_tombstone_withdraws_the_recording_its_source_and_its_chunks() -> None:
    async with rolled_back() as session:
        store = KeptStore()
        await synced(session, store)
        recording = await session.scalar(
            select(FieldRecording).where(FieldRecording.portalMediaId == "fr-media-1")
        )
        assert recording is not None
        source_id = recording.sourceId
        ledger = ledger_for(session, store)
        applied = await ledger.apply_page(await gone_page(session, "transcripts", "fr-media-1"), {})
        assert applied.gone == 1
        assert await session.get(FieldRecording, recording.id, populate_existing=True) is None
        assert await count(session, Source, Source.id == source_id) == 0
        assert await count(session, Chunk, Chunk.sourceId == source_id) == 0
        assert await count(session, FieldSegment, FieldSegment.recordingId == recording.id) == 0


async def test_a_tombstone_withdraws_the_photograph_its_media_and_its_copy() -> None:
    async with rolled_back() as session:
        store = KeptStore()
        await synced(session, store)
        image = await session.scalar(select(FieldImage).where(FieldImage.portalMediaId == "fr-img-1"))
        assert image is not None
        key, media_id = image.objectKey, image.mediaRefId
        ledger = ledger_for(session, store)
        await ledger.apply_page(await gone_page(session, "images", "fr-img-1"), {})
        assert await count(session, FieldImage, FieldImage.portalMediaId == "fr-img-1") == 0
        assert await count(session, MediaRef, MediaRef.id == media_id) == 0
        assert store.deleted == [key]


async def test_an_unknown_recording_has_no_reading_view() -> None:
    async with rolled_back() as session:
        assert await field_transcript(session, uuid.uuid4()) is None


async def synced_artisan_linked(session: Any, store: KeptStore) -> dict[str, Any]:
    answers = caught_up(FR)
    page = answers[(f"{STATE}/images", "all", None)]
    page["changes"][0]["artisanLinked"] = True
    resigned(page["changes"][0])
    live = [(c["id"], c["revision"]) for c in page["changes"] if c["state"] == "LIVE"]
    answers[(STATE, None, None)]["streams"]["images"]["digest"] = reference_digest(live)
    reader = field_voices_reader(enabled_settings(), FR, transport=portal_transport(answers))
    report = await sync_portal(reader, ledger_for(session, store), FakeCopier(), clock=FakeClock().clock())
    return report.as_dict()


async def photo_ids(session: Any, craft_id: uuid.UUID) -> set[str]:
    listed, _total = await craft_field_photos(session, craft_id, limit=25, offset=0)
    part = await voices_part(session, craft_id, voices=6, photos=12)
    return {photo.item_id for photo in listed} | {photo.item_id for photo in part.photos}


async def test_an_artisan_linked_photograph_is_held_hidden_listed_for_admins_and_shown_only_when_reviewed() -> (
    None
):
    async with rolled_back() as session:
        report = await synced_artisan_linked(session, KeptStore())
        assert report["ok"], report
        image = await session.scalar(select(FieldImage).where(FieldImage.portalMediaId == "fr-img-1"))
        assert image is not None and image.artisanLinked is True
        assert image.objectKey and image.mediaRefId is not None
        craft = await ajrakh(session)
        item = f"{FR}:fr-img-1"
        assert item not in await photo_ids(session, craft.id)
        assert await shown_image(session, image.id) is None
        held = await held_image_list(session, cursor=None)
        assert held.visibility == "HIDDEN" and item in {each.item_id for each in held.images}
        await set_artisan_image_visibility(session, "SHOWN", actor_id=None)
        await session.flush()
        assert await shown_image(session, image.id) is None
        assert item not in await photo_ids(session, craft.id)
        session.add(
            FieldPhotoReview(imageId=image.id, imageSha256=image.sha256, decision="SHOW", deciderRole="ADMIN")
        )
        await session.flush()
        assert await shown_image(session, image.id) is not None
        assert item in await photo_ids(session, craft.id)
        await set_artisan_image_visibility(session, "HIDDEN", actor_id=None)
        await session.flush()
        assert await shown_image(session, image.id) is None
