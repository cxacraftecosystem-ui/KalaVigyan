import uuid
from collections.abc import AsyncIterator
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.db import get_engine
from app.media.claim_set import claim_set
from app.media.ledger import refund_entry, unit_entry
from app.media.queue_store import SqlQueueStore
from app.media.records import Created, CreateLimits, JobRecord, NewAsset, NewJob
from app.media.store import SqlMediaStore, queue_key
from app.models import (
    Claim,
    ClaimSource,
    Concept,
    Craft,
    CraftLocation,
    Job,
    Material,
    MediaAsset,
    MediaJob,
    Process,
    ProcessStage,
    QuotaLedger,
    Source,
    StageMaterial,
    UsageEvent,
    User,
)

pytestmark = pytest.mark.db

NOW = datetime.now(UTC).replace(microsecond=0)
Stores = tuple[SqlMediaStore, SqlQueueStore, AsyncSession]


@pytest.fixture
async def stores() -> AsyncIterator[Stores]:
    async with get_engine().connect() as connection:
        transaction = await connection.begin()
        try:
            factory = async_sessionmaker(
                bind=connection, expire_on_commit=False, join_transaction_mode="create_savepoint"
            )
            async with factory() as session:
                yield SqlMediaStore(factory), SqlQueueStore(factory), session
        finally:
            await transaction.rollback()


async def user(session: AsyncSession) -> User:
    found = User(id=uuid.uuid4(), name="Media Learner", email=f"media-{uuid.uuid4().hex[:8]}@example.com")
    session.add(found)
    await session.commit()
    return found


async def cited(
    session: AsyncSession, claim: Claim, *, check: str = "PASS", sensitivity: str = "OPEN"
) -> None:
    source = Source(id=uuid.uuid4(), kind="PAPER", title=f"Source for {claim.text}", sensitivity=sensitivity)
    session.add(source)
    await session.flush()
    session.add(ClaimSource(claimId=claim.id, sourceId=source.id, quote=claim.text[:60], quoteCheck=check))


async def stage_with_claims(session: AsyncSession) -> tuple[ProcessStage, dict[str, uuid.UUID]]:
    craft = Craft(id=uuid.uuid4(), name="Media Test Printing", slug=f"Media-Test-{uuid.uuid4().hex[:8]}")
    session.add(craft)
    await session.flush()
    concept = Concept(id=uuid.uuid4(), craftId=craft.id, type="PROCESS_STAGE", name="Alum printing")
    process = Process(id=uuid.uuid4(), craftId=craft.id, name="Printing")
    session.add_all([concept, process])
    await session.flush()
    stage = ProcessStage(
        id=uuid.uuid4(), processId=process.id, ordinal=6, conceptId=concept.id, name="Alum printing"
    )
    session.add(stage)
    session.add(
        CraftLocation(craftId=craft.id, precision="POINT", placeLabel="Ajrakhpur", evidenceLevel="REVIEWED")
    )
    await session.flush()
    ids = await planned_claims(session, concept)
    ids["material"] = await material_claim(session, stage)
    await session.commit()
    return stage, ids


CLAIM_PLAN = {
    "verified": ("VERIFIED", "APPROVED", "PASS", "OPEN"),
    "quoted": ("PROVISIONAL", "APPROVED", "PASS", "OPEN"),
    "unquoted": ("PROVISIONAL", "APPROVED", "NA", "OPEN"),
    "hypothesis": ("HYPOTHESIS", "APPROVED", "PASS", "OPEN"),
    "retracted": ("VERIFIED", "RETRACTED", "PASS", "OPEN"),
    "restricted": ("VERIFIED", "APPROVED", "PASS", "RESTRICTED"),
}


async def planned_claims(session: AsyncSession, concept: Concept) -> dict[str, uuid.UUID]:
    ids: dict[str, uuid.UUID] = {}
    for name, (level, status, check, source_sensitivity) in CLAIM_PLAN.items():
        claim = Claim(
            id=uuid.uuid4(),
            subjectType="CONCEPT",
            subjectId=concept.id,
            predicate="PROCESS_STAGE",
            text=f"The {name} fact about alum.",
            evidenceLevel=level,
            origin="IMPORT",
            status=status,
        )
        session.add(claim)
        await session.flush()
        await cited(session, claim, check=check, sensitivity=source_sensitivity)
        ids[name] = claim.id
    return ids


async def material_claim(session: AsyncSession, stage: ProcessStage) -> uuid.UUID:
    claim = Claim(
        id=uuid.uuid4(),
        subjectType="CONCEPT",
        subjectId=uuid.uuid4(),
        predicate="MATERIAL",
        text="Alum is the mordant.",
        evidenceLevel="REVIEWED",
        origin="IMPORT",
    )
    material = Material(id=uuid.uuid4(), name="Alum", nameNorm=f"alum-{uuid.uuid4().hex[:6]}")
    session.add_all([claim, material])
    await session.flush()
    await cited(session, claim, check="NA")
    session.add(StageMaterial(stageId=stage.id, materialId=material.id, claimId=claim.id))
    await session.flush()
    return claim.id


def record(
    owner: User, stage: ProcessStage, claim_ids: tuple[uuid.UUID, ...], **changes: object
) -> JobRecord:
    base = JobRecord(
        id=uuid.uuid4(),
        kind="IMAGE",
        status="QUEUED",
        requested_by=owner.id,
        stage_id=stage.id,
        claim_ids=claim_ids,
        style_hint=None,
        prompt="Draw one stage.",
        prompt_hash="c" * 64,
        model="gemini-3.1-flash-image",
        alt_text="Alum is the mordant.",
        attempts=0,
        asset_id=None,
        hold_id=uuid.uuid4(),
        bundle={"mac": "x"},
        error=None,
        created_at=NOW,
        updated_at=NOW,
    )
    return replace(base, **changes)


def limits(allowance: int | None = 5, max_active: int = 3) -> CreateLimits:
    return CreateLimits(allowance=allowance, max_active=max_active, now=NOW)


async def queued(
    media: SqlMediaStore, owner: User, stage: ProcessStage, claim_ids: tuple, **kw: object
) -> JobRecord:
    job = record(owner, stage, claim_ids)
    new = NewJob(job, f"media:{uuid.uuid4().hex}", (await media.stage(stage.id)).craft.id, unit_entry(job))
    assert await media.create(new, kw.get("limits", limits())) is Created.CREATED
    return job


async def test_stored_stage_claims_give_the_contract_claim_set(stores: Stores) -> None:
    media, _, session = stores
    stage, ids = await stage_with_claims(session)
    facts = await media.stage(stage.id)
    assert facts is not None and facts.craft.place.locality == "Ajrakhpur"
    assert facts.craft.place_names == ("Ajrakhpur",)
    found = await media.stage_claims([stage.id])
    chosen = [c.id for c in claim_set(found[stage.id], acls=("PUBLIC",))]
    assert chosen == [ids["verified"], ids["material"], ids["quoted"]]


async def test_a_created_job_holds_one_unit_and_one_queue_row(stores: Stores) -> None:
    media, _, session = stores
    stage, ids = await stage_with_claims(session)
    owner = await user(session)
    job = record(owner, stage, (ids["verified"], ids["quoted"]))
    new = NewJob(job, "media:" + "d" * 64, (await media.stage(stage.id)).craft.id, unit_entry(job))
    assert await media.create(new, limits()) is Created.CREATED
    assert await media.create(new, limits()) is Created.REPEATED
    stored = await media.job_by_key("media:" + "d" * 64)
    assert stored is not None and stored.hold_id == job.hold_id and stored.alt_text == job.alt_text
    queue = (await session.execute(select(Job).where(Job.idempotencyKey == queue_key(job.id)))).scalar_one()
    assert (queue.queue, queue.status, queue.maxAttempts) == ("media.image", "QUEUED", 3)
    assert await media.units_used(owner.id, "IMAGE", NOW) == 1
    assert await media.active_jobs(owner.id) == 1


async def test_the_allowance_and_the_open_job_limit_hold_inside_the_lock(stores: Stores) -> None:
    media, _, session = stores
    stage, ids = await stage_with_claims(session)
    owner = await user(session)
    claim_ids = (ids["verified"], ids["quoted"])
    craft_id = (await media.stage(stage.id)).craft.id
    first = record(owner, stage, claim_ids)
    assert (
        await media.create(NewJob(first, "media:" + "1" * 64, craft_id, unit_entry(first)), limits(1))
        is Created.CREATED
    )
    second = record(owner, stage, claim_ids)
    assert (
        await media.create(NewJob(second, "media:" + "2" * 64, craft_id, unit_entry(second)), limits(1))
        is Created.NO_UNITS
    )
    assert (
        await media.create(NewJob(second, "media:" + "3" * 64, craft_id, unit_entry(second)), limits(9, 1))
        is Created.BUSY
    )


async def test_claims_respect_the_image_concurrency_of_four(stores: Stores) -> None:
    media, queue, session = stores
    stage, ids = await stage_with_claims(session)
    owner = await user(session)
    jobs = [
        await queued(media, owner, stage, (ids["verified"], ids["quoted"]), limits=limits(None, 99))
        for _ in range(6)
    ]
    first = await queue.claim("IMAGE", limit=10, worker_id="w1")
    assert len(first) == 4 and set(first) <= {job.id for job in jobs}
    assert await queue.claim("IMAGE", limit=10, worker_id="w2") == []
    running = await queue.job(first[0])
    assert running is not None and (running.status, running.attempts) == ("RUNNING", 1)
    await queue.retry(first[0], error="timeout", run_after=NOW - timedelta(seconds=1))
    assert len(await queue.claim("IMAGE", limit=10, worker_id="w1")) == 1


async def test_success_stores_the_labelled_asset_and_links_the_job(stores: Stores) -> None:
    media, queue, session = stores
    stage, ids = await stage_with_claims(session)
    owner = await user(session)
    job = await queued(media, owner, stage, (ids["verified"], ids["quoted"]))
    [claimed] = await queue.claim("IMAGE", limit=1, worker_id="w1")
    await queue.forget_hold(claimed)
    asset = NewAsset(
        id=uuid.uuid4(),
        s3_key=f"media/{owner.id}/{uuid.uuid4().hex}/KalaVigyan_Generated-Image_2026-11-16_1430_Media-Test_Image_Step-06.png",
        mime="image/png",
        size=2048,
        width=1024,
        height=1024,
        duration_seconds=None,
        model="gemini-3.1-flash-image",
        alt_text="Alum is the mordant.",
        depicts_named_cluster=False,
    )
    await queue.succeed(claimed, asset, cost_usd=Decimal("0.067350"), billed_tokens=1180)
    done = await media.job(job.id)
    assert done is not None and (done.status, done.asset_id, done.hold_id) == ("SUCCEEDED", asset.id, None)
    stored = await media.asset(asset.id)
    assert stored is not None and (stored.model, stored.visibility, stored.job_id) == (
        "gemini-3.1-flash-image",
        "PRIVATE",
        job.id,
    )
    row = await session.get(MediaAsset, asset.id)
    assert row is not None and row.label == "AI illustration"
    assert await media.shared_asset(job.prompt_hash) is None
    row.visibility = "CRAFT_SHARED"
    await session.commit()
    shared = await media.shared_asset(job.prompt_hash)
    assert shared is not None and shared.id == asset.id


async def test_the_hold_of_a_queued_job_is_renewed_and_a_running_one_is_not(stores: Stores) -> None:
    media, queue, session = stores
    stage, ids = await stage_with_claims(session)
    owner = await user(session)
    waiting = await queued(media, owner, stage, (ids["verified"], ids["quoted"]))
    running = await queued(media, owner, stage, (ids["verified"], ids["quoted"]))
    held_at = NOW - timedelta(minutes=10)
    holds = {
        job.id: UsageEvent(task="IMAGE", outcome="RESERVED", createdAt=held_at) for job in (waiting, running)
    }
    session.add_all(holds.values())
    await session.flush()
    for job_id, hold in holds.items():
        row = await session.get(MediaJob, job_id)
        row.params = {**(row.params or {}), "holdId": str(hold.id)}
    (await session.get(MediaJob, running.id)).status = "RUNNING"
    await session.commit()
    assert await queue.renew_holds(NOW - timedelta(minutes=7, seconds=30)) == 1
    await session.refresh(holds[waiting.id])
    await session.refresh(holds[running.id])
    assert holds[waiting.id].createdAt > held_at and holds[running.id].createdAt == held_at


async def test_a_refund_counts_on_the_day_its_job_was_asked_for(stores: Stores) -> None:
    media, queue, session = stores
    stage, ids = await stage_with_claims(session)
    owner = await user(session)
    job = await queued(media, owner, stage, (ids["verified"], ids["quoted"]))
    await queue.claim("IMAGE", limit=1, worker_id="w1")
    asked = NOW - timedelta(days=1)
    await queue.fail(
        job.id, status="FAILED", error="timeout", refund=refund_entry(replace(job, created_at=asked))
    )
    refunded = await session.scalar(
        select(QuotaLedger.createdAt).where(QuotaLedger.idempotencyKey == f"media-refund:{job.id}")
    )
    assert refunded == asked
    assert await media.units_used(owner.id, "IMAGE", NOW) == 1


async def test_a_failure_refunds_the_unit_once(stores: Stores) -> None:
    media, queue, session = stores
    stage, ids = await stage_with_claims(session)
    owner = await user(session)
    job = await queued(media, owner, stage, (ids["verified"], ids["quoted"]))
    await queue.claim("IMAGE", limit=1, worker_id="w1")
    await queue.fail(job.id, status="BLOCKED", error="refusal", refund=refund_entry(job))
    await queue.fail(job.id, status="BLOCKED", error="refusal", refund=refund_entry(job))
    assert await media.units_used(owner.id, "IMAGE", NOW) == 0
    keys = (
        await session.scalars(select(QuotaLedger.idempotencyKey).where(QuotaLedger.userId == owner.id))
    ).all()
    assert sorted(keys) == sorted([f"media:{job.id}", f"media-refund:{job.id}"])
    row = await session.get(MediaJob, job.id)
    queue_row = (
        await session.execute(select(Job).where(Job.idempotencyKey == queue_key(job.id)))
    ).scalar_one()
    assert (row.status, queue_row.status, queue_row.lockedAt) == ("BLOCKED", "BLOCKED", None)


async def test_a_stale_running_job_is_handed_back_once(stores: Stores) -> None:
    media, queue, session = stores
    stage, ids = await stage_with_claims(session)
    owner = await user(session)
    job = await queued(media, owner, stage, (ids["verified"], ids["quoted"]))
    await queue.claim("IMAGE", limit=1, worker_id="w1")
    assert await queue.stale(datetime.now(UTC) + timedelta(minutes=1)) == [job.id]
    assert await queue.stale(datetime.now(UTC) - timedelta(minutes=10)) == []
