from __future__ import annotations

import hashlib
import uuid
from dataclasses import dataclass, replace
from datetime import datetime
from typing import Any, Protocol

from app.core.daily_allowances import daily_allowance
from app.core.errors import SPEND_REFUSAL_KIND, AppError
from app.core.roles import PROFESSOR, Capability, can, has_rank, role_value
from app.providers.catalogue import AiTask
from app.providers.media_router import MediaAsk
from app.providers.quota import remaining_today, seconds_until_next_day
from app.providers.router import RouterError
from app.research.retrieval import chunk_acls_for
from app.schemas.media import (
    MAX_ACTIVE_JOBS_PER_USER,
    MediaJobRequest,
    MediaJobView,
    MediaKindOption,
    MediaOptions,
    MediaStageOption,
)

from .bundle import sealed_bundle
from .claim_set import claim_set, enough_claims
from .ledger import unit_entry
from .prompt import alt_text, build_prompt, media_ask
from .records import (
    ClaimFacts,
    CraftFacts,
    Created,
    CreateLimits,
    JobRecord,
    MediaStore,
    NewJob,
    StageFacts,
)
from .views import AssetLinks, is_cached, job_view

__all__ = [
    "BUSY_RETRY_SECONDS",
    "MEDIA_CAPABILITIES",
    "REFUSALS",
    "MediaBudget",
    "MediaDeps",
    "MediaRefused",
    "idempotency_hash",
    "media_options",
    "submit_job",
    "visible_job",
]

MEDIA_KINDS = ("IMAGE", "VIDEO")
MEDIA_CAPABILITIES = {"IMAGE": Capability.GENERATE_IMAGE, "VIDEO": Capability.GENERATE_VIDEO}
BUSY_RETRY_SECONDS = 30
REFUSALS = {
    "capability": "Your role can't make this kind of illustration.",
    "not_found": "That stage isn't available.",
    "too_few_claims": "This stage doesn't have enough cited facts to illustrate yet.",
    "no_units": "You've used today's allowance. It resets at midnight IST.",
    "busy": "You already have three illustrations in progress. Try again shortly.",
    "key_conflict": "This request key was already used for a different request.",
    "not_configured": "Illustrations can't be made right now.",
    "unshared": "This illustration is no longer shared.",
    "budget": "The monthly budget for images and video has been reached.",
}


class MediaRefused(AppError):
    def __init__(self, reason: str, message: str | None = None, *, retry_after: int | None = None) -> None:
        super().__init__(message or REFUSALS[reason])
        self.reason = reason
        self.message = message or REFUSALS[reason]
        self.retry_after = retry_after


class MediaBudget(Protocol):
    async def first_model(self, task: AiTask) -> str | None: ...

    async def available(self, ask: MediaAsk) -> bool: ...

    async def hold(self, ask: MediaAsk) -> uuid.UUID: ...

    async def release(self, event_id: uuid.UUID) -> None: ...


@dataclass(frozen=True)
class MediaDeps:
    store: MediaStore
    budget: MediaBudget
    links: AssetLinks | None
    bundle_key: bytes | None
    now: datetime


def idempotency_hash(user_id: uuid.UUID, key: str) -> str:
    return "media:" + hashlib.sha256(f"{user_id}:{key}".encode()).hexdigest()


async def media_options(deps: MediaDeps, user: Any, craft_slug: str) -> MediaOptions:
    found = await deps.store.craft_stages(craft_slug)
    if found is None or not _craft_visible(found[0], user):
        raise MediaRefused("not_found")
    craft, stages = found
    kinds = await _offered_kinds(deps, user) if await _makeable(deps) else []
    offered = [option.kind for option in kinds]
    claims = await deps.store.stage_claims([stage.id for stage in stages]) if offered else {}
    acls = chunk_acls_for(user)
    return MediaOptions(
        craft=craft.ref,
        kinds=kinds,
        stages=[
            MediaStageOption(stage_id=stage.id, kinds=offered)
            for stage in stages
            if enough_claims(claim_set(claims.get(stage.id, []), acls=acls))
        ],
    )


async def submit_job(deps: MediaDeps, user: Any, request: MediaJobRequest) -> tuple[MediaJobView, bool]:
    if not can(user, MEDIA_CAPABILITIES[request.kind]):
        raise MediaRefused("capability")
    key_hash = idempotency_hash(user.id, request.idempotency_key)
    existing = await deps.store.job_by_key(key_hash)
    if existing is not None:
        return await _repeated(deps, user, existing, request), False
    stage = await _visible_stage(deps, user, request.stage_id)
    claims = await _stage_claim_set(deps, user, stage)
    model = await deps.budget.first_model(AiTask(request.kind))
    if model is None or deps.bundle_key is None or deps.links is None:
        raise MediaRefused("not_configured")
    job = _new_record(request, user, stage, claims, model=model, now=deps.now)
    shared = await deps.store.shared_asset(job.prompt_hash)
    if shared is not None:
        cached = replace(job, status="SUCCEEDED", asset_id=shared.id)
        return await _created_cached(deps, user, request, NewJob(cached, key_hash, stage.craft.id, None))
    new = NewJob(job, key_hash, stage.craft.id, unit_entry(job))
    return await _queued(deps, user, request, new, deps.bundle_key)


async def visible_job(deps: MediaDeps, user: Any, job_id: uuid.UUID) -> MediaJobView:
    job = await deps.store.job(job_id)
    if job is None or job.requested_by != user.id or job.stage_id is None:
        raise MediaRefused("not_found")
    stage = await deps.store.stage(job.stage_id)
    if stage is None:
        raise MediaRefused("not_found")
    asset = await deps.store.asset(job.asset_id) if job.asset_id else None
    if is_cached(job, asset) and asset is not None and asset.visibility != "CRAFT_SHARED":
        raise MediaRefused("unshared")
    if deps.links is None:
        raise MediaRefused("not_configured")
    return job_view(job, stage, asset, links=deps.links, now=deps.now)


async def _offered_kinds(deps: MediaDeps, user: Any) -> list[MediaKindOption]:
    kinds: list[MediaKindOption] = []
    for kind in MEDIA_KINDS:
        if not can(user, MEDIA_CAPABILITIES[kind]):
            continue
        left = remaining_today(user, kind, await deps.store.units_used(user.id, kind, deps.now))
        if left is not None and left < 1:
            continue
        if await deps.budget.available(media_ask(kind, "", user_id=user.id, role=role_value(user))):
            kinds.append(MediaKindOption(kind=kind, remaining_today=left))
    return kinds


async def _visible_stage(deps: MediaDeps, user: Any, stage_id: uuid.UUID) -> StageFacts:
    stage = await deps.store.stage(stage_id)
    if stage is None or not _craft_visible(stage.craft, user):
        raise MediaRefused("not_found")
    return stage


async def _stage_claim_set(deps: MediaDeps, user: Any, stage: StageFacts) -> tuple[ClaimFacts, ...]:
    found = await deps.store.stage_claims([stage.id])
    claims = claim_set(found.get(stage.id, []), acls=chunk_acls_for(user))
    if not enough_claims(claims):
        raise MediaRefused("too_few_claims")
    return claims


def _new_record(
    request: MediaJobRequest,
    user: Any,
    stage: StageFacts,
    claims: tuple[ClaimFacts, ...],
    *,
    model: str,
    now: datetime,
) -> JobRecord:
    prompt = build_prompt(request.kind, stage.name, claims, style_hint=request.style_hint, model=model)
    return JobRecord(
        id=uuid.uuid4(),
        kind=request.kind,
        status="QUEUED",
        requested_by=user.id,
        stage_id=stage.id,
        claim_ids=tuple(claim.id for claim in claims),
        style_hint=request.style_hint,
        prompt=prompt.text,
        prompt_hash=prompt.hash,
        model=model,
        alt_text=alt_text(claims),
        attempts=0,
        asset_id=None,
        hold_id=None,
        bundle=None,
        error=None,
        created_at=now,
        updated_at=now,
    )


async def _queued(
    deps: MediaDeps, user: Any, request: MediaJobRequest, new: NewJob, key: bytes
) -> tuple[MediaJobView, bool]:
    job = new.record
    if not await deps.store.worker_listening(deps.now):
        raise MediaRefused("not_configured")
    _refuse_without_units(user, job.kind, await deps.store.units_used(user.id, job.kind, deps.now), deps.now)
    if await deps.store.active_jobs(user.id) >= MAX_ACTIVE_JOBS_PER_USER:
        raise MediaRefused("busy", retry_after=BUSY_RETRY_SECONDS)
    role = role_value(user)
    hold = await _hold(deps, media_ask(job.kind, job.prompt, user_id=user.id, role=role))
    held = replace(job, hold_id=hold)
    sealed = replace(held, bundle=sealed_bundle(key, held, role=role, now=deps.now))
    limits = CreateLimits(
        allowance=daily_allowance(user, job.kind), max_active=MAX_ACTIVE_JOBS_PER_USER, now=deps.now
    )
    outcome = await deps.store.create(replace(new, record=sealed), limits)
    if outcome is Created.CREATED:
        return await visible_job(deps, user, sealed.id), True
    await deps.budget.release(hold)
    return await _not_created(deps, user, request, new.key_hash, outcome)


async def _created_cached(
    deps: MediaDeps, user: Any, request: MediaJobRequest, new: NewJob
) -> tuple[MediaJobView, bool]:
    outcome = await deps.store.create_cached(new)
    if outcome is Created.CREATED:
        return await visible_job(deps, user, new.record.id), False
    return await _not_created(deps, user, request, new.key_hash, outcome)


async def _not_created(
    deps: MediaDeps, user: Any, request: MediaJobRequest, key_hash: str, outcome: Created
) -> tuple[MediaJobView, bool]:
    if outcome is Created.NO_UNITS:
        raise MediaRefused("no_units", retry_after=seconds_until_next_day(deps.now))
    if outcome is Created.BUSY:
        raise MediaRefused("busy", retry_after=BUSY_RETRY_SECONDS)
    existing = await deps.store.job_by_key(key_hash)
    if existing is None:
        raise MediaRefused("key_conflict")
    return await _repeated(deps, user, existing, request), False


async def _repeated(deps: MediaDeps, user: Any, job: JobRecord, request: MediaJobRequest) -> MediaJobView:
    same = (job.kind, job.stage_id, job.style_hint) == (request.kind, request.stage_id, request.style_hint)
    if not same or job.requested_by != user.id:
        raise MediaRefused("key_conflict")
    return await visible_job(deps, user, job.id)


async def _hold(deps: MediaDeps, ask: MediaAsk) -> uuid.UUID:
    try:
        return await deps.budget.hold(ask)
    except RouterError as error:
        if error.kind == SPEND_REFUSAL_KIND:
            raise MediaRefused("budget", error.message) from None
        raise MediaRefused("not_configured") from None


async def _makeable(deps: MediaDeps) -> bool:
    return bool(deps.bundle_key and deps.links) and await deps.store.worker_listening(deps.now)


def _refuse_without_units(user: Any, kind: str, used: int, now: datetime) -> None:
    left = remaining_today(user, kind, used)
    if left is not None and left < 1:
        raise MediaRefused("no_units", retry_after=seconds_until_next_day(now))


def _craft_visible(craft: CraftFacts, user: Any) -> bool:
    return craft.active or has_rank(user, PROFESSOR)
