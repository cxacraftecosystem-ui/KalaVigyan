from __future__ import annotations

import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import InvalidInput
from app.curation.files import CURATION_DIR, dossier_paths
from app.models import (
    Craft,
    CraftGiRecord,
    CraftLocation,
    CraftPrice,
    CraftWorkforce,
    CuratedCraft,
    KnowledgePiece as PieceRow,
    Process,
)
from app.models.science import live_process

from .curated_index import CuratedPage, stored_curated_page
from .curation_claims import craft_curated_claims, write_claims
from .curation_seed_rows import SeedRetirement, restore_seed_rows
from .curation_writes import delete_rows

__all__ = ["DOSSIER_RETIRED_NOTE", "RetiredDossier", "retire_dossier"]

DOSSIER_RETIRED_NOTE = "curated dossier retired, its file left the curation folder"


@dataclass(frozen=True)
class RetiredDossier:
    craft_slug: str
    claims: int
    pieces: int
    processes: int
    seed_rows: SeedRetirement
    records: int = 0

    def summary(self) -> dict[str, Any]:
        return {
            "retired": self.craft_slug,
            "claims": self.claims,
            "pieces": self.pieces,
            "processes": self.processes,
            "records": self.records,
            "restoredSeedRows": self.seed_rows.summary(),
        }


async def retire_dossier(
    session: AsyncSession, craft_slug: str, *, directory: Path = CURATION_DIR
) -> RetiredDossier:
    if any(path.stem == craft_slug for path in dossier_paths(directory)):
        raise InvalidInput(f"{craft_slug}.json is still in the curation folder; remove it before retiring it")
    craft = await session.scalar(select(Craft).where(Craft.slug == craft_slug))
    stored = (
        await session.scalar(select(CuratedCraft.page).where(CuratedCraft.craftId == craft.id))
        if craft
        else None
    )
    if craft is None or stored is None:
        raise InvalidInput(f"{craft_slug} has no imported dossier to retire")
    page = stored_curated_page(craft.id, stored)
    records = await _removed_records(session, craft.id, page)
    claims = await write_claims(session, craft_curated_claims(craft.id), [], DOSSIER_RETIRED_NOTE)
    pieces = await _stale_pieces(session, page)
    processes = await _archived_process(session, page)
    await delete_rows(session, CuratedCraft, CuratedCraft.craftId == craft.id)
    restored = await restore_seed_rows(session, craft.id)
    return RetiredDossier(craft_slug, claims, pieces, processes, restored, records)


async def _removed_records(session: AsyncSession, craft_id: uuid.UUID, page: CuratedPage | None) -> int:
    curated = list(await session.scalars(craft_curated_claims(craft_id)))
    locations = list(page.location_ids()) if page else []
    removed = await delete_rows(session, CraftLocation, CraftLocation.id.in_(locations)) if locations else 0
    if not curated:
        return removed
    removed += await delete_rows(
        session, CraftPrice, CraftPrice.craftId == craft_id, CraftPrice.claimId.in_(curated)
    )
    removed += await delete_rows(
        session, CraftWorkforce, CraftWorkforce.craftId == craft_id, CraftWorkforce.claimId.in_(curated)
    )
    return removed + await delete_rows(
        session, CraftGiRecord, CraftGiRecord.craftId == craft_id, CraftGiRecord.claimIds.overlap(curated)
    )


async def _stale_pieces(session: AsyncSession, page: CuratedPage | None) -> int:
    piece_ids: list[uuid.UUID] = list(page.piece_ids().values()) if page else []
    if not piece_ids:
        return 0
    result = await session.execute(
        update(PieceRow)
        .where(PieceRow.id.in_(piece_ids), PieceRow.staleSince.is_(None), PieceRow.supersededById.is_(None))
        .values(staleSince=func.now())
    )
    return max(result.rowcount or 0, 0)


async def _archived_process(session: AsyncSession, page: CuratedPage | None) -> int:
    if page is None or page.process_id is None:
        return 0
    result = await session.execute(
        update(Process)
        .where(Process.id == page.process_id, live_process())
        .values(archivedAt=func.now(), updatedAt=func.now())
    )
    return max(result.rowcount or 0, 0)
