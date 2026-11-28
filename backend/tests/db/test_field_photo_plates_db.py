import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Craft, PagePreview, User
from app.research.page_layout import PageLayout
from app.services.field_photo_plates import cleared_photos, field_key, field_plates
from app.services.field_voices_view import craft_field_photos
from app.services.open_work_subjects import WorkSubject
from app.services.page_preview_links import render_key, signed_token
from app.services.page_preview_pictures import pass_field_photo
from tests.db.field_photo_rows import ITEM, PhotoStore, decided, person, portal_photo, screened, switched
from tests.db.field_voices_rows import KeptStore, ajrakh, rolled_back

pytestmark = pytest.mark.db

NOW = datetime(2026, 11, 28, 9, 0, tzinfo=UTC)


def subject_of(craft: Craft) -> WorkSubject:
    return WorkSubject(craft.id, "craft", craft.slug, craft.name, gi=True)


def placing(subject: WorkSubject, label: str) -> PageLayout:
    entry = {"ref": label, "chapter": "made", "order": 1, "role": "FIGURE"}
    return PageLayout.model_validate(
        {"subjectKind": "craft", "subjectSlug": subject.slug, "version": 9, "entries": [entry]}
    )


async def test_a_published_field_photograph_is_offered_and_drawn_where_the_layout_places_it() -> None:
    async with rolled_back() as session:
        image = await portal_photo(session, KeptStore(), linked=False)
        subject = subject_of(await ajrakh(session))
        shown, _ = await craft_field_photos(session, subject.id, limit=25, offset=0)
        assert ITEM in {photo.item_id for photo in shown}
        photos, total = await cleared_photos(session, subject)
        (photo,) = [each for each in photos if each.image_id == image.id]
        assert total >= 1 and photo.key == field_key(image.id)
        assert photo.src == f"/api/field-voices/images/{image.id}" and photo.credit.startswith("Photo: ")
        (plate,) = await field_plates(session, subject, placing(subject, photo.label))
        assert (plate.chapter, plate.role, plate.src) == ("made", "FIGURE", photo.src)


async def test_a_photograph_a_reviewer_hid_is_not_offered() -> None:
    async with rolled_back() as session:
        photos = PhotoStore()
        image = await portal_photo(session, KeptStore(), linked=False)
        subject = subject_of(await ajrakh(session))
        admin = await person(session, "ADMIN")
        await decided(session, image, admin, photos, decision="HIDE", reason="POOR_QUALITY")
        offered, _ = await cleared_photos(session, subject)
        assert image.id not in {photo.image_id for photo in offered}
        label = f"{subject.slug.lower()}/pictures/{field_key(image.id)}"
        assert await field_plates(session, subject, placing(subject, label)) == []


async def test_an_artisan_s_identity_photograph_is_never_offered_even_shown_on_the_craft_page() -> None:
    async with rolled_back() as session:
        photos = PhotoStore()
        image = await portal_photo(session, KeptStore(), linked=True)
        subject = subject_of(await ajrakh(session))
        offered, _ = await cleared_photos(session, subject)
        assert image.id not in {photo.image_id for photo in offered}
        await switched(session, "SHOWN")
        await screened(session, photos, image)
        await decided(session, image, await person(session, "ADMIN"), photos, decision="SHOW")
        shown, _ = await craft_field_photos(session, subject.id, limit=25, offset=0)
        assert ITEM in {photo.item_id for photo in shown}
        offered, _ = await cleared_photos(session, subject)
        assert image.id not in {photo.image_id for photo in offered}
        label = f"{subject.slug.lower()}/pictures/{field_key(image.id)}"
        assert await field_plates(session, subject, placing(subject, label)) == []


async def drawn_pass(session: AsyncSession, user: User, src: str) -> str:
    row = PagePreview(
        id=uuid.uuid4(),
        userId=user.id,
        subjectKind="craft",
        subjectSlug="Kutch-Ajrakh",
        document={"specs": {"kutch-ajrakh/pictures/field": {"picture": {"src": src}}}},
        expiresAt=NOW + timedelta(hours=1),
        createdAt=NOW - timedelta(minutes=1),
    )
    session.add(row)
    await session.flush()
    return signed_token(row.id, user.id, NOW + timedelta(minutes=2), render_key())


async def test_the_renderer_reads_a_placed_field_photograph_through_its_pass_until_a_reviewer_hides_it() -> (
    None
):
    async with rolled_back() as session:
        photos = PhotoStore()
        image = await portal_photo(session, KeptStore(), linked=False)
        subject = subject_of(await ajrakh(session))
        (photo,) = [each for each in (await cleared_photos(session, subject))[0] if each.image_id == image.id]
        render_pass = await drawn_pass(session, await person(session, "RESEARCHER"), photo.src)
        found = await pass_field_photo(session, render_pass, image.id, now=NOW)
        assert found is not None and (found.key, found.mime) == (image.objectKey, image.mimeType)
        assert await pass_field_photo(session, render_pass, uuid.uuid4(), now=NOW) is None
        assert await pass_field_photo(session, render_pass, image.id, now=NOW + timedelta(minutes=3)) is None
        await decided(
            session, image, await person(session, "ADMIN"), photos, decision="HIDE", reason="POOR_QUALITY"
        )
        assert await pass_field_photo(session, render_pass, image.id, now=NOW) is None
