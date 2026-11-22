import io
import uuid
from collections.abc import AsyncIterator
from decimal import Decimal
from typing import Any, cast

import pytest
from PIL import Image
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import InvalidInput
from app.models import ImageFingerprint, ImageScreen, MediaAsset, PictureDeclaration, TaskReservation
from app.research.image_contributions import BatchPicture, ImageBatch, SharedDeclaration
from app.research.image_intake_pixels import pixels_of
from app.research.image_screens import FLAG_REASONS, ScreenTools, signed_fingerprint
from app.services import image_contributions as images
from app.services.image_screens_backfill import fingerprint_stored
from app.services.task_reservations import claim_task
from app.services.upload_links_give import GivenFile, Giving, Handing, give_pictures

from ..pictures import FakeObjects, SeenVision, picture, screen_tools
from .picture_seed import MATERIAL, NOW, SLUG, STAGE, People, people_in, seeded_session, sent

pytestmark = pytest.mark.db

SITE = "https://kalavigyan.example"
CARD_NOTE = "A card with a photo and a twelve-digit number"
WORDS = "Yes, I took these photographs and the Centre may publish them without my name."
DRAWING = {"origin": "DRAWING", "generator": None, "prompt": None}
SVG = (
    b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 640 480"><script>alert(1)</script>'
    b'<rect width="640" height="480" fill="var(--sunk)"/></svg>'
)


@pytest.fixture
async def session() -> AsyncIterator[AsyncSession]:
    async for opened in seeded_session():
        yield opened


@pytest.fixture
async def people(session: AsyncSession) -> People:
    return await people_in(session)


async def screen_of(session: AsyncSession, contribution_id: uuid.UUID) -> ImageScreen:
    found = await session.scalar(select(ImageScreen).where(ImageScreen.contributionId == contribution_id))
    assert found is not None
    return found


def smaller_jpeg(data: bytes) -> bytes:
    made = Image.open(io.BytesIO(data))
    out = io.BytesIO()
    made.resize((made.width // 2, made.height // 2)).save(out, "JPEG", quality=70)
    return out.getvalue()


async def test_a_professors_flagged_picture_waits_for_review_with_its_reasons_and_its_cost(
    session: AsyncSession, people: People
) -> None:
    vision = SeenVision(flags=("ID_DOCUMENT",), note=CARD_NOTE)
    row = await sent(session, people.professor, picture(seed=41), tools=screen_tools(vision))
    assert (row.status, row.reviewedById) == ("PENDING", None)
    screen = await screen_of(session, row.id)
    assert (screen.verdict, screen.flags, screen.costUsd, screen.provider, screen.receivedMime) == (
        "FLAGGED",
        ["ID_DOCUMENT"],
        Decimal("0.000150"),
        "GEMINI",
        "image/png",
    )
    assert screen.reasons == [FLAG_REASONS["ID_DOCUMENT"], CARD_NOTE]
    (request,) = vision.requests
    assert (request.ai_made, request.mime, request.user_id) == (True, "image/jpeg", people.professor.id)
    stored = await session.get(ImageFingerprint, row.assetId)
    assert stored is not None and stored.fingerprint == screen.fingerprint


async def test_without_a_vision_route_even_a_professors_picture_waits_for_a_person(
    session: AsyncSession, people: People
) -> None:
    row = await sent(session, people.professor, picture(seed=42), tools=ScreenTools(vision=None))
    screen = await screen_of(session, row.id)
    assert (row.status, screen.verdict, screen.flags, screen.costUsd) == (
        "PENDING",
        "UNSCREENED",
        ["NOT_SCREENED"],
        Decimal(0),
    )


async def test_a_smaller_copy_of_a_contributed_picture_is_refused_before_the_vision_call(
    session: AsyncSession, people: People
) -> None:
    original = picture(1200, 900, seed=43)
    await sent(session, people.researcher, original)
    vision = SeenVision()
    with pytest.raises(images.ContributionRefused, match="contributed already"):
        await sent(session, people.other_researcher, smaller_jpeg(original), tools=screen_tools(vision))
    assert vision.requests == []


async def test_a_copy_of_a_picture_kalavigyan_holds_is_refused(session: AsyncSession, people: People) -> None:
    data = picture(seed=44)
    asset = MediaAsset(
        s3Key=f"media/test/{uuid.uuid4()}.png", mime="image/png", bytes=len(data), visibility="PRIVATE"
    )
    session.add(asset)
    await session.flush()
    session.add(
        ImageFingerprint(assetId=asset.id, fingerprint=signed_fingerprint(pixels_of(data).fingerprint))
    )
    await session.flush()
    with pytest.raises(images.ContributionRefused, match="already holds"):
        await sent(session, people.researcher, data)


async def test_a_stored_picture_without_a_fingerprint_gets_one(session: AsyncSession) -> None:
    data = picture(seed=45)
    objects = FakeObjects()
    key = f"media/test/{uuid.uuid4()}.png"
    objects.puts[key] = (data, "image/png")
    asset = MediaAsset(s3Key=key, mime="image/png", bytes=len(data), visibility="PRIVATE")
    session.add(asset)
    await session.flush()
    report = await fingerprint_stored(session, cast(Any, objects))
    stored = await session.get(ImageFingerprint, asset.id)
    assert report.fingerprinted >= 1 and str(asset.id) not in report.unreadable
    assert stored is not None and stored.fingerprint == signed_fingerprint(pixels_of(data).fingerprint)


async def test_an_svg_drawing_is_cleaned_and_always_waits_for_a_person(
    session: AsyncSession, people: People
) -> None:
    vision = SeenVision()
    row = await sent(session, people.professor, SVG, tools=screen_tools(vision), **DRAWING)
    asset = await session.get(MediaAsset, row.assetId)
    screen = await screen_of(session, row.id)
    assert (row.status, asset is not None and asset.mime, screen.verdict, screen.fingerprint) == (
        "PENDING",
        "image/svg+xml",
        "UNSCREENED",
        None,
    )
    assert vision.requests == []


async def test_a_picture_for_a_task_takes_its_material_and_its_approval_completes_the_task(
    session: AsyncSession, people: People
) -> None:
    key = f"MISSING_PICTURE:craft:{SLUG}:material-{MATERIAL}"
    await claim_task(session, people.researcher.id, key, site=SITE, now=NOW)
    row = await sent(session, people.researcher, picture(seed=46), taskKey=key)
    assert (row.materialId, row.stageId, row.slot, row.taskKey) == (MATERIAL, None, None, key)
    await images.approve(session, row.id, people.admin, None, now=NOW)
    held = await session.scalar(select(TaskReservation).where(TaskReservation.taskKey == key))
    assert held is not None and held.ending == "COMPLETED"


@pytest.mark.parametrize(
    "changes",
    [
        {"taskKey": "MISSING_PICTURE:craft:Some-Other-Craft:slot-masthead"},
        {"taskKey": f"MISSING_PICTURE:craft:{SLUG}:material-{MATERIAL}", "stageId": str(STAGE)},
        {"taskKey": f"MISSING_FIELD:craft:{SLUG}:HISTORY"},
    ],
    ids=["other-craft", "other-target", "not-a-picture-task"],
)
async def test_a_task_of_another_craft_or_target_is_refused(
    session: AsyncSession, people: People, changes: dict[str, Any]
) -> None:
    with pytest.raises(InvalidInput, match="not a picture task"):
        await sent(session, people.researcher, picture(seed=47), **changes)


async def test_a_batch_declares_each_picture_under_one_declaration(
    session: AsyncSession, people: People
) -> None:
    batch = ImageBatch.model_validate(
        {
            "craftSlug": SLUG,
            "origin": "PHOTOGRAPH",
            "rightsConfirmed": True,
            "termsVersion": "2026-11-19",
            "pictures": [
                {"caption": "The vat at dawn", "altText": "A clay vat", "stageId": str(STAGE)},
                {"caption": "The indigo cake", "altText": "A blue lump", "materialId": str(MATERIAL)},
            ],
        }
    )
    rows = await images.declare_batch(
        session, people.researcher, batch, images.Filing(channel="WEB"), now=NOW
    )
    record = await session.get(PictureDeclaration, rows[0].declarationId)
    assert record is not None and (record.channel, record.pictures, record.origin) == ("WEB", 2, "PHOTOGRAPH")
    assert [(row.stageId, row.materialId, row.declarationId) for row in rows] == [
        (STAGE, None, record.id),
        (None, MATERIAL, record.id),
    ]


async def test_pictures_from_the_chat_are_screened_one_by_one_under_one_confirmed_declaration(
    session: AsyncSession, people: People
) -> None:
    shared = SharedDeclaration(origin="PHOTOGRAPH", rights_confirmed=True, terms_version="2026-11-19")
    vat = BatchPicture(caption="The vat at dawn", alt_text="A clay vat", stage_id=STAGE)
    files = [
        GivenFile(1, vat, picture(seed=48)),
        GivenFile(2, vat, picture(seed=48)),
        GivenFile(3, vat, None, "The picture's link was refused: inside resolves to 10.0.0.7"),
    ]
    giving = Giving(craft_slug=SLUG, shared=shared, confirmation=WORDS, files=files)
    handing = Handing(objects=cast(Any, FakeObjects()), tools=screen_tools(), now=NOW)
    result = await give_pictures(session, people.professor, giving, handing=handing)
    assert (result.given, result.refused) == (1, 2)
    assert [picture.refused for picture in result.pictures] == [
        None,
        "The same picture is given twice in this call",
        "The picture's link was refused: inside resolves to 10.0.0.7",
    ]
    assert (result.pictures[0].status, result.pictures[0].screen is not None) == ("APPROVED", True)
    record = await session.get(PictureDeclaration, result.declaration_id)
    assert record is not None and (
        record.channel,
        record.confirmation,
        record.contributorId,
        record.pictures,
    ) == (
        "MCP",
        WORDS,
        people.professor.id,
        1,
    )
