import json
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    Chunk,
    Claim,
    ClaimSource,
    Concept,
    Craft,
    FieldImage,
    FieldRecording,
    FieldVoiceStream,
    Source,
)
from app.research.explainer import Explainer
from app.research.retrieval import EVERY_CHUNK_KINDS, OPEN_CHUNK_ACLS
from app.retrieval.statements import CraftScope, chunk_conditions
from app.services.field_voices_items import FeedPerson
from app.services.field_voices_ledger import rekey_people, rekeyed
from app.services.field_voices_readback import Withdrawn, current_field_voices, field_withdrawals
from app.services.field_voices_reading import field_transcript, shown_image
from app.services.field_voices_view import craft_field_photos, craft_voices, voices_part
from app.services.knowledge_view import claims_by_id, claims_for
from tests.contracts.golden import golden_json
from tests.db.field_voices_rows import (
    KeptStore,
    ajrakh,
    cited_claim,
    count,
    gone_page,
    ledger_for,
    page_of,
    recorded_recording,
    rolled_back,
    stored_recording,
    synced,
)
from tests.field_voices.fixtures import FR

pytestmark = pytest.mark.db

KEPT_QUOTE = "We grind the alum with tamarind seed"
CUT_QUOTE = "the paste must rest overnight"
ASKED = "How do you prepare the mordant"
EDITED_ENGLISH = "We grind the alum with tamarind seed. Call me on [number]."
STALE = timedelta(days=8)
INTERVIEW = "907e2c52-14e7-5e41-9b27-9c10f70906a9"
LONG_TURNS = 60
PAGE = 25


async def visible_claims(session: AsyncSession, craft: Craft) -> set[uuid.UUID]:
    views, _ = await claims_for(session, craft, mode="HYBRID")
    return {view.id for view in views}


async def field_chunks(session: AsyncSession, craft: Craft) -> set[uuid.UUID]:
    scope = CraftScope(craft_id=craft.id, sub_category_id=craft.subCategoryId)
    conditions = chunk_conditions(scope, mode="HYBRID", acls=OPEN_CHUNK_ACLS, kinds=EVERY_CHUNK_KINDS)
    rows = await session.scalars(
        select(Chunk.id).join(Source).where(*conditions, Source.kind == "FIELD_TESTIMONY")
    )
    return set(rows.all())


async def aged(session: AsyncSession, stream: str) -> None:
    row = await session.get(FieldVoiceStream, (FR, stream), populate_existing=True)
    assert row is not None
    row.lastContactAt = datetime.now(UTC) - STALE
    await session.flush()


async def quoted(session: AsyncSession, quote: str = KEPT_QUOTE) -> tuple[Craft, FieldRecording, uuid.UUID]:
    craft = await ajrakh(session)
    recording = await stored_recording(session)
    return craft, recording, await cited_claim(session, craft, recording.sourceId, quote)


async def test_an_eight_day_old_contact_hides_the_write_back_claim_and_every_field_chunk() -> None:
    async with rolled_back() as session:
        await synced(session, KeptStore())
        craft, recording, claim = await quoted(session)
        assert claim in await visible_claims(session, craft)
        assert await field_chunks(session, craft)
        await aged(session, "TRANSCRIPTS")
        assert claim not in await visible_claims(session, craft)
        assert await field_chunks(session, craft) == set()
        assert (await claims_by_id(session, [claim]))[0] == {}
        assert await field_transcript(session, recording.id) is None
        part = await voices_part(session, craft.id, voices=6, photos=12)
        assert not [voice for voice in part.voices if voice.origin == FR]


async def test_an_eight_day_old_image_stream_hides_the_gallery_and_the_image_route() -> None:
    async with rolled_back() as session:
        await synced(session, KeptStore())
        craft = await ajrakh(session)
        image = await session.scalar(select(FieldImage).where(FieldImage.portalMediaId == "fr-img-1"))
        assert image is not None and await shown_image(session, image.id) is not None
        await aged(session, "IMAGES")
        assert await shown_image(session, image.id) is None
        assert await craft_field_photos(session, craft.id, limit=PAGE, offset=0) == ([], 0)


async def test_a_hidden_stream_serves_nothing_and_hides_the_claims_it_supports() -> None:
    async with rolled_back() as session:
        store = KeptStore()
        await synced(session, store)
        craft, recording, claim = await quoted(session)
        image = await session.scalar(select(FieldImage).where(FieldImage.portalMediaId == "fr-img-1"))
        assert image is not None
        ledger = ledger_for(session, store)
        await ledger.hide(FR, "transcripts")
        await ledger.hide(FR, "images")
        part = await voices_part(session, craft.id, voices=6, photos=12)
        assert not [voice for voice in part.voices if voice.origin == FR] and part.photos == ()
        assert await field_transcript(session, recording.id) is None
        assert await shown_image(session, image.id) is None
        assert claim not in await visible_claims(session, craft)
        assert await field_chunks(session, craft) == set()


async def test_a_tombstone_deletes_the_write_back_claim_that_cited_only_the_recording() -> None:
    async with rolled_back() as session:
        store = KeptStore()
        await synced(session, store)
        _craft, recording, claim = await quoted(session)
        await ledger_for(session, store).apply_page(await gone_page(session, "transcripts", "fr-media-1"), {})
        assert await count(session, Claim, Claim.id == claim) == 0
        assert await count(session, ClaimSource, ClaimSource.sourceId == recording.sourceId) == 0


async def test_an_edited_turn_drops_the_claim_its_edit_removed_and_repoints_the_one_it_kept() -> None:
    async with rolled_back() as session:
        store = KeptStore()
        await synced(session, store)
        craft, recording, kept = await quoted(session)
        cut = await cited_claim(session, craft, recording.sourceId, CUT_QUOTE)
        before = set(await session.scalars(select(Chunk.id).where(Chunk.sourceId == recording.sourceId)))

        def edited(change: dict[str, Any]) -> None:
            change["transcript"]["segments"][1]["english"] = EDITED_ENGLISH

        page = page_of("transcripts", "all", "fr-t-3", [recorded_recording(edited)])
        assert (await ledger_for(session, store).apply_page(page, {})).live == 1
        after = set(await session.scalars(select(Chunk.id).where(Chunk.sourceId == recording.sourceId)))
        assert after and before.isdisjoint(after)
        assert await count(session, Claim, Claim.id == cut) == 0
        assert await count(session, Claim, Claim.id == kept) == 1
        cite = await session.scalar(
            select(ClaimSource).where(ClaimSource.claimId == kept).execution_options(populate_existing=True)
        )
        assert cite is not None and cite.chunkId in after
        chunk = await session.get(Chunk, cite.chunkId)
        assert (
            chunk is not None
            and (chunk.acl, chunk.kind) == ("PUBLIC", "PASSAGE")
            and KEPT_QUOTE in chunk.text
        )


async def test_an_edit_drops_a_claim_whose_words_only_a_transcript_window_holds() -> None:
    async with rolled_back() as session:
        store = KeptStore()
        await synced(session, store)
        craft, recording, kept = await quoted(session)
        windowed = await window_cited_claim(session, craft, recording.sourceId, ASKED)

        def edited(change: dict[str, Any]) -> None:
            change["transcript"]["segments"][1]["english"] = EDITED_ENGLISH

        page = page_of("transcripts", "all", "fr-t-3", [recorded_recording(edited)])
        assert (await ledger_for(session, store).apply_page(page, {})).live == 1
        windows = await session.scalars(
            select(Chunk.text).where(Chunk.sourceId == recording.sourceId, Chunk.kind == "WINDOW")
        )
        assert any(ASKED in text for text in windows.all())
        assert await count(session, Claim, Claim.id == windowed) == 0
        assert await count(session, Claim, Claim.id == kept) == 1


async def window_cited_claim(
    session: AsyncSession, craft: Craft, source_id: uuid.UUID, quote: str
) -> uuid.UUID:
    rows = await session.scalars(
        select(Chunk).where(Chunk.sourceId == source_id, Chunk.kind == "WINDOW").order_by(Chunk.ordinal)
    )
    window = next(chunk for chunk in rows if quote in chunk.text)
    assert window.acl == "PUBLIC"
    concept = Concept(craftId=craft.id, type="PROCESS_STAGE", name="Mordant question")
    session.add(concept)
    await session.flush()
    claim = Claim(
        subjectType="CONCEPT",
        subjectId=concept.id,
        predicate="states",
        text=f"The researcher asks: {quote}.",
        evidenceLevel="PROVISIONAL",
        origin="LIVE_RESEARCH",
        status="APPROVED",
    )
    session.add(claim)
    await session.flush()
    session.add(
        ClaimSource(
            claimId=claim.id,
            sourceId=source_id,
            chunkId=window.id,
            locator=window.locator,
            quote=quote,
            quoteCheck="PASS",
            relation="DIRECT",
        )
    )
    await session.flush()
    return claim.id


def long_recording(change: dict[str, Any]) -> None:
    change.update(id="fr-media-long", recordingId=None)
    change["transcript"].update(languages=["en"], detectedLanguage="en")
    change["transcript"]["segments"] = [
        {
            "id": f"fr-long-{(position * 37) % 61:02d}",
            "position": position,
            "speakerKey": "speaker_0",
            "startMs": None,
            "endMs": None,
            "language": "en",
            "text": f"Turn {position:02d}: we press the block twice so the resist line stays even.",
            "textSource": "EDITED",
            "english": None,
            "englishSource": None,
            "scrubbed": [],
        }
        for position in range(LONG_TURNS)
    ]


async def test_show_all_lists_every_quote_of_a_long_recording_exactly_once() -> None:
    async with rolled_back() as session:
        store = KeptStore()
        await synced(session, store)
        page = page_of("transcripts", "all", "fr-t-3", [recorded_recording(long_recording)])
        await ledger_for(session, store).apply_page(page, {})
        craft = await ajrakh(session)
        _first, total = await craft_voices(session, craft.id, limit=PAGE, offset=0)
        seen = [
            voice.item_id
            for offset in range(0, total, PAGE)
            for voice in (await craft_voices(session, craft.id, limit=PAGE, offset=offset))[0]
        ]
        assert len(seen) == len(set(seen)) == total
        expected = {
            f"{FR}:fr-media-long:fr-long-{(position * 37) % 61:02d}" for position in range(LONG_TURNS)
        }
        assert expected <= set(seen)


async def test_a_merged_artisan_is_rekeyed_in_speakers_and_photo_credits() -> None:
    async with rolled_back() as session:
        await synced(session, KeptStore())
        recording = await stored_recording(session)
        recording.people = rekeyed(recording.people, "id", "fr-art-1", "fr-art-old")
        recording.speakers = rekeyed(recording.speakers, "personId", "fr-art-1", "fr-art-old")
        image = await session.scalar(select(FieldImage).where(FieldImage.portalMediaId == "fr-img-1"))
        assert image is not None
        image.people = rekeyed(image.people, "id", "fr-art-1", "fr-art-old")
        image.credits = rekeyed(image.credits, "personId", "fr-art-1", "fr-art-old")
        await session.flush()
        survivor = FeedPerson(id="fr-art-1", kind="ARTISAN", name="Asha Demo", merged_ids=("fr-art-old",))
        await rekey_people(session, FieldRecording, FR, survivor)
        await rekey_people(session, FieldImage, FR, survivor)
        await session.flush()
        recording = await stored_recording(session)
        assert [s["personId"] for s in recording.speakers if s["key"] == "speaker_0"] == ["fr-art-1"]
        await session.refresh(image)
        assert [credit["personId"] for credit in image.credits] == ["fr-art-1"]
        transcript = await field_transcript(session, recording.id)
        assert transcript is not None
        assert [s.label for s in transcript.speakers if s.key == "speaker_0"] == ["Asha Demo"]


def explainer_citing(source_id: str, claim_id: uuid.UUID) -> Explainer:
    document = golden_json("explainer.document.golden.json")
    sentence = next(
        each
        for section in document["sections"]
        for block in section["blocks"]
        for each in block.get("sentences", [])
        if each["id"] == "s2.b1.3"
    )
    text = json.dumps(document).replace(sentence["citations"][0]["claimId"], str(claim_id))
    document = json.loads(text.replace(INTERVIEW, source_id))
    for source in document["sources"]:
        if source["id"] == source_id:
            source.update(kind="FIELD_TESTIMONY", publisher="Field Repository", authors=["Asha Demo"])
    return Explainer.model_validate(document)


async def test_a_stored_explainer_drops_the_sentence_that_quoted_a_withdrawn_interview() -> None:
    async with rolled_back() as session:
        store = KeptStore()
        await synced(session, store)
        _craft, recording, claim = await quoted(session)
        source_id = str(recording.sourceId)
        stored = explainer_citing(source_id, claim)
        assert await field_withdrawals(session, stored) == Withdrawn()
        assert await current_field_voices(session, stored) is stored
        await ledger_for(session, store).apply_page(await gone_page(session, "transcripts", "fr-media-1"), {})
        withdrawn = await field_withdrawals(session, stored)
        assert source_id in withdrawn.sources
        shown = await current_field_voices(session, stored)
        assert shown is not None
        assert source_id not in {source.id for source in shown.sources}
        assert "Asha Demo" not in shown.model_dump_json()
