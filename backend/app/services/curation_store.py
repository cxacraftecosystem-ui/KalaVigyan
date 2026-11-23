from __future__ import annotations

import uuid
from collections.abc import Sequence
from typing import Any

from sqlalchemy import Select, and_, select, tuple_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    ClaimSource,
    Concept,
    ConceptEdge,
    CraftGiRecord,
    CraftLocation,
    CraftPrice,
    CraftWorkforce,
    CuratedClaim,
    Material,
    MediaRef,
    MediaRefClaim,
    Process,
    ProcessStage,
    Reaction,
    ReactionCitation,
    Source,
    StageMaterial,
    Term,
    TermConcept,
    TermCraft,
)

from .claim_holds import with_kept_verdicts
from .curated_compounds import linked_compounds
from .curated_index import CuratedPage
from .curation_claims import craft_curated_claims
from .curation_plan import CurationPlan, PlanParts
from .curation_structure import CONTRAST_RELATION
from .curation_writes import delete_rows, insert_missing, keep_only, stored_values, sync_rows, update_rows

__all__ = [
    "source_aliases",
    "write_evidence",
    "write_media_and_terms",
    "write_records",
    "write_structure",
]


async def source_aliases(session: AsyncSession, plan: PlanParts) -> dict[uuid.UUID, uuid.UUID]:
    by_doi: dict[str, list[uuid.UUID]] = {}
    for row in plan.part("sources"):
        if row["doi"]:
            by_doi.setdefault(row["doi"], []).append(row["id"])
    if not by_doi:
        return {}
    stored = dict(
        (await session.execute(select(Source.doi, Source.id).where(Source.doi.in_(list(by_doi)))))
        .tuples()
        .all()
    )
    aliases: dict[uuid.UUID, uuid.UUID] = {}
    for doi, ids in by_doi.items():
        keeper = stored.get(doi, ids[0])
        aliases.update((source_id, keeper) for source_id in ids if source_id != keeper)
    return aliases


async def write_evidence(
    session: AsyncSession, plan: PlanParts, *, marker: Any = CuratedClaim
) -> dict[str, int]:
    claim_ids = [row["id"] for row in plan.part("claims")]
    kept = [row["id"] for row in plan.part("claimSources")]
    return {
        "sources": await sync_rows(session, Source, plan.part("sources")),
        "concepts": await sync_rows(session, Concept, plan.part("concepts")),
        "curatedClaims": await sync_rows(session, marker, plan.part("curatedClaims"), key="claimId"),
        "claimSources": await sync_rows(
            session, ClaimSource, await with_kept_verdicts(session, plan.part("claimSources"))
        ),
        "droppedQuotes": await delete_rows(
            session, ClaimSource, ClaimSource.claimId.in_(claim_ids), keep_only(ClaimSource.id, kept)
        ),
    }


async def write_structure(
    session: AsyncSession, plan: CurationPlan, previous: CuratedPage | None
) -> dict[str, int]:
    changed = {"locations": await _locations(session, plan, previous)}
    changed["processes"] = await sync_rows(session, Process, plan.part("processes"))
    changed["stages"] = await _stages(session, plan)
    materials, changed["compounds"] = await _with_compounds(session, plan)
    changed["materials"] = await sync_rows(session, Material, materials)
    stage_ids = [row["id"] for row in plan.part("stages")]
    reaction_ids = [row["id"] for row in plan.part("reactions")]
    changed["stageMaterials"] = await _synced(
        session, StageMaterial, plan.part("stageMaterials"), StageMaterial.stageId.in_(stage_ids)
    )
    changed["reactions"] = await _synced(
        session, Reaction, plan.part("reactions"), Reaction.stageId.in_(stage_ids)
    )
    changed["reactionCitations"] = await _synced(
        session,
        ReactionCitation,
        plan.part("reactionCitations"),
        ReactionCitation.reactionId.in_(reaction_ids),
    )
    claim_ids = [row["id"] for row in plan.part("claims")]
    changed["alternatives"] = await _synced(
        session,
        ConceptEdge,
        plan.part("alternatives"),
        and_(ConceptEdge.relation == CONTRAST_RELATION, ConceptEdge.claimId.in_(claim_ids)),
    )
    return changed


async def _synced(session: AsyncSession, model: Any, rows: Sequence[dict[str, Any]], scope: Any) -> int:
    written = await sync_rows(session, model, rows)
    removed = await delete_rows(session, model, scope, keep_only(model.id, [row["id"] for row in rows]))
    return written + removed


async def _locations(session: AsyncSession, plan: CurationPlan, previous: CuratedPage | None) -> int:
    rows = plan.part("locations")
    written = await sync_rows(session, CraftLocation, rows)
    stale = (previous.location_ids() if previous else set()) - {row["id"] for row in rows}
    removed = await delete_rows(session, CraftLocation, CraftLocation.id.in_(list(stale))) if stale else 0
    return written + removed


async def _stages(session: AsyncSession, plan: CurationPlan) -> int:
    process = plan.index.process_id
    rows = plan.part("stages")
    if process is None:
        return 0
    wanted = {row["id"]: row["ordinal"] for row in rows}
    removed = await delete_rows(
        session, ProcessStage, ProcessStage.processId == process, keep_only(ProcessStage.id, list(wanted))
    )
    current = dict(
        (
            await session.execute(
                select(ProcessStage.id, ProcessStage.ordinal).where(ProcessStage.processId == process)
            )
        )
        .tuples()
        .all()
    )
    if any(current[stage_id] != wanted[stage_id] for stage_id in current):
        await update_rows(
            session,
            ProcessStage,
            [{"id": stage_id, "ordinal": -1 - ordinal} for stage_id, ordinal in current.items()],
        )
    return removed + await sync_rows(session, ProcessStage, rows)


async def _with_compounds(session: AsyncSession, plan: CurationPlan) -> tuple[list[dict[str, Any]], int]:
    if not any(item.pubchem_cid for item in plan.index.materials):
        return list(plan.part("materials")), 0
    linked = await linked_compounds(session, plan.index.materials, retrieved_at=plan.dossier.curated_at)
    rows = [{**row, "compoundId": linked.by_material.get(row["id"])} for row in plan.part("materials")]
    return rows, linked.written


async def write_records(
    session: AsyncSession, plan: CurationPlan, previous: CuratedPage | None
) -> dict[str, int]:
    craft = plan.craft.id
    shown = {picture.media_ref_id for picture in previous.pictures} if previous else set()
    changed = await write_media_and_terms(
        session, plan, previous_media=shown, marked=craft_curated_claims(craft)
    )
    changed["termLinks"] += await insert_missing(session, TermCraft, plan.part("termCrafts"))
    changed |= {
        "giRecords": await sync_rows(session, CraftGiRecord, plan.part("giRecords"), key="craftId"),
        "prices": await _synced(session, CraftPrice, plan.part("prices"), CraftPrice.craftId == craft),
        "workforce": await _synced(
            session, CraftWorkforce, plan.part("workforce"), CraftWorkforce.craftId == craft
        ),
    }
    if not plan.part("giRecords"):
        changed["giRecords"] += await delete_rows(session, CraftGiRecord, CraftGiRecord.craftId == craft)
    return changed


async def write_media_and_terms(
    session: AsyncSession,
    plan: PlanParts,
    *,
    previous_media: set[uuid.UUID],
    marked: Select[tuple[uuid.UUID]],
) -> dict[str, int]:
    media = {row["id"] for row in plan.part("media")} | previous_media
    inserted = await insert_missing(session, MediaRef, plan.part("media"))
    return {
        "media": inserted + await _filled_sizes(session, plan.part("media")),
        "mediaClaims": await _media_claims(session, plan.part("mediaClaims"), media, marked),
        "terms": await insert_missing(session, Term, plan.part("terms")),
        "termLinks": await insert_missing(session, TermConcept, plan.part("termConcepts")),
    }


async def _filled_sizes(session: AsyncSession, rows: Sequence[dict[str, Any]]) -> int:
    sized = {row["id"]: row for row in rows if row["width"] is not None}
    if not sized:
        return 0
    stored = await stored_values(session, MediaRef, list(sized), ["width"])
    fills = [
        {"id": media_id, "width": row["width"], "height": row["height"]}
        for media_id, row in sized.items()
        if media_id in stored and stored[media_id]["width"] is None
    ]
    await update_rows(session, MediaRef, fills)
    return len(fills)


async def _media_claims(
    session: AsyncSession,
    links: Sequence[dict[str, Any]],
    media: set[uuid.UUID],
    marked: Select[tuple[uuid.UUID]],
) -> int:
    inserted = await insert_missing(session, MediaRefClaim, links)
    if not media:
        return inserted
    kept = [(row["mediaRefId"], row["claimId"]) for row in links]
    conditions = [MediaRefClaim.mediaRefId.in_(list(media)), MediaRefClaim.claimId.in_(marked)]
    if kept:
        conditions.append(tuple_(MediaRefClaim.mediaRefId, MediaRefClaim.claimId).not_in(kept))
    return inserted + await delete_rows(session, MediaRefClaim, *conditions)
