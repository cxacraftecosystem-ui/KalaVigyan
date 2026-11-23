import uuid
from datetime import datetime

from app.models import FieldImage, FieldRecording, FieldSegment, Source
from app.research.citations import SourceRef
from app.research.craft_page import CraftPage
from app.research.field_voices import FieldVoicesTotals, PageFieldPhoto, PageVoice, PhotoGroup, VoiceStage
from app.research.voices import VoiceSpeaker
from app.services.chapter_inputs import InputFieldVoices, chapter_inputs
from app.services.chapter_preview import PREVIEW_SITE
from app.services.field_voices_feed import Live, parse_page
from app.services.field_voices_image_store import _image_values, field_image_id, image_route_url
from app.services.field_voices_images import StoredCopy
from app.services.field_voices_items import ImageItem, TranscriptItem
from app.services.field_voices_photos import photo_plan
from app.services.field_voices_records import RecordingPlan, recording_plan, source_values
from app.services.field_voices_store import (
    ApplyContext,
    ResolvedCrafts,
    _recording_values,
    field_recording_id,
    field_segment_id,
    field_source_id,
    reading_url,
)
from app.services.field_voices_view import _photo, field_voice
from app.services.knowledge_view import source_ref

from ..curation.import_support import AJRAKH, AJRAKH_GOLDEN
from ..field_voices.fixtures import FR, recorded
from .golden import SHARED, golden_json
from .golden_fields import field_keys, shown_fields

INPUTS = "craft.page.inputs.json"
TRANSCRIPT_PAGES = ("field-transcripts-all-1", "field-transcripts-all-2")
IMAGE_PAGES = ("field-images-all-1",)
NO_CRAFTS = ResolvedCrafts(craft_ids=(), unresolved=())
SHOWN_MODELS = (PageVoice, VoiceStage, VoiceSpeaker, PageFieldPhoto, PhotoGroup)


def ajrakh_changes(name: str) -> list[tuple[Live, datetime]]:
    body = recorded(name)
    page = parse_page(body, portal=FR, asked=(body["stream"], body["view"], body["cursor"]))
    return [
        (change, page.generated_at)
        for change in page.changes
        if isinstance(change, Live) and any(craft.slug == AJRAKH for craft in change.item.crafts)
    ]


def segment_rows(recording_id: uuid.UUID, plan: RecordingPlan) -> list[FieldSegment]:
    return [
        FieldSegment(
            id=field_segment_id(recording_id, segment.portal_segment_id),
            recordingId=recording_id,
            portalSegmentId=segment.portal_segment_id,
            position=segment.position,
            speakerKey=segment.speaker_key,
            personId=segment.person_id,
            role=segment.role,
            startMs=segment.start_ms,
            endMs=segment.end_ms,
            language=segment.language,
            text=segment.text,
            textSource=segment.text_source,
            english=segment.english,
            englishSource=segment.english_source,
            quotable=segment.quotable,
        )
        for segment in plan.segments
    ]


def recording_voices(change: Live, read_at: datetime) -> tuple[list[PageVoice], SourceRef]:
    item = change.item
    assert isinstance(item, TranscriptItem)
    plan = recording_plan(item, portal=FR)
    recording_id = field_recording_id(FR, item.id)
    preview = ApplyContext(now=read_at, web_base=PREVIEW_SITE, api_base=PREVIEW_SITE)
    values = source_values(
        plan,
        item,
        portal=FR,
        url=reading_url(preview, recording_id),
        revision=change.revision,
        retrieved_at=read_at,
    )
    source = Source(id=field_source_id(FR, item.id), **values)
    recording = FieldRecording(
        id=recording_id,
        portal=FR,
        portalMediaId=item.id,
        sourceId=source.id,
        **_recording_values(item, plan, NO_CRAFTS),
    )
    rows = [segment for segment in segment_rows(recording_id, plan) if segment.quotable]
    voices = [voice for segment in rows if (voice := field_voice(segment, recording))]
    return voices, SourceRef.model_validate(source_ref(source))


def portal_sized_copy(item: ImageItem) -> StoredCopy:
    image = item.image
    return StoredCopy(
        key=f"media/field-voices/{image.sha256}/copy.jpg",
        mime_type=image.mime_type,
        width=image.width,
        height=image.height,
        bytes=image.bytes,
        sha256=image.sha256,
        portal_sha256=image.sha256,
    )


def image_photo(change: Live) -> PageFieldPhoto:
    item = change.item
    assert isinstance(item, ImageItem)
    copy = portal_sized_copy(item)
    values = _image_values(item, photo_plan(item, portal=FR), copy)
    row = FieldImage(id=field_image_id(FR, item.id), portal=FR, portalMediaId=item.id, **values)
    return _photo(row, image_route_url(PREVIEW_SITE, row.id), (copy.width, copy.height))


def recorded_field_voices() -> InputFieldVoices:
    voices: list[PageVoice] = []
    sources: list[SourceRef] = []
    for change, read_at in [pair for name in TRANSCRIPT_PAGES for pair in ajrakh_changes(name)]:
        quoted, source = recording_voices(change, read_at)
        voices += quoted
        sources += [source] if quoted else []
    photos = [image_photo(change) for name in IMAGE_PAGES for change, _ in ajrakh_changes(name)]
    totals = FieldVoicesTotals(quotes=len(voices), images=len(photos))
    return InputFieldVoices(voices=voices, photos=photos, totals=totals, sources=sources)


def test_the_inputs_field_voices_are_the_recorded_kutch_ajrakh_feed_items_as_the_app_stores_them() -> None:
    held = chapter_inputs(SHARED / INPUTS).field_voices
    assert held == recorded_field_voices()
    assert [voice.item_id for voice in held.voices] == ["FIELD_REPOSITORY:fr-media-1:fr-turn-2"]
    assert [photo.item_id for photo in held.photos] == ["FIELD_REPOSITORY:fr-img-1"]


def test_the_golden_lists_the_recorded_voice_and_photo_with_the_voice_s_source() -> None:
    held = recorded_field_voices()
    page = golden_json(AJRAKH_GOLDEN)
    assert page["voices"] == [voice.model_dump(mode="json", by_alias=True) for voice in held.voices]
    assert page["fieldPhotos"] == [photo.model_dump(mode="json", by_alias=True) for photo in held.photos]
    assert page["fieldVoicesTotal"] == held.totals.model_dump(mode="json", by_alias=True)
    listed = {source["id"] for source in page["sources"]}
    assert {source.id for source in held.sources} <= listed


def test_the_golden_shows_every_field_of_a_voice_and_a_field_photo() -> None:
    wanted = {key for model in SHOWN_MODELS for key in field_keys(model)}
    assert wanted <= shown_fields(CraftPage, [AJRAKH_GOLDEN])
