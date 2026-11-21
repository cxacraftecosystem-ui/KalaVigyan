import uuid
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import FieldImage, User
from app.research.field_photo_reviews import PhotoCrop, PhotoDecisionRequest
from app.services.field_photo_decisions import Decided, decide_photo
from app.services.field_photo_screens import ScreenReport, screen_held_photos
from app.services.field_voices_held import set_artisan_image_visibility
from app.services.field_voices_reader import field_voices_reader
from app.services.field_voices_sync import sync_portal
from app.services.field_voices_view import craft_field_photos, voices_part
from app.services.object_store import PresignedGet
from tests.db.field_voices_rows import KeptStore, ledger_for
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
from tests.pictures import SeenVision, picture, screen_tools

__all__ = [
    "ITEM",
    "PhotoStore",
    "decided",
    "held_photo",
    "person",
    "photo_ids",
    "same_session",
    "screened",
    "switched",
]

ITEM = f"{FR}:fr-img-1"
NOTE = "Checked against the artisan's own record"


@dataclass
class PhotoStore:
    objects: dict[str, tuple[bytes, str]] = field(default_factory=dict)
    deleted: list[str] = field(default_factory=list)

    async def get(self, key: str) -> bytes | None:
        stored = self.objects.get(key)
        return stored[0] if stored else None

    async def put(self, key: str, body: bytes, *, content_type: str) -> None:
        self.objects[key] = (body, content_type)

    async def delete(self, key: str) -> None:
        self.deleted.append(key)
        self.objects.pop(key, None)

    def presigned_get(self, key: str, *, disposition: str, seconds: int, now: datetime) -> PresignedGet:
        return PresignedGet(url=f"https://bucket.test/{key}", expires_at=now + timedelta(seconds=seconds))


def same_session(session: AsyncSession) -> Callable[[], Any]:
    @asynccontextmanager
    async def opened() -> AsyncIterator[AsyncSession]:
        yield session

    return opened


async def held_photo(
    session: AsyncSession, store: KeptStore, *, change: Callable[[dict[str, Any]], None] | None = None
) -> FieldImage:
    answers = caught_up(FR)
    page = answers[(f"{STATE}/images", "all", None)]
    page["changes"][0]["artisanLinked"] = True
    if change is not None:
        change(page["changes"][0])
    resigned(page["changes"][0])
    live = [(c["id"], c["revision"]) for c in page["changes"] if c["state"] == "LIVE"]
    answers[(STATE, None, None)]["streams"]["images"]["digest"] = reference_digest(live)
    reader = field_voices_reader(enabled_settings(), FR, transport=portal_transport(answers))
    report = await sync_portal(reader, ledger_for(session, store), FakeCopier(), clock=FakeClock().clock())
    assert report.as_dict()["ok"], report.as_dict()
    image = await session.scalar(
        select(FieldImage)
        .where(FieldImage.portalMediaId == "fr-img-1")
        .execution_options(populate_existing=True)
    )
    assert image is not None and image.artisanLinked is True
    return image


async def screened(
    session: AsyncSession, photos: PhotoStore, image: FieldImage, vision: SeenVision | None = None
) -> ScreenReport:
    photos.objects[image.objectKey] = (
        picture(image.width, image.height, seed=7, kind="JPEG"),
        image.mimeType,
    )
    return await screen_held_photos(
        same_session(session), photos, screen_tools(vision or SeenVision()), limit=10
    )


async def person(session: AsyncSession, role: str) -> User:
    user = User(
        id=uuid.uuid4(),
        email=f"{role.lower()}-{uuid.uuid4().hex[:8]}@example.org",
        name=f"{role.title()} Reviewer",
        role=role,
    )
    session.add(user)
    await session.flush()
    return user


async def decided(
    session: AsyncSession, image: FieldImage, actor: User, photos: PhotoStore, **choice: Any
) -> Decided:
    crop = choice.pop("crop", None)
    request = PhotoDecisionRequest(
        decision=choice.pop("decision"),
        seen_sha256=image.sha256,
        crop=PhotoCrop(**crop) if crop else None,
        note=choice.pop(
            "note", NOTE if choice.get("clear_flags") or choice.get("reason") == "OTHER" else None
        ),
        **choice,
    )
    made = await decide_photo(session, image.id, request, actor=actor, objects=photos)
    await session.flush()
    return made


async def switched(session: AsyncSession, visibility: str) -> None:
    await set_artisan_image_visibility(session, visibility, actor_id=None)
    await session.flush()


async def photo_ids(session: AsyncSession, craft_id: uuid.UUID) -> set[str]:
    listed, _total = await craft_field_photos(session, craft_id, limit=25, offset=0)
    part = await voices_part(session, craft_id, voices=6, photos=12)
    return {photo.item_id for photo in listed} | {photo.item_id for photo in part.photos}
