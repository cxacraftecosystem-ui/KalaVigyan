from collections.abc import AsyncIterator, Callable
from datetime import UTC, datetime
from typing import Any

import httpx
import pytest
from sqlalchemy import select

from app.core.db import get_session
from app.main import create_app
from app.models import AuditLog, FieldPhotoScreen, User
from app.research.field_photo_reviews import PhotoDecisionRequest
from app.research.image_screens import FLAG_REASONS
from app.services.field_photo_crops import PhotoRefused
from app.services.field_photo_decisions import CHANGED, decide_photo
from app.services.field_photo_queue import photo_queue
from app.services.field_photo_scope import served_photo
from app.services.field_voices_view import craft_field_photos
from tests.db.field_photo_rows import ITEM, PhotoStore, decided, held_photo, person, screened, switched
from tests.db.field_voices_rows import KeptStore, ajrakh, rolled_back
from tests.pictures import SeenVision
from tests.readers import sign_in_as

pytestmark = pytest.mark.db

NOW = datetime(2026, 11, 21, 9, 0, tzinfo=UTC)
CARD = "A card with a photograph and a twelve-digit number"
CROP = {"left": 600, "top": 300, "width": 1000, "height": 700}


def unnamed(change: dict[str, Any]) -> None:
    for each in change.get("people") or []:
        each["name"] = None
        each["localName"] = None


async def test_the_screens_look_at_each_held_photograph_as_a_photograph_and_record_what_they_found() -> None:
    async with rolled_back() as session:
        photos = PhotoStore()
        image = await held_photo(session, KeptStore())
        vision = SeenVision(flags=("ID_DOCUMENT",), note=CARD)
        report = await screened(session, photos, image, vision)
        assert (report.screened, report.flagged, report.missing) == (1, 1, [])
        (request,) = vision.requests
        assert (request.ai_made, request.faces, request.user_id, request.mime) == (
            False,
            True,
            None,
            "image/jpeg",
        )
        screen = await session.get(FieldPhotoScreen, image.id, populate_existing=True)
        assert screen is not None and screen.imageSha256 == image.sha256
        assert (screen.verdict, screen.flags, screen.provider) == ("FLAGGED", ["ID_DOCUMENT"], "GEMINI")
        assert screen.reasons == [FLAG_REASONS["ID_DOCUMENT"], CARD]
        again = await screened(session, photos, image, vision)
        assert again.screened == 0 and len(vision.requests) == 1
        queue = await photo_queue(session, state="WAITING", cursor=None, objects=photos, now=NOW)
        (item,) = [each for each in queue.items if each.item_id == ITEM]
        assert (item.risk, item.master_only, item.state) == ("IDENTITY", True, "WAITING")
        assert item.file_url == f"https://bucket.test/{image.objectKey}"


async def test_a_photograph_flagged_as_an_identity_document_is_shown_only_by_a_master_admin() -> None:
    async with rolled_back() as session:
        photos = PhotoStore()
        image = await held_photo(session, KeptStore())
        craft = await ajrakh(session)
        await switched(session, "SHOWN")
        await screened(session, photos, image, SeenVision(flags=("ID_DOCUMENT",), note=CARD))
        admin, master = await person(session, "ADMIN"), await person(session, "MASTER_ADMIN")
        with pytest.raises(PhotoRefused) as refused:
            await decided(session, image, admin, photos, decision="SHOW")
        assert refused.value.status == 403
        with pytest.raises(PhotoRefused) as unclear:
            await decided(session, image, master, photos, decision="SHOW")
        assert unclear.value.status == 409
        await decided(session, image, admin, photos, decision="HIDE", reason="IDENTITY_DOCUMENT")
        await decided(session, image, master, photos, decision="SHOW", clear_flags=True)
        listed, _total = await craft_field_photos(session, craft.id, limit=25, offset=0)
        assert ITEM in {photo.item_id for photo in listed}


async def test_a_face_no_one_is_named_for_needs_a_master_admin_and_a_named_face_does_not() -> None:
    async with rolled_back() as session:
        photos = PhotoStore()
        named = await held_photo(session, KeptStore())
        await screened(session, photos, named, SeenVision(flags=("FACE",)))
        await decided(session, named, await person(session, "ADMIN"), photos, decision="SHOW")
    async with rolled_back() as session:
        photos = PhotoStore()
        image = await held_photo(session, KeptStore(), change=unnamed)
        await screened(session, photos, image, SeenVision(flags=("FACE",)))
        with pytest.raises(PhotoRefused) as refused:
            await decided(session, image, await person(session, "ADMIN"), photos, decision="SHOW")
        assert refused.value.status == 403
        made = await decided(
            session, image, await person(session, "MASTER_ADMIN"), photos, decision="CROP", crop=CROP
        )
        assert made.made_key is not None


async def test_every_decision_is_recorded_with_who_when_and_why() -> None:
    async with rolled_back() as session:
        photos = PhotoStore()
        image = await held_photo(session, KeptStore())
        admin = await person(session, "ADMIN")
        await decided(
            session, image, admin, photos, decision="HIDE", reason="OTHER", note="A wedding, not the craft"
        )
        row = await session.scalar(
            select(AuditLog).where(
                AuditLog.action == "field_photo.decided", AuditLog.targetId == str(image.id)
            )
        )
        assert row is not None and (row.actorId, row.targetType) == (admin.id, "FieldImage")
        assert row.detail is not None
        assert (row.detail["decision"], row.detail["reason"], row.detail["note"]) == (
            "HIDE",
            "OTHER",
            "A wedding, not the craft",
        )
        assert row.detail["itemId"] == ITEM and row.detail["imageSha256"] == image.sha256
        assert datetime.fromisoformat(row.detail["decidedAt"]).tzinfo is not None


async def test_the_crop_is_served_and_the_original_never_is() -> None:
    async with rolled_back() as session:
        photos = PhotoStore()
        image = await held_photo(session, KeptStore())
        craft = await ajrakh(session)
        await switched(session, "SHOWN")
        await screened(session, photos, image)
        made = await decided(
            session, image, await person(session, "ADMIN"), photos, decision="CROP", crop=CROP
        )
        assert made.made_key is not None and made.made_key != image.objectKey
        served = await served_photo(session, image.id)
        assert served is not None and served.key == made.made_key
        body, mime = photos.objects[made.made_key]
        assert mime == "image/jpeg" and body != photos.objects[image.objectKey][0]
        listed, _total = await craft_field_photos(session, craft.id, limit=25, offset=0)
        (photo,) = [each for each in listed if each.item_id == ITEM]
        assert (photo.width, photo.height) == (1000, 700)
        made_again = await decided(session, image, await person(session, "ADMIN"), photos, decision="SHOW")
        assert made_again.released_key == made.made_key


async def test_a_decision_on_a_copy_other_than_the_one_seen_is_refused() -> None:
    async with rolled_back() as session:
        photos = PhotoStore()
        image = await held_photo(session, KeptStore())
        await screened(session, photos, image)
        request = PhotoDecisionRequest(decision="SHOW", seen_sha256="0" * 64)
        admin = await person(session, "ADMIN")
        with pytest.raises(PhotoRefused) as refused:
            await decide_photo(session, image.id, request, actor=admin, objects=photos)
        assert (refused.value.status, refused.value.detail) == (409, CHANGED)


def as_user(user: User) -> Callable[[], User]:
    return lambda: user


@pytest.fixture
async def reviewed() -> AsyncIterator[dict[str, Any]]:
    async with rolled_back() as session:
        yield {"session": session, "image": await held_photo(session, KeptStore())}


async def test_only_admins_and_master_admins_decide(reviewed: dict[str, Any]) -> None:
    session, image = reviewed["session"], reviewed["image"]
    app = create_app()

    async def opened() -> AsyncIterator[Any]:
        yield session

    app.dependency_overrides[get_session] = opened
    body = {"decision": "HIDE", "reason": "POOR_QUALITY", "seenSha256": image.sha256}
    path = f"/api/field-photos/{image.id}/decision"
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        for role in ("STUDENT", "RESEARCHER", "PROFESSOR"):
            user = await person(session, role)
            sign_in_as(app, as_user(user))
            assert (await client.post(path, json=body)).status_code == 403, role
        for role in ("ADMIN", "MASTER_ADMIN"):
            user = await person(session, role)
            sign_in_as(app, as_user(user))
            answered = await client.post(path, json=body)
            assert answered.status_code == 200, (role, answered.text)
            assert (answered.json()["state"], answered.json()["decision"]["decidedRole"]) == ("HIDDEN", role)
