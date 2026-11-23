import copy
import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Claim, ClaimSource, Concept, Craft, FieldImage, MediaRef, MediaRefClaim
from app.services.craft_page_records import craft_page_records
from app.services.field_voices_illustrations import link_photo_claims
from app.services.media_ref_store import stored_pictures
from tests.db.field_voices_rows import (
    KeptStore,
    ajrakh,
    count,
    gone_page,
    ledger_for,
    page_of,
    public_chunk,
    rolled_back,
    stored_recording,
    synced,
)
from tests.field_voices.fixtures import FR, recorded, resigned

pytestmark = pytest.mark.db

QUOTE = "We grind the alum with tamarind seed"
INVENTED_WORDS = "Zubrin quellate"
NAMES_BOTH = "Zubrin quellate paste is pressed on the cloth."
NAMES_ONE = "Zubrin bark is boiled for the dye."
NAMES_THE_CAPTION = "The first resist is printed again on the Ajrakh stole."


async def stated(session: AsyncSession, craft: Craft, text: str) -> uuid.UUID:
    source_id = (await stored_recording(session)).sourceId
    concept = Concept(craftId=craft.id, type="PROCESS_STAGE", name=f"Illustrated {uuid.uuid4().hex[:8]}")
    session.add(concept)
    await session.flush()
    claim = Claim(
        subjectType="CONCEPT",
        subjectId=concept.id,
        predicate="states",
        text=text,
        evidenceLevel="PROVISIONAL",
        origin="LIVE_RESEARCH",
        status="APPROVED",
    )
    session.add(claim)
    await session.flush()
    chunk = await public_chunk(session, source_id, QUOTE)
    session.add(
        ClaimSource(
            claimId=claim.id,
            sourceId=source_id,
            chunkId=chunk.id,
            locator=chunk.locator,
            quote=QUOTE,
            quoteCheck="PASS",
            relation="DIRECT",
        )
    )
    await session.flush()
    return claim.id


async def photographed(session: AsyncSession) -> tuple[Craft, FieldImage, uuid.UUID]:
    image = await session.scalar(
        select(FieldImage)
        .where(FieldImage.portalMediaId == "fr-img-1")
        .execution_options(populate_existing=True)
    )
    assert image is not None and image.mediaRefId is not None
    return await ajrakh(session), image, image.mediaRefId


async def links(session: AsyncSession, media_id: uuid.UUID) -> set[tuple[uuid.UUID, str]]:
    rows = await session.execute(
        select(MediaRefClaim.claimId, MediaRefClaim.relevance).where(MediaRefClaim.mediaRefId == media_id)
    )
    return {(row.claimId, row.relevance) for row in rows}


async def test_a_field_image_illustrates_the_claim_of_its_craft_that_its_words_name_twice() -> None:
    async with rolled_back() as session:
        await synced(session, KeptStore())
        craft, _image, media = await photographed(session)
        both = await stated(session, craft, NAMES_BOTH)
        one = await stated(session, craft, NAMES_ONE)
        chosen = await link_photo_claims(session, media, described=INVENTED_WORDS, craft_ids=[craft.id])
        assert chosen == (both,)
        assert await links(session, media) == {(both, "TEXT")}
        found = await stored_pictures(session, [one, both])
        assert [(picture.media.id, picture.claim_id) for picture in found] == [(media, both)]


async def test_a_held_artisan_photograph_is_linked_but_never_shown_beside_a_sentence() -> None:
    async with rolled_back() as session:
        await synced(session, KeptStore())
        craft, image, media = await photographed(session)
        both = await stated(session, craft, NAMES_BOTH)
        image.artisanLinked = True
        await session.flush()
        await link_photo_claims(session, media, described=INVENTED_WORDS, craft_ids=[craft.id])
        assert await links(session, media) == {(both, "TEXT")}
        assert await stored_pictures(session, [both]) == []
        image.artisanLinked = False
        await session.flush()
        assert [picture.claim_id for picture in await stored_pictures(session, [both])] == [both]


async def test_a_changed_photograph_is_linked_again_from_its_caption_and_labels() -> None:
    async with rolled_back() as session:
        store = KeptStore()
        await synced(session, store)
        craft, _image, media = await photographed(session)
        named = await stated(session, craft, NAMES_THE_CAPTION)
        change = copy.deepcopy(recorded("field-images-all-1")["changes"][0])
        change["caption"] = "Printing the first resist again"
        resigned(change)
        change["updatedAt"] = "2026-11-18T02:59:00.000001Z"
        change["image"]["expiresAt"] = "2026-11-18T03:10:00Z"
        await ledger_for(session, store).apply_page(page_of("images", "all", "fr-i-1", [change]), {})
        assert (named, "TEXT") in await links(session, media)


async def test_withdrawing_a_photograph_deletes_its_media_and_every_claim_it_illustrated() -> None:
    async with rolled_back() as session:
        store = KeptStore()
        await synced(session, store)
        craft, _image, media = await photographed(session)
        both = await stated(session, craft, NAMES_BOTH)
        await link_photo_claims(session, media, described=INVENTED_WORDS, craft_ids=[craft.id])
        await ledger_for(session, store).apply_page(await gone_page(session, "images", "fr-img-1"), {})
        assert await count(session, MediaRefClaim, MediaRefClaim.mediaRefId == media) == 0
        assert await count(session, MediaRef, MediaRef.id == media) == 0
        assert await count(session, Claim, Claim.id == both) == 1


async def test_a_photograph_illustrating_a_claim_stays_in_the_gallery_not_among_the_page_s_pictures() -> None:
    async with rolled_back() as session:
        await synced(session, KeptStore())
        craft, _image, media = await photographed(session)
        both = await stated(session, craft, NAMES_BOTH)
        await link_photo_claims(session, media, described=INVENTED_WORDS, craft_ids=[craft.id])
        records = await craft_page_records(session, craft)
        assert both in {view.id for view in records.views}
        assert media not in {picture.media.id for picture in records.pictures}
        assert f"{FR}:fr-img-1" in {photo.item_id for photo in records.field_voices.photos}
