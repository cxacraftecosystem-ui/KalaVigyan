from datetime import UTC, datetime

import pytest
from sqlalchemy import select

from app.models import FieldImage, FieldPhotoReview
from app.services.craft_page_stamp import page_stamp
from app.services.field_photo_crops import sweep_withdrawn_reviews
from app.services.field_photo_queue import photo_queue
from app.services.field_photo_scope import served_photo
from app.services.field_voices_reading import field_list, shown_image
from tests.db.field_photo_rows import (
    ITEM,
    PhotoStore,
    decided,
    held_photo,
    person,
    photo_ids,
    same_session,
    screened,
    switched,
)
from tests.db.field_voices_rows import KeptStore, ajrakh, count, gone_page, ledger_for, rolled_back

pytestmark = pytest.mark.db

NOW = datetime(2026, 11, 21, 9, 0, tzinfo=UTC)
CROP = {"left": 400, "top": 200, "width": 1200, "height": 900}


async def test_a_held_photograph_stays_hidden_until_its_own_decision_shows_it() -> None:
    async with rolled_back() as session:
        photos = PhotoStore()
        image = await held_photo(session, KeptStore())
        craft = await ajrakh(session)
        await switched(session, "SHOWN")
        assert ITEM not in await photo_ids(session, craft.id)
        assert await served_photo(session, image.id) is None
        assert await shown_image(session, image.id) is None
        await screened(session, photos, image)
        assert ITEM not in await photo_ids(session, craft.id)
        await decided(session, image, await person(session, "ADMIN"), photos, decision="SHOW")
        assert ITEM in await photo_ids(session, craft.id)
        served = await served_photo(session, image.id)
        assert served is not None and served.key == image.objectKey
        listed = await field_list(session, craft, kind="images", cursor=None)
        assert ITEM in {photo.item_id for photo in listed.images}


async def test_the_master_switch_off_hides_every_reviewed_photograph_and_on_shows_only_those() -> None:
    async with rolled_back() as session:
        photos = PhotoStore()
        image = await held_photo(session, KeptStore())
        craft = await ajrakh(session)
        await screened(session, photos, image)
        await decided(session, image, await person(session, "ADMIN"), photos, decision="SHOW")
        await switched(session, "HIDDEN")
        assert ITEM not in await photo_ids(session, craft.id)
        assert await served_photo(session, image.id) is None
        await switched(session, "SHOWN")
        assert ITEM in await photo_ids(session, craft.id)
        assert await served_photo(session, image.id) is not None


async def test_a_photograph_hidden_again_leaves_every_page_at_once() -> None:
    async with rolled_back() as session:
        photos = PhotoStore()
        image = await held_photo(session, KeptStore())
        craft = await ajrakh(session)
        admin = await person(session, "ADMIN")
        await switched(session, "SHOWN")
        await screened(session, photos, image)
        await decided(session, image, admin, photos, decision="SHOW")
        assert ITEM in await photo_ids(session, craft.id)
        await decided(session, image, admin, photos, decision="HIDE", reason="PRIVATE_PLACE")
        assert ITEM not in await photo_ids(session, craft.id)
        assert await served_photo(session, image.id) is None
        listed = await field_list(session, craft, kind="images", cursor=None)
        assert ITEM not in {photo.item_id for photo in listed.images}
        queue = await photo_queue(session, state="HIDDEN", cursor=None, objects=photos, now=NOW)
        (item,) = [each for each in queue.items if each.item_id == ITEM]
        assert item.decision is not None and (item.decision.reason, item.state) == ("PRIVATE_PLACE", "HIDDEN")
        assert [entry.decision for entry in item.history] == ["HIDE", "SHOW"]


async def test_a_withdrawal_wins_over_a_decision_and_takes_its_crop_with_it() -> None:
    async with rolled_back() as session:
        photos, store = PhotoStore(), KeptStore()
        image = await held_photo(session, store)
        master = await person(session, "MASTER_ADMIN")
        await switched(session, "SHOWN")
        await screened(session, photos, image)
        made = await decided(session, image, master, photos, decision="CROP", crop=CROP)
        assert made.made_key is not None and made.made_key in photos.objects
        await ledger_for(session, store).apply_page(await gone_page(session, "images", "fr-img-1"), {})
        assert await count(session, FieldImage, FieldImage.id == image.id) == 0
        assert await served_photo(session, image.id) is None
        orphaned = await session.scalar(
            select(FieldPhotoReview)
            .where(FieldPhotoReview.cropKey == made.made_key)
            .execution_options(populate_existing=True)
        )
        assert orphaned is not None and orphaned.imageId is None
        assert await sweep_withdrawn_reviews(same_session(session), photos) == 1
        assert await count(session, FieldPhotoReview, FieldPhotoReview.cropKey == made.made_key) == 0
        assert made.made_key in photos.deleted and made.made_key not in photos.objects


async def test_each_decision_moves_the_craft_page_stamp() -> None:
    async with rolled_back() as session:
        photos = PhotoStore()
        image = await held_photo(session, KeptStore())
        craft = await ajrakh(session)
        admin = await person(session, "ADMIN")
        await screened(session, photos, image)
        before = await page_stamp(session, craft, "OPEN")
        await decided(session, image, admin, photos, decision="SHOW")
        shown = await page_stamp(session, craft, "OPEN")
        assert shown != before
        await decided(session, image, admin, photos, decision="HIDE", reason="POOR_QUALITY")
        assert await page_stamp(session, craft, "OPEN") not in {before, shown}
