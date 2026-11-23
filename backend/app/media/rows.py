from __future__ import annotations

import uuid
from collections import defaultdict
from collections.abc import Sequence
from typing import Any

from sqlalchemy import false, select, true, union_all
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import InvalidInput
from app.models import (
    AdminDistrict,
    AdminState,
    Chunk,
    Claim,
    ClaimSource,
    Concept,
    Craft,
    CraftLocation,
    MediaAsset,
    MediaJob,
    Process,
    ProcessStage,
    Source,
    StageMaterial,
)
from app.research.crafts import CraftRef
from app.research.retrieval import RESTRICTED_SENSITIVITY, VISIBLE_SENSITIVITY
from app.services.citation_tiers import reading_acl
from app.services.group_names import craft_group_names
from app.services.knowledge_view import craft_ref

from .place import LocationFacts, media_place
from .records import AssetRecord, CitationFacts, ClaimFacts, CraftFacts, JobRecord, StageFacts

__all__ = [
    "ACTIVE_CRAFT",
    "STYLE_HINT_PARAM",
    "asset_record",
    "craft_facts",
    "job_params",
    "job_record",
    "stage_claims",
    "stage_facts",
]

ACTIVE_CRAFT = "ACTIVE"
STYLE_HINT_PARAM = "styleHint"
ALT_TEXT_PARAM = "altText"
HOLD_PARAM = "holdId"


def job_params(record: JobRecord) -> dict[str, Any]:
    params: dict[str, Any] = {STYLE_HINT_PARAM: record.style_hint, ALT_TEXT_PARAM: record.alt_text}
    if record.hold_id is not None:
        params[HOLD_PARAM] = str(record.hold_id)
    return params


def job_record(row: MediaJob) -> JobRecord:
    params = row.params or {}
    hold = params.get(HOLD_PARAM)
    return JobRecord(
        id=row.id,
        kind=row.kind,
        status=row.status,
        requested_by=row.requestedById,
        stage_id=row.stageId,
        claim_ids=tuple(row.claimIds or ()),
        style_hint=params.get(STYLE_HINT_PARAM),
        prompt=row.prompt or "",
        prompt_hash=row.promptHash or "",
        model=row.model or "",
        alt_text=params.get(ALT_TEXT_PARAM) or "",
        attempts=row.attempts,
        asset_id=row.assetId,
        hold_id=uuid.UUID(hold) if hold else None,
        bundle=row.bundle,
        error=row.error,
        created_at=row.createdAt,
        updated_at=row.updatedAt,
    )


def asset_record(row: MediaAsset) -> AssetRecord:
    if row.width is None or row.height is None or not row.model or not row.altText:
        raise InvalidInput(f"Media asset {row.id} lacks its size, model or alt text")
    return AssetRecord(
        id=row.id,
        job_id=row.jobId,
        s3_key=row.s3Key,
        mime=row.mime,
        width=row.width,
        height=row.height,
        duration_seconds=None if row.durationS is None else float(row.durationS),
        model=row.model,
        alt_text=row.altText,
        visibility=row.visibility,
        created_at=row.createdAt,
    )


async def craft_facts(session: AsyncSession, crafts: Sequence[Craft]) -> dict[uuid.UUID, CraftFacts]:
    statement = (
        select(
            CraftLocation.craftId,
            CraftLocation.id,
            CraftLocation.precision,
            CraftLocation.placeLabel,
            CraftLocation.evidenceLevel,
            AdminDistrict.name,
            AdminState.name,
        )
        .outerjoin(AdminDistrict, AdminDistrict.lgd == CraftLocation.districtLgd)
        .outerjoin(AdminState, AdminState.lgd == CraftLocation.stateLgd)
        .where(CraftLocation.craftId.in_([craft.id for craft in crafts]))
    )
    located: dict[uuid.UUID, list[LocationFacts]] = defaultdict(list)
    for craft_id, location_id, precision, label, level, district, state in (
        await session.execute(statement)
    ).all():
        located[craft_id].append(LocationFacts(str(location_id), precision, label, level, district, state))
    groups = await craft_group_names(session, [craft.id for craft in crafts])
    facts: dict[uuid.UUID, CraftFacts] = {}
    for craft in crafts:
        place, names = media_place(located[craft.id], list(craft.stateOfPractice or []))
        ref = CraftRef.model_validate(craft_ref(craft))
        active = craft.status == ACTIVE_CRAFT
        facts[craft.id] = CraftFacts(craft.id, ref, active, place, names, groups.get(craft.id, ()))
    return facts


async def stage_facts(session: AsyncSession, stage_ids: Sequence[uuid.UUID]) -> dict[uuid.UUID, StageFacts]:
    rows = (
        await session.execute(
            select(ProcessStage, Craft)
            .join(Process, Process.id == ProcessStage.processId)
            .join(Craft, Craft.id == Process.craftId)
            .where(ProcessStage.id.in_(list(stage_ids)))
        )
    ).all()
    crafts = await craft_facts(session, list({craft.id: craft for _, craft in rows}.values()))
    return {
        stage.id: StageFacts(stage.id, stage.ordinal, stage.name, crafts[craft.id]) for stage, craft in rows
    }


async def stage_claims(
    session: AsyncSession, stage_ids: Sequence[uuid.UUID]
) -> dict[uuid.UUID, list[ClaimFacts]]:
    links = (await session.execute(_claim_links(stage_ids))).all()
    claim_ids = list({link.claim_id for link in links})
    claims = {
        row.id: row
        for row in (
            await session.execute(
                select(Claim.id, Claim.text, Claim.evidenceLevel, Claim.status, Claim.sensitivity).where(
                    Claim.id.in_(claim_ids)
                )
            )
        ).all()
    }
    citations = await _citations(session, claim_ids)
    found: dict[uuid.UUID, list[ClaimFacts]] = defaultdict(list)
    for link in links:
        claim = claims.get(link.claim_id)
        if claim is not None:
            found[link.stage_id].append(
                ClaimFacts(
                    id=claim.id,
                    text=claim.text,
                    level=claim.evidenceLevel,
                    status=claim.status,
                    sensitivity=claim.sensitivity,
                    own=bool(link.own),
                    citations=citations.get(claim.id, ()),
                )
            )
    return dict(found)


def _claim_links(stage_ids: Sequence[uuid.UUID]) -> Any:
    own = (
        select(ProcessStage.id.label("stage_id"), Claim.id.label("claim_id"), true().label("own"))
        .join(Concept, Concept.id == ProcessStage.conceptId)
        .join(Claim, Claim.subjectId == Concept.id)
        .where(
            ProcessStage.id.in_(list(stage_ids)),
            Claim.subjectType == "CONCEPT",
            Concept.sensitivity == VISIBLE_SENSITIVITY,
        )
    )
    material = select(
        StageMaterial.stageId.label("stage_id"),
        StageMaterial.claimId.label("claim_id"),
        false().label("own"),
    ).where(StageMaterial.stageId.in_(list(stage_ids)), StageMaterial.claimId.is_not(None))
    return union_all(own, material)


async def _citations(
    session: AsyncSession, claim_ids: Sequence[uuid.UUID]
) -> dict[uuid.UUID, tuple[CitationFacts, ...]]:
    rows = (
        await session.execute(
            select(
                ClaimSource.claimId,
                ClaimSource.quoteCheck,
                Source.sensitivity,
                reading_acl(),
                Chunk.sensitivity,
            )
            .join(Source, Source.id == ClaimSource.sourceId)
            .outerjoin(Chunk, Chunk.id == ClaimSource.chunkId)
            .where(ClaimSource.claimId.in_(list(claim_ids)))
        )
    ).all()
    found: dict[uuid.UUID, list[CitationFacts]] = defaultdict(list)
    for claim_id, quote_check, source_sensitivity, acl, chunk_sensitivity in rows:
        restricted = RESTRICTED_SENSITIVITY in (source_sensitivity, chunk_sensitivity)
        found[claim_id].append(CitationFacts(quote_check, restricted, acl))
    return {claim_id: tuple(items) for claim_id, items in found.items()}
