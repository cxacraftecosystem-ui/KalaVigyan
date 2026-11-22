from __future__ import annotations

import asyncio
import logging
import uuid
from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Protocol

from app.core.errors import SPEND_REFUSAL_KIND, ExternalFailure, InvalidInput, Refused
from app.core.logging import request_id_scope
from app.providers.media_router import MediaAsk, MediaCall
from app.providers.router import RouterError
from app.schemas.media import JOB_RETRIES, JOB_TIMEOUT_SECONDS
from app.services.craft_ai_media import page_copy_key
from app.services.naming import MediaName, generated_media_file_name, media_key

from .bundle import opened_bundle
from .ledger import refund_entry
from .output import checked_output
from .prompt import media_ask, names_a_place
from .records import JobRecord, NewAsset, QueueStore, StageFacts

__all__ = [
    "FINAL_ROUTER_KINDS",
    "RETRY_DELAY_SECONDS",
    "Generator",
    "ObjectWriter",
    "RunnerDeps",
    "abandon_job",
    "run_job",
]

logger = logging.getLogger(__name__)

RETRY_DELAY_SECONDS = 15
FINAL_ROUTER_KINDS = frozenset({"bad_request", SPEND_REFUSAL_KIND, "no_route", "unsupported"})
BLOCKED_KIND = "refusal"


class Generator(Protocol):
    async def generate(self, ask: MediaAsk) -> MediaCall: ...

    async def release(self, event_id: uuid.UUID) -> None: ...


class ObjectWriter(Protocol):
    async def put(self, key: str, body: bytes, *, content_type: str) -> None: ...


@dataclass(frozen=True)
class RunnerDeps:
    store: QueueStore
    generator: Generator
    objects: ObjectWriter
    bundle_key: bytes
    clock: Callable[[], datetime]
    timeout_seconds: float = JOB_TIMEOUT_SECONDS


@dataclass(frozen=True)
class _Made:
    asset: NewAsset
    cost_usd: Decimal
    billed_tokens: int | None


async def run_job(deps: RunnerDeps, job_id: uuid.UUID) -> str:
    job = await deps.store.job(job_id)
    if job is None:
        raise InvalidInput(f"Media job {job_id} was claimed but cannot be read")
    with request_id_scope(f"media-{job.id.hex}"):
        return await _run(deps, job)


async def abandon_job(deps: RunnerDeps, job_id: uuid.UUID) -> str:
    job = await deps.store.job(job_id)
    if job is None:
        raise InvalidInput(f"Media job {job_id} was abandoned but cannot be read")
    with request_id_scope(f"media-{job.id.hex}"):
        return await _retry_or_fail(deps, await _released(deps, job), "abandoned")


async def _run(deps: RunnerDeps, job: JobRecord) -> str:
    try:
        role = opened_bundle(deps.bundle_key, job.bundle, job, now=deps.clock())
    except Refused as refused:
        logger.warning("media bundle refused", extra={"jobId": str(job.id), "reason": refused.reason})
        return await _finish(deps, job, "FAILED", refused.reason)
    stage = await deps.store.stage(job.stage_id) if job.stage_id else None
    if stage is None:
        return await _finish(deps, job, "FAILED", "stage_missing")
    try:
        generated_media_file_name(_media_name(job, stage, deps.clock()))
    except InvalidInput:
        return await _finish(deps, job, "FAILED", "unnameable")
    return await _attempt(deps, await _released(deps, job), stage, role)


async def _attempt(deps: RunnerDeps, job: JobRecord, stage: StageFacts, role: str) -> str:
    try:
        async with asyncio.timeout(deps.timeout_seconds):
            made = await _made(deps, job, stage, role)
    except RouterError as error:
        if error.kind == BLOCKED_KIND:
            return await _finish(deps, job, "BLOCKED", error.kind)
        if error.kind in FINAL_ROUTER_KINDS:
            return await _finish(deps, job, "FAILED", error.kind)
        return await _retry_or_fail(deps, job, error.kind)
    except TimeoutError:
        return await _retry_or_fail(deps, job, "timeout")
    except (InvalidInput, ExternalFailure) as error:
        logger.warning("media attempt failed", extra={"jobId": str(job.id), "error": str(error)[:300]})
        return await _retry_or_fail(deps, job, "output" if isinstance(error, InvalidInput) else error.kind)
    await deps.store.succeed(job.id, made.asset, cost_usd=made.cost_usd, billed_tokens=made.billed_tokens)
    return "SUCCEEDED"


async def _made(deps: RunnerDeps, job: JobRecord, stage: StageFacts, role: str) -> _Made:
    call = await deps.generator.generate(media_ask(job.kind, job.prompt, user_id=job.requested_by, role=role))
    output = checked_output(job.kind, call.result)
    leaf = generated_media_file_name(_media_name(job, stage, deps.clock()))
    key = media_key(job.requested_by, leaf)
    await deps.objects.put(key, output.data, content_type=output.mime)
    page_key = page_copy_key(output.data, key)
    await deps.objects.put(page_key, output.data, content_type=output.mime)
    asset = NewAsset(
        id=uuid.uuid4(),
        s3_key=key,
        mime=output.mime,
        size=len(output.data),
        width=output.width,
        height=output.height,
        duration_seconds=output.duration_seconds,
        model=call.model,
        alt_text=job.alt_text,
        depicts_named_cluster=names_a_place(job.prompt, stage.craft.place_names),
        page_key=page_key,
    )
    return _Made(asset=asset, cost_usd=call.cost_usd, billed_tokens=call.result.output_tokens)


def _media_name(job: JobRecord, stage: StageFacts, moment: datetime) -> MediaName:
    return MediaName(
        kind=job.kind,
        generated_at=moment,
        place=stage.craft.place,
        craft=stage.craft.ref.name,
        stage_name=stage.name,
        stage_ordinal=stage.ordinal,
    )


async def _released(deps: RunnerDeps, job: JobRecord) -> JobRecord:
    if job.hold_id is None:
        return job
    await deps.generator.release(job.hold_id)
    await deps.store.forget_hold(job.id)
    return replace(job, hold_id=None)


async def _retry_or_fail(deps: RunnerDeps, job: JobRecord, reason: str) -> str:
    if job.attempts >= JOB_RETRIES + 1:
        return await _finish(deps, job, "FAILED", reason)
    run_after = deps.clock() + timedelta(seconds=RETRY_DELAY_SECONDS * max(1, job.attempts))
    await deps.store.retry(job.id, error=reason, run_after=run_after)
    return "QUEUED"


async def _finish(deps: RunnerDeps, job: JobRecord, status: str, reason: str) -> str:
    released = await _released(deps, job)
    await deps.store.fail(released.id, status=status, error=reason, refund=refund_entry(released))
    return status
