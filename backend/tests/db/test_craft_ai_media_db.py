import hashlib
import uuid
from decimal import Decimal

import pytest

from app.media.records import NewAsset
from app.models import MediaAsset, ProcessStage, User
from app.services.craft_ai_media import copied_older_media, page_media_key_of, shared_ai_media

from .test_media_store_db import Stores, queued, stage_with_claims, stores, user

pytestmark = pytest.mark.db

__all__ = ["stores"]

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32


class Bucket:
    def __init__(self, stored: dict[str, bytes]) -> None:
        self.stored = stored
        self.puts: dict[str, tuple[bytes, str]] = {}

    async def get(self, key: str) -> bytes | None:
        return self.stored.get(key)

    async def put(self, key: str, body: bytes, *, content_type: str) -> None:
        self.puts[key] = (body, content_type)


def asset(owner: User, *, page_key: str | None, named: bool = False) -> NewAsset:
    leaf = "KalaVigyan_Generated-Image_2026-11-16_1430_Media-Test_Image_Step-06.png"
    return NewAsset(
        id=uuid.uuid4(),
        s3_key=f"media/{owner.id}/{uuid.uuid4().hex}/{leaf}",
        mime="image/png",
        size=len(PNG),
        width=1024,
        height=1024,
        duration_seconds=None,
        model="gemini-3.1-flash-image",
        alt_text="Alum is the mordant.",
        depicts_named_cluster=named,
        page_key=page_key,
    )


async def succeeded(
    stores: Stores, stage: ProcessStage, ids: dict[str, uuid.UUID], made: NewAsset, owner: User
) -> None:
    media, queue, _ = stores
    await queued(media, owner, stage, (ids["verified"], ids["quoted"]))
    [claimed] = await queue.claim("IMAGE", limit=1, worker_id="w1")
    await queue.succeed(claimed, made, cost_usd=Decimal("0.067"), billed_tokens=1120)


async def test_a_page_copy_shares_the_asset_unless_it_names_a_cluster(stores: Stores) -> None:
    media, _, session = stores
    stage, ids = await stage_with_claims(session)
    owner = await user(session)
    shown = asset(owner, page_key=f"media/craft/{'a' * 64}/shown.png")
    named = asset(owner, page_key=f"media/craft/{'b' * 64}/named.png", named=True)
    for made in (shown, named):
        await succeeded(stores, stage, ids, made, owner)
    craft_id = (await media.stage(stage.id)).craft.id
    listed = await shared_ai_media(session, craft_id)
    assert [record.asset_id for record in listed] == [shown.id]
    assert listed[0].stage_id == stage.id and set(listed[0].claim_ids) == {ids["verified"], ids["quoted"]}
    assert (listed[0].kind, listed[0].model, listed[0].alt_text) == (
        "IMAGE",
        "gemini-3.1-flash-image",
        "Alum is the mordant.",
    )
    assert await page_media_key_of(session, shown.id) == shown.page_key
    assert await page_media_key_of(session, named.id) is None


async def test_the_job_copies_an_older_asset_once_and_shares_it(stores: Stores) -> None:
    _, _, session = stores
    stage, ids = await stage_with_claims(session)
    owner = await user(session)
    older = asset(owner, page_key=None)
    await succeeded(stores, stage, ids, older, owner)
    row = await session.get(MediaAsset, older.id)
    assert row is not None and (row.visibility, row.pageKey) == ("PRIVATE", None)
    bucket = Bucket({older.s3_key: PNG})
    assert await copied_older_media(session, bucket) >= 1
    page_key = f"media/craft/{hashlib.sha256(PNG).hexdigest()}/{older.s3_key.rsplit('/', 1)[-1]}"
    assert bucket.puts[page_key] == (PNG, "image/png")
    await session.refresh(row)
    assert (row.visibility, row.pageKey) == ("CRAFT_SHARED", page_key)
    again = Bucket({older.s3_key: PNG})
    await copied_older_media(session, again)
    assert page_key not in again.puts
