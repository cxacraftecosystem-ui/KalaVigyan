from __future__ import annotations

import hashlib
import logging
import uuid
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pydantic import ValidationError
from sqlalchemy import select, update
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError, InvalidInput
from app.curation.check_file import CheckFile
from app.curation.checks import CheckContext, default_context
from app.curation.dossier import Dossier
from app.curation.files import CURATION_DIR, check_path, checked_dossier, dossier_paths
from app.data.district_register import load_district_codes
from app.data.portal_craft_register import load_portal_crafts
from app.models import Craft, CuratedCraft, KnowledgePiece as PieceRow

from . import knowledge_view
from .answer_events import cited_claims
from .curated_index import CuratedPage
from .curation_claims import craft_curated_claims, withdraw_seed_edges, write_claims
from .curation_overview import OverviewPieces, indexed_overview, overview_pieces
from .curation_plan import CurationPlan, curation_plan
from .curation_rows import CraftTarget
from .curation_sections import publish_dossier_sections
from .curation_seed_rows import SeedRetirement, retire_curated_seed_rows
from .curation_store import source_aliases, write_evidence, write_records, write_structure
from .curation_terms import write_curated_term_summaries
from .curation_writes import insert_missing, stored_values, sync_rows
from .monograph_generated_sections import SectionOwner
from .piece_lookup import craft_districts
from .piece_store import piece_values

__all__ = [
    "IMPORTED",
    "REFUSED",
    "WAITING",
    "DossierOutcome",
    "ImportReport",
    "dossier_digest",
    "import_curation",
    "import_dossier",
    "import_path",
    "write_pieces",
]

logger = logging.getLogger(__name__)

IMPORTED = "IMPORTED"
REFUSED = "REFUSED"
WAITING = "WAITING"


@dataclass(frozen=True)
class DossierOutcome:
    file: str
    status: str
    craft_slug: str | None = None
    version: int | None = None
    changed: dict[str, int] = field(default_factory=dict)
    problems: tuple[str, ...] = ()
    dropped_sentences: tuple[str, ...] = ()

    def summary(self) -> dict[str, Any]:
        return {
            "file": self.file,
            "status": self.status,
            "craftSlug": self.craft_slug,
            "version": self.version,
            "changed": self.changed,
            "problems": list(self.problems),
            "droppedSentences": list(self.dropped_sentences),
        }


@dataclass(frozen=True)
class ImportReport:
    withdrawn_edges: int
    dossiers: tuple[DossierOutcome, ...]
    retired_seed_rows: SeedRetirement = field(default_factory=SeedRetirement)
    term_summaries: int = 0

    @property
    def refused(self) -> list[DossierOutcome]:
        return [outcome for outcome in self.dossiers if outcome.status == REFUSED]

    def summary(self) -> dict[str, Any]:
        return {
            "withdrawnEdgeSentences": self.withdrawn_edges,
            "retiredSeedRows": self.retired_seed_rows.summary(),
            "termSummaries": self.term_summaries,
            "imported": sum(1 for outcome in self.dossiers if outcome.status == IMPORTED),
            "refused": len(self.refused),
            "waiting": sum(1 for outcome in self.dossiers if outcome.status == WAITING),
            "dossiers": [outcome.summary() for outcome in self.dossiers],
        }


def dossier_digest(dossier_path: Path, check: Path) -> str:
    digest = hashlib.sha256(dossier_path.read_bytes())
    digest.update(b"\n")
    digest.update(check.read_bytes())
    return digest.hexdigest()


async def import_curation(
    session: AsyncSession, *, directory: Path = CURATION_DIR, context: CheckContext | None = None
) -> ImportReport:
    withdrawn = await withdraw_seed_edges(session)
    checking = context or default_context()
    outcomes = [await import_path(session, path, checking) for path in dossier_paths(directory)]
    retired = await retire_curated_seed_rows(session)
    return ImportReport(
        withdrawn_edges=withdrawn,
        dossiers=tuple(outcomes),
        retired_seed_rows=retired,
        term_summaries=await write_curated_term_summaries(session),
    )


async def import_path(session: AsyncSession, path: Path, context: CheckContext) -> DossierOutcome:
    result = checked_dossier(path, context)
    if result.problems or result.dossier is None or result.check is None:
        lines = tuple(problem.line(path.name) for problem in result.problems) or (
            "the check file is missing",
        )
        return DossierOutcome(file=path.name, status=REFUSED, problems=lines)
    slug = result.dossier.craft_slug
    if slug in {craft.slug for craft in load_portal_crafts()} and not await _stored(session, slug):
        return DossierOutcome(
            file=path.name,
            status=WAITING,
            craft_slug=slug,
            problems=(
                f"{slug} is a portal-added craft the database does not hold yet; the portal craft sync adds it",
            ),
        )
    digest = dossier_digest(path, check_path(path, result.dossier.craft_slug))
    try:
        async with session.begin_nested():
            return await import_dossier(session, result.dossier, result.check, digest=digest)
    except (AppError, DBAPIError, ValidationError) as refused:
        logger.warning("dossier %s was not imported: %s", path.name, refused)
        return DossierOutcome(
            file=path.name, status=REFUSED, craft_slug=result.dossier.craft_slug, problems=(str(refused),)
        )


async def import_dossier(
    session: AsyncSession, dossier: Dossier, check: CheckFile, *, digest: str
) -> DossierOutcome:
    craft = await _craft(session, dossier.craft_slug)
    target = CraftTarget(id=craft.id, slug=craft.slug, name=craft.name)
    stored = await stored_values(session, CuratedCraft, [craft.id], ["digest", "page"], key="craftId")
    previous = _previous_index(stored.get(craft.id))
    plan = curation_plan(dossier, check, target, load_district_codes())
    plan = plan.with_sources(await source_aliases(session, plan))
    note = f"curation import {dossier.craft_slug} v{dossier.version}"
    marked = craft_curated_claims(craft.id)
    changed = {"claims": await write_claims(session, marked, plan.part("claims"), note)}
    changed |= await write_evidence(session, plan)
    changed |= await write_structure(session, plan, previous)
    changed |= await write_records(session, plan, previous)
    await session.flush()
    changed["sections"] = await publish_dossier_sections(session, dossier, SectionOwner.craft(craft.id))
    overview = await _overview(session, plan, craft)
    changed["pieces"] = await write_pieces(session, overview, previous.piece_ids() if previous else {})
    changed["curatedCraft"] = await _write_page(session, plan, overview, (digest, stored.get(craft.id)))
    return DossierOutcome(
        file=f"{dossier.craft_slug}.json",
        status=IMPORTED,
        craft_slug=dossier.craft_slug,
        version=dossier.version,
        changed={key: value for key, value in changed.items() if value},
        dropped_sentences=overview.dropped,
    )


async def _stored(session: AsyncSession, slug: str) -> bool:
    return await session.scalar(select(Craft.id).where(Craft.slug == slug)) is not None


async def _craft(session: AsyncSession, slug: str) -> Craft:
    craft = await session.scalar(select(Craft).where(Craft.slug == slug))
    if craft is None:
        raise InvalidInput(f"craft {slug} is not in the database; run seed_crafts first")
    return craft


def _previous_index(stored: dict[str, Any] | None) -> CuratedPage | None:
    if stored is None:
        return None
    try:
        return CuratedPage.model_validate(stored["page"])
    except ValidationError:
        logger.warning("the stored curated page index no longer meets its model; it is rebuilt")
        return None


async def _overview(session: AsyncSession, plan: CurationPlan, craft: Craft) -> OverviewPieces:
    views, sources = await knowledge_view.claims_by_id(session, plan.claim_ids())
    cited = cited_claims(list(views.values()), sources)
    districts = await craft_districts(session, craft)
    return overview_pieces(plan.dossier, cited, craft_id=craft.id, districts=districts)


async def write_pieces(
    session: AsyncSession, overview: OverviewPieces, previous_parts: Mapping[str, uuid.UUID]
) -> int:
    written = await insert_missing(session, PieceRow, [piece_values(piece) for piece in overview.pieces])
    retired = 0
    for part, old in previous_parts.items():
        new = overview.parts.get(part)
        if new == old:
            continue
        values = {"supersededById": new} if new else {"staleSince": datetime.now(UTC)}
        column = PieceRow.supersededById if new else PieceRow.staleSince
        result = await session.execute(
            update(PieceRow).where(PieceRow.id == old, column.is_(None)).values(values)
        )
        retired += max(result.rowcount or 0, 0)
    return written + retired


async def _write_page(
    session: AsyncSession,
    plan: CurationPlan,
    overview: OverviewPieces,
    digests: tuple[str, dict[str, Any] | None],
) -> int:
    digest, stored = digests
    row: dict[str, Any] = {
        "craftId": plan.craft.id,
        "version": plan.dossier.version,
        "curatedAt": plan.dossier.curated_at,
        "coverage": plan.dossier.coverage,
        "digest": digest,
        "page": indexed_overview(plan.index, overview).model_dump(mode="json", by_alias=True),
    }
    if stored is None or stored["digest"] != digest:
        row["importedAt"] = datetime.now(UTC)
    return await sync_rows(session, CuratedCraft, [row], key="craftId")
