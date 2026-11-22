from __future__ import annotations

import uuid
import zlib
from collections.abc import Sequence
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from app.media.records import (
    AssetRecord,
    CitationFacts,
    ClaimFacts,
    CraftFacts,
    Created,
    CreateLimits,
    JobRecord,
    NewAsset,
    NewJob,
    StageFacts,
)
from app.providers.base import MediaResult
from app.providers.catalogue import AiTask
from app.providers.media_router import MediaAsk, MediaCall
from app.providers.quota import LedgerEntry
from app.providers.router import RouterError
from app.research.crafts import CraftRef
from app.services.naming import PlaceParts
from app.services.object_store import PresignedGet

NOW = datetime(2026, 11, 16, 9, 0, 5, tzinfo=UTC)
STAGE_ID = uuid.UUID("575d3427-7a90-568d-87d5-bb0f1c602591")
OTHER_STAGE_ID = uuid.UUID("eb895bd5-83a3-511a-9e64-ba7e452afea8")
THIN_STAGE_ID = uuid.UUID("0c4f8a52-6f43-4b55-9d26-3f1a6c0d9e11")
CRAFT_ID = uuid.UUID("2f0d8e33-17b4-4f0e-a6a8-0c5d7b1e9a40")
USER_ID = uuid.UUID("66ceb1a0-fce2-5527-b3c8-c9c4507c60b9")
PA_CLAIM = uuid.UUID("9a3c214f-f54f-5f76-a5b7-88aa6a363489")
ALUM_CLAIM = uuid.UUID("1dcf0fe9-1f1c-518e-868b-5e54bcd44a2e")
PA_TEXT = (
    "Pa, a smooth paste of alum in tamarind-seed paste, is printed with blocks patterned for the "
    "mavi areas where red is required."
)
ALUM_TEXT = "Alum acts as the mordant that fixes the red dye to the cotton."
BUNDLE_KEY = b"test-only-media-bundle-key-0123456789abcdef"
PUBLIC_ACL = "PUBLIC"
AJRAKH = CraftRef(slug="Kutch-Ajrakh", name="Kutch Ajrakh", path="/crafts/Kutch-Ajrakh")
BUCKET_HOST = "https://kalavigyan-media-example.s3.ap-south-1.amazonaws.com"


def craft(*, active: bool = True, names: tuple[str, ...] = ("Ajrakhpur", "Kachchh")) -> CraftFacts:
    place = PlaceParts(locality="Ajrakhpur", district="Kachchh", state="Gujarat")
    return CraftFacts(CRAFT_ID, AJRAKH, active, place, names)


def stage(stage_id: uuid.UUID = STAGE_ID, *, ordinal: int = 6, active: bool = True) -> StageFacts:
    return StageFacts(stage_id, ordinal, "Pa (alum mordant printing for red)", craft(active=active))


def passing(acl: str | None = PUBLIC_ACL) -> CitationFacts:
    return CitationFacts(quote_check="PASS", restricted=False, chunk_acl=acl)


def unchecked(acl: str | None = PUBLIC_ACL) -> CitationFacts:
    return CitationFacts(quote_check="NA", restricted=False, chunk_acl=acl)


def claim(
    claim_id: uuid.UUID,
    text: str,
    *,
    level: str = "REVIEWED",
    status: str = "APPROVED",
    sensitivity: str = "OPEN",
    own: bool = True,
    citations: tuple[CitationFacts, ...] = (passing(),),
) -> ClaimFacts:
    return ClaimFacts(claim_id, text, level, status, sensitivity, own, citations)


def stage_claims() -> list[ClaimFacts]:
    return [claim(PA_CLAIM, PA_TEXT, level="VERIFIED"), claim(ALUM_CLAIM, ALUM_TEXT, own=False)]


def png_bytes(width: int = 1024, height: int = 1024) -> bytes:
    header = width.to_bytes(4) + height.to_bytes(4) + bytes([8, 6, 0, 0, 0])
    ihdr = b"IHDR" + header
    chunk = len(header).to_bytes(4) + ihdr + zlib.crc32(ihdr).to_bytes(4)
    end = (0).to_bytes(4) + b"IEND" + zlib.crc32(b"IEND").to_bytes(4)
    return b"\x89PNG\r\n\x1a\n" + chunk + end


def media_result(data: bytes, mime: str = "image/png", *, output_tokens: int | None = 1120) -> MediaResult:
    return MediaResult(
        data=data,
        mime=mime,
        input_tokens=300,
        output_tokens=output_tokens,
        media_tokens=output_tokens,
        provider_ref="interaction-1",
        served_model="gemini-3.1-flash-image",
    )


@dataclass
class FakeLinks:
    calls: list[tuple[str, str]] = field(default_factory=list)

    def presigned_get(self, key: str, *, disposition: str, seconds: int, now: datetime) -> PresignedGet:
        self.calls.append((key, disposition))
        return PresignedGet(
            url=f"{BUCKET_HOST}/{key}?X-Amz-Expires={seconds}&X-Amz-Signature=fixture",
            expires_at=now + timedelta(seconds=seconds),
        )


@dataclass
class FakeBudget:
    model: str | None = "gemini-3.1-flash-image"
    open: bool = True
    refuse_hold: RouterError | None = None
    holds: list[MediaAsk] = field(default_factory=list)
    released: list[uuid.UUID] = field(default_factory=list)

    async def first_model(self, task: AiTask) -> str | None:
        return self.model

    async def available(self, ask: MediaAsk) -> bool:
        return self.open

    async def hold(self, ask: MediaAsk) -> uuid.UUID:
        if self.refuse_hold is not None:
            raise self.refuse_hold
        self.holds.append(ask)
        return uuid.uuid5(uuid.NAMESPACE_URL, f"hold-{len(self.holds)}")

    async def release(self, event_id: uuid.UUID) -> None:
        self.released.append(event_id)


@dataclass
class FakeGenerator:
    outcomes: list[MediaCall | BaseException] = field(default_factory=list)
    asks: list[MediaAsk] = field(default_factory=list)
    released: list[uuid.UUID] = field(default_factory=list)

    async def generate(self, ask: MediaAsk) -> MediaCall:
        self.asks.append(ask)
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, BaseException):
            raise outcome
        return outcome

    async def release(self, event_id: uuid.UUID) -> None:
        self.released.append(event_id)


@dataclass
class FakeObjects:
    puts: dict[str, tuple[bytes, str]] = field(default_factory=dict)

    async def put(self, key: str, body: bytes, *, content_type: str) -> None:
        self.puts[key] = (body, content_type)


def media_call(result: MediaResult, *, model: str = "gemini-3.1-flash-image") -> MediaCall:
    return MediaCall(result, "GEMINI", model, uuid.uuid4(), Decimal("0.067350"))


@dataclass
class MemoryMedia:
    stages: dict[uuid.UUID, StageFacts] = field(default_factory=dict)
    claims: dict[uuid.UUID, list[ClaimFacts]] = field(default_factory=dict)
    jobs: dict[uuid.UUID, JobRecord] = field(default_factory=dict)
    keys: dict[str, uuid.UUID] = field(default_factory=dict)
    assets: dict[uuid.UUID, AssetRecord] = field(default_factory=dict)
    ledger: dict[str, LedgerEntry] = field(default_factory=dict)
    queued: list[uuid.UUID] = field(default_factory=list)
    retries: list[tuple[uuid.UUID, str, datetime]] = field(default_factory=list)
    stale_ids: list[uuid.UUID] = field(default_factory=list)
    now: datetime = NOW

    async def craft_stages(self, slug: str) -> tuple[CraftFacts, list[StageFacts]] | None:
        found = [s for s in self.stages.values() if s.craft.ref.slug == slug]
        return (found[0].craft, found) if found else None

    async def stage(self, stage_id: uuid.UUID) -> StageFacts | None:
        return self.stages.get(stage_id)

    async def stage_claims(self, stage_ids: Sequence[uuid.UUID]) -> dict[uuid.UUID, list[ClaimFacts]]:
        return {stage_id: list(self.claims.get(stage_id, [])) for stage_id in stage_ids}

    async def units_used(self, user_id: uuid.UUID, kind: str, now: datetime) -> int:
        return max(
            0, sum(e.units for e in self.ledger.values() if e.user_id == user_id and e.resource == kind)
        )

    async def active_jobs(self, user_id: uuid.UUID) -> int:
        return sum(
            1 for j in self.jobs.values() if j.requested_by == user_id and j.status in ("QUEUED", "RUNNING")
        )

    async def job_by_key(self, key_hash: str) -> JobRecord | None:
        job_id = self.keys.get(key_hash)
        return None if job_id is None else self.jobs[job_id]

    async def job(self, job_id: uuid.UUID) -> JobRecord | None:
        return self.jobs.get(job_id)

    async def asset(self, asset_id: uuid.UUID) -> AssetRecord | None:
        return self.assets.get(asset_id)

    async def shared_asset(self, prompt_hash: str) -> AssetRecord | None:
        for asset in self.assets.values():
            producer = self.jobs.get(asset.job_id) if asset.job_id else None
            if producer and producer.prompt_hash == prompt_hash and asset.visibility == "CRAFT_SHARED":
                return asset
        return None

    async def create(self, job: NewJob, limits: CreateLimits) -> Created:
        record = job.record
        if job.key_hash in self.keys:
            return Created.REPEATED
        if await self.active_jobs(record.requested_by) >= limits.max_active:
            return Created.BUSY
        used = await self.units_used(record.requested_by, record.kind, limits.now)
        if limits.allowance is not None and used + 1 > limits.allowance:
            return Created.NO_UNITS
        self._insert(job)
        if job.ledger is not None:
            self.ledger.setdefault(job.ledger.key, job.ledger)
        self.queued.append(record.id)
        return Created.CREATED

    async def create_cached(self, job: NewJob) -> Created:
        if job.key_hash in self.keys:
            return Created.REPEATED
        self._insert(job)
        return Created.CREATED

    async def stale(self, older_than: datetime) -> list[uuid.UUID]:
        found, self.stale_ids = self.stale_ids, []
        return found

    async def claim(self, kind: str, *, limit: int, worker_id: str) -> list[uuid.UUID]:
        ready = [i for i in self.queued if self.jobs[i].kind == kind][:limit]
        for job_id in ready:
            self.queued.remove(job_id)
            job = self.jobs[job_id]
            self.jobs[job_id] = replace(job, status="RUNNING", attempts=job.attempts + 1)
        return ready

    async def forget_hold(self, job_id: uuid.UUID) -> None:
        self.jobs[job_id] = replace(self.jobs[job_id], hold_id=None)

    async def succeed(
        self, job_id: uuid.UUID, asset: NewAsset, *, cost_usd: Decimal, billed_tokens: int | None
    ) -> None:
        self.assets[asset.id] = AssetRecord(
            id=asset.id,
            job_id=job_id,
            s3_key=asset.s3_key,
            mime=asset.mime,
            width=asset.width,
            height=asset.height,
            duration_seconds=asset.duration_seconds,
            model=asset.model,
            alt_text=asset.alt_text,
            visibility="PRIVATE",
            created_at=self.now,
        )
        self.jobs[job_id] = replace(self.jobs[job_id], status="SUCCEEDED", asset_id=asset.id, error=None)

    async def retry(self, job_id: uuid.UUID, *, error: str, run_after: datetime) -> None:
        self.retries.append((job_id, error, run_after))
        self.jobs[job_id] = replace(self.jobs[job_id], status="QUEUED", error=error)
        self.queued.append(job_id)

    async def fail(self, job_id: uuid.UUID, *, status: str, error: str, refund: LedgerEntry) -> None:
        self.jobs[job_id] = replace(self.jobs[job_id], status=status, error=error)
        self.ledger.setdefault(refund.key, refund)

    def _insert(self, job: NewJob) -> None:
        self.jobs[job.record.id] = job.record
        self.keys[job.key_hash] = job.record.id
