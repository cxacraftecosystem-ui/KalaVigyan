import logging
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable, Sequence
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_engine
from app.models import (
    AppSetting,
    ArtisanContribution,
    Claim,
    ClaimSource,
    Compound,
    Craft,
    CraftLocation,
    CraftPageArchive,
    CraftPageSnapshot,
    CraftSubCategory,
    CuratedCategoryClaim,
    DistrictEnvValue,
    EnvDataset,
    FieldRecording,
    FieldRecordingCraft,
    FieldVoiceStream,
    KnowledgePiece,
    MediaRef,
    MediaRefClaim,
    Source,
)
from app.research.field_voices import ARTISAN_IMAGES_SETTING, ARTISAN_IMAGES_SHOWN
from app.retrieval.statements import CraftScope, scope_claims
from app.services import knowledge_view
from app.services.category_import import import_categories
from app.services.craft_chapters_job import build_craft_chapters
from app.services.craft_page_archive import archived_page, curation_version
from app.services.craft_page_cache import PageCache
from app.services.craft_page_snapshots import rebuild_snapshots, served_page
from app.services.craft_page_stamp import craft_compound_ids, page_stamp
from app.services.curation_import import import_curation
from app.sources.reference.wikidata_places import PlacePoint

from .field_voices_rows import KeptStore, synced
from .testimony_seed import seed

pytestmark = pytest.mark.db

AJRAKH = "Kutch-Ajrakh"
KACHCHH = 449
LATER = datetime.now(UTC) + timedelta(minutes=5)

Mover = Callable[[AsyncSession, Craft], Awaitable[None]]


@pytest.fixture
async def session() -> AsyncIterator[AsyncSession]:
    async with get_engine().connect() as connection:
        transaction = await connection.begin()
        try:
            session = AsyncSession(bind=connection, expire_on_commit=False, autoflush=False)
            yield session
            await session.close()
        finally:
            await transaction.rollback()


async def ajrakh(session: AsyncSession) -> Craft:
    assert (await import_curation(session)).refused == []
    assert (await import_categories(session)).refused == []
    craft = await knowledge_view.resolve_craft(session, AJRAKH)
    assert craft is not None
    return craft


def own_claims(craft: Craft) -> object:
    return select(Claim.id).where(scope_claims(CraftScope(craft.id, craft.subCategoryId)))


async def touch_citation(session: AsyncSession, craft: Craft) -> None:
    await session.execute(
        update(ClaimSource).where(ClaimSource.claimId.in_(own_claims(craft))).values(updatedAt=LATER)
    )


async def touch_source(session: AsyncSession, craft: Craft) -> None:
    cited = select(ClaimSource.sourceId).where(ClaimSource.claimId.in_(own_claims(craft)))
    await session.execute(update(Source).where(Source.id.in_(cited)).values(updatedAt=LATER))


async def retract_family_claim(session: AsyncSession, craft: Craft) -> None:
    family = select(CraftSubCategory.categoryId).where(CraftSubCategory.id == craft.subCategoryId)
    claim_id = await session.scalar(
        select(CuratedCategoryClaim.claimId).where(CuratedCategoryClaim.categoryId.in_(family)).limit(1)
    )
    assert claim_id is not None
    await session.execute(
        update(Claim).where(Claim.id == claim_id).values(status="RETRACTED", updatedAt=LATER)
    )


async def touch_relative(session: AsyncSession, craft: Craft) -> None:
    kin = select(Craft.id).where(Craft.subCategoryId == craft.subCategoryId, Craft.id != craft.id).limit(1)
    await session.execute(update(Craft).where(Craft.id.in_(kin)).values(updatedAt=LATER))


async def keep_a_conformer(session: AsyncSession, craft: Craft) -> None:
    compound_id = await session.scalar(
        select(Compound.id).where(Compound.id.in_(craft_compound_ids(craft))).limit(1)
    )
    assert compound_id is not None
    await session.execute(update(Compound).where(Compound.id == compound_id).values(conformerKeptAt=LATER))


async def load_a_geo_value(session: AsyncSession, craft: Craft) -> None:
    located = await session.scalar(
        select(CraftLocation.districtLgd).where(
            CraftLocation.craftId == craft.id, CraftLocation.districtLgd == KACHCHH
        )
    )
    assert located == KACHCHH
    dataset = EnvDataset(id=uuid.uuid4(), code=f"TEST_{uuid.uuid4().hex[:8]}", title="A test dataset")
    session.add(dataset)
    await session.flush()
    session.add(
        DistrictEnvValue(
            districtLgd=KACHCHH, datasetId=dataset.id, variable="test_mean", stat="DISTRICT_MEAN", value=1
        )
    )


async def hide_a_piece(session: AsyncSession, craft: Craft) -> None:
    piece_id = await session.scalar(
        select(KnowledgePiece.id).where(KnowledgePiece.craftId == craft.id).limit(1)
    )
    assert piece_id is not None
    await session.execute(update(KnowledgePiece).where(KnowledgePiece.id == piece_id).values(hiddenAt=LATER))


async def touch_a_picture(session: AsyncSession, craft: Craft) -> None:
    linked = select(MediaRefClaim.mediaRefId).where(MediaRefClaim.claimId.in_(own_claims(craft)))
    await session.execute(update(MediaRef).where(MediaRef.id.in_(linked)).values(updatedAt=LATER))


async def show_artisan_images(session: AsyncSession, craft: Craft) -> None:
    found = await session.scalar(select(AppSetting).where(AppSetting.key == ARTISAN_IMAGES_SETTING))
    if found is None:
        session.add(AppSetting(key=ARTISAN_IMAGES_SETTING, value=ARTISAN_IMAGES_SHOWN))
        return
    await session.execute(
        update(AppSetting).where(AppSetting.id == found.id).values(value="CHANGED", updatedAt=LATER)
    )


async def freshen_a_stream(session: AsyncSession, craft: Craft) -> None:
    stream = await session.get(FieldVoiceStream, ("DESIGNER", "IMAGES"))
    if stream is None:
        session.add(FieldVoiceStream(portal="DESIGNER", stream="IMAGES", lastContactAt=datetime.now(UTC)))
        return
    stale = datetime.now(UTC) - timedelta(days=30)
    fresh = stream.lastContactAt is not None and stream.lastContactAt > stale
    stream.lastContactAt = stale if fresh else datetime.now(UTC)


MOVERS: dict[str, Mover] = {
    "a citation": touch_citation,
    "a cited source": touch_source,
    "a family claim's visibility": retract_family_claim,
    "a relative": touch_relative,
    "a kept conformer": keep_a_conformer,
    "a geo value of a mapped district": load_a_geo_value,
    "a piece's hidden mark": hide_a_piece,
    "a picture of the craft": touch_a_picture,
    "the artisan images setting": show_artisan_images,
    "a portal stream's freshness": freshen_a_stream,
}


@pytest.mark.parametrize("name", sorted(MOVERS))
async def test_the_stamp_moves_with_each_input_the_page_reads(session: AsyncSession, name: str) -> None:
    craft = await ajrakh(session)
    before = await page_stamp(session, craft, "OPEN")
    assert await page_stamp(session, craft, "OPEN") == before
    await MOVERS[name](session, craft)
    await session.flush()
    assert await page_stamp(session, craft, "OPEN") != before


async def test_the_stamp_moves_when_a_field_recording_is_hidden(session: AsyncSession) -> None:
    craft = await ajrakh(session)
    await synced(session, KeptStore())
    recording_id = await session.scalar(select(FieldRecording.id).limit(1))
    assert recording_id is not None
    linked = await session.get(FieldRecordingCraft, (recording_id, craft.id))
    if linked is None:
        session.add(FieldRecordingCraft(recordingId=recording_id, craftId=craft.id))
        await session.flush()
    before = await page_stamp(session, craft, "OPEN")
    await session.execute(
        update(FieldRecording)
        .where(FieldRecording.id == recording_id)
        .values(hiddenAt=LATER, updatedAt=LATER)
    )
    await session.flush()
    assert await page_stamp(session, craft, "OPEN") != before


@pytest.mark.parametrize("change", ["approvedAt", "withdrawnAt"])
async def test_the_stamp_moves_when_testimony_is_approved_or_withdrawn(
    session: AsyncSession, change: str
) -> None:
    seeded = await seed(session)
    before = await page_stamp(session, seeded.craft, "OPEN")
    approved = {"status": "APPROVED", "claimId": seeded.fact_claim}
    settled = approved if change == "approvedAt" else {"status": "WITHDRAWN"}
    await session.execute(
        update(ArtisanContribution)
        .where(ArtisanContribution.id == seeded.contribution.id)
        .values({change: LATER, **settled})
    )
    await session.flush()
    assert await page_stamp(session, seeded.craft, "OPEN") != before


async def test_a_body_that_changes_under_the_same_stamp_is_logged(
    session: AsyncSession, caplog: pytest.LogCaptureFixture
) -> None:
    craft = await ajrakh(session)
    await served_page(session, craft, "OPEN")
    await served_page(session, craft, "RESEARCHER")
    stored = await session.get(CraftPageSnapshot, (craft.id, "OPEN"))
    assert stored is not None
    stored.body = {**stored.body, "lede": []}
    stored.etag = "a body the inputs do not explain"
    await session.flush()
    with caplog.at_level(logging.ERROR):
        assert await rebuild_snapshots(session, craft) is True
    errors = [r.getMessage() for r in caplog.records if r.levelno == logging.ERROR]
    assert any(AJRAKH in message and "unchanged stamp" in message for message in errors)


async def test_a_process_cache_answers_a_repeat_read_without_the_snapshot(session: AsyncSession) -> None:
    craft = await ajrakh(session)
    cache = PageCache()
    first = await served_page(session, craft, "OPEN", cache=cache)
    stored = await session.get(CraftPageSnapshot, (craft.id, "OPEN"))
    assert stored is not None
    await session.delete(stored)
    await session.flush()
    again = await served_page(session, craft, "OPEN", cache=cache)
    assert again is first


async def test_an_archived_version_is_read_without_its_field_voices(session: AsyncSession) -> None:
    craft = await ajrakh(session)
    version = await curation_version(session, craft)
    assert version is not None
    first = await served_page(session, craft, "OPEN")
    voiced = {
        **first.body,
        "fieldVoicesTotal": {"quotes": 3, "images": 1},
        "curation": {**first.body["curation"], "version": version - 1},
    }
    session.add(
        CraftPageArchive(
            craftId=craft.id,
            curationVersion=version - 1,
            variant="OPEN",
            body=voiced,
            etag="frozen",
            frozenAt=datetime.now(UTC),
        )
    )
    await session.flush()
    archived = await archived_page(session, craft, "OPEN", version - 1)
    assert archived is not None and archived["fieldVoicesTotal"] == {"quotes": 0, "images": 0}
    assert archived["voices"] == [] and archived["fieldPhotos"] == []


async def stored_bodies(session: AsyncSession, craft: Craft) -> dict[str, Any]:
    rows = await session.scalars(
        select(CraftPageSnapshot)
        .where(CraftPageSnapshot.craftId == craft.id)
        .execution_options(populate_existing=True)
    )
    return {row.variant: row.body for row in rows}


def moved_paths(before: Any, after: Any, path: str = "$", limit: int = 12) -> list[str]:
    if type(before) is not type(after):
        return [path]
    if isinstance(before, dict):
        keys = sorted(set(before) | set(after))
        found = [
            p for key in keys for p in moved_paths(before.get(key), after.get(key), f"{path}.{key}", limit)
        ]
        return found[:limit]
    if isinstance(before, list):
        if len(before) != len(after):
            return [f"{path}[{len(before)}->{len(after)}]"]
        found = [
            p
            for i, (a, b) in enumerate(zip(before, after, strict=True))
            for p in moved_paths(a, b, f"{path}[{i}]", limit)
        ]
        return found[:limit]
    return [] if before == after else [f"{path}: {str(before)[:80]!r} -> {str(after)[:80]!r}"]


class KeptConformers:
    def __init__(self) -> None:
        self.asked: list[int] = []

    async def conformer(self, cid: int) -> str | None:
        self.asked.append(cid)
        return f"conformer of {cid}"


class NoPoints:
    async def place_points(self, item_ids: Sequence[str]) -> dict[str, PlacePoint]:
        return {}


async def test_the_chapters_job_keeps_each_conformer_once_and_rebuilds_the_pages(
    session: AsyncSession,
) -> None:
    craft = await ajrakh(session)
    keeper = KeptConformers()
    first = await build_craft_chapters(session, [craft], lookups=(keeper, NoPoints()), now=datetime.now(UTC))
    assert first.ok and first.pages_rebuilt == 1 and first.conformers_kept == len(keeper.asked) > 0
    kept = await session.scalar(
        select(func.count())
        .select_from(Compound)
        .where(Compound.id.in_(craft_compound_ids(craft)), Compound.conformerKeptAt.is_not(None))
    )
    assert kept == first.conformers_kept
    built = await stored_bodies(session, craft)
    again = await build_craft_chapters(session, [craft], lookups=(keeper, NoPoints()), now=datetime.now(UTC))
    moved = {
        variant: moved_paths(body, (await stored_bodies(session, craft))[variant])
        for variant, body in built.items()
    }
    assert moved == {variant: [] for variant in built}
    assert (again.conformers_kept, again.pages_changed) == (0, 0)
    assert len(keeper.asked) == first.conformers_kept
