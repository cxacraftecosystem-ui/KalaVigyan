from __future__ import annotations

import uuid
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any, Protocol

from app.providers.quota import LedgerEntry
from app.research.crafts import CraftRef
from app.services.naming import PlaceParts

__all__ = [
    "JOB_KIND",
    "MEDIA_QUEUES",
    "AssetRecord",
    "CitationFacts",
    "ClaimFacts",
    "CraftFacts",
    "CreateLimits",
    "Created",
    "JobRecord",
    "MediaStore",
    "NewAsset",
    "NewJob",
    "QueueStore",
    "StageFacts",
]

JOB_KIND = "media.generate"
MEDIA_QUEUES: Mapping[str, str] = {"IMAGE": "media.image", "VIDEO": "media.video"}


@dataclass(frozen=True)
class CraftFacts:
    id: uuid.UUID
    ref: CraftRef
    active: bool
    place: PlaceParts
    place_names: tuple[str, ...]


@dataclass(frozen=True)
class StageFacts:
    id: uuid.UUID
    ordinal: int
    name: str
    craft: CraftFacts


@dataclass(frozen=True)
class CitationFacts:
    quote_check: str
    restricted: bool
    chunk_acl: str | None


@dataclass(frozen=True)
class ClaimFacts:
    id: uuid.UUID
    text: str
    level: str
    status: str
    sensitivity: str
    own: bool
    citations: tuple[CitationFacts, ...]


@dataclass(frozen=True)
class AssetRecord:
    id: uuid.UUID
    job_id: uuid.UUID | None
    s3_key: str
    mime: str
    width: int
    height: int
    duration_seconds: float | None
    model: str
    alt_text: str
    visibility: str
    created_at: datetime


@dataclass(frozen=True)
class JobRecord:
    id: uuid.UUID
    kind: str
    status: str
    requested_by: uuid.UUID | None
    stage_id: uuid.UUID | None
    claim_ids: tuple[uuid.UUID, ...]
    style_hint: str | None
    prompt: str
    prompt_hash: str
    model: str
    alt_text: str
    attempts: int
    asset_id: uuid.UUID | None
    hold_id: uuid.UUID | None
    bundle: Mapping[str, Any] | None
    error: str | None
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True)
class NewJob:
    record: JobRecord
    key_hash: str
    craft_id: uuid.UUID
    ledger: LedgerEntry | None


@dataclass(frozen=True)
class NewAsset:
    id: uuid.UUID
    s3_key: str
    mime: str
    size: int
    width: int
    height: int
    duration_seconds: float | None
    model: str
    alt_text: str
    depicts_named_cluster: bool
    page_key: str | None = None


@dataclass(frozen=True)
class CreateLimits:
    allowance: int | None
    max_active: int
    now: datetime


class Created(StrEnum):
    CREATED = "CREATED"
    REPEATED = "REPEATED"
    NO_UNITS = "NO_UNITS"
    BUSY = "BUSY"


class MediaStore(Protocol):
    async def craft_stages(self, slug: str) -> tuple[CraftFacts, list[StageFacts]] | None: ...

    async def stage(self, stage_id: uuid.UUID) -> StageFacts | None: ...

    async def stage_claims(self, stage_ids: Sequence[uuid.UUID]) -> dict[uuid.UUID, list[ClaimFacts]]: ...

    async def units_used(self, user_id: uuid.UUID, kind: str, now: datetime) -> int: ...

    async def worker_listening(self, now: datetime) -> bool: ...

    async def active_jobs(self, user_id: uuid.UUID) -> int: ...

    async def job_by_key(self, key_hash: str) -> JobRecord | None: ...

    async def job(self, job_id: uuid.UUID) -> JobRecord | None: ...

    async def asset(self, asset_id: uuid.UUID) -> AssetRecord | None: ...

    async def shared_asset(self, prompt_hash: str) -> AssetRecord | None: ...

    async def create(self, job: NewJob, limits: CreateLimits) -> Created: ...

    async def create_cached(self, job: NewJob) -> Created: ...


class QueueStore(Protocol):
    async def stale(self, older_than: datetime) -> list[uuid.UUID]: ...

    async def claim(self, kind: str, *, limit: int, worker_id: str) -> list[uuid.UUID]: ...

    async def renew_holds(self, older_than: datetime) -> int: ...

    async def job(self, job_id: uuid.UUID) -> JobRecord | None: ...

    async def stage(self, stage_id: uuid.UUID) -> StageFacts | None: ...

    async def forget_hold(self, job_id: uuid.UUID) -> None: ...

    async def succeed(
        self, job_id: uuid.UUID, asset: NewAsset, *, cost_usd: Decimal, billed_tokens: int | None
    ) -> None: ...

    async def retry(self, job_id: uuid.UUID, *, error: str, run_after: datetime) -> None: ...

    async def fail(self, job_id: uuid.UUID, *, status: str, error: str, refund: LedgerEntry) -> None: ...
