from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pydantic import ValidationError
from sqlalchemy import Select, select
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError, InvalidInput
from app.curation.check_file import CheckFile
from app.curation.checks import CheckContext, default_context
from app.curation.dossier import Dossier
from app.curation.files import CATEGORIES_DIR_NAME, CURATION_DIR, category_paths, check_path, checked_dossier
from app.models import CraftCategory, CuratedCategory, CuratedCategoryClaim

from . import knowledge_view
from .answer_events import cited_claims
from .category_plan import CategoryPlan, CategoryTarget, category_plan
from .curated_category_index import CuratedCategoryPage, indexed_category_overview, stored_category_page
from .curation_claims import write_claims
from .curation_import import IMPORTED, REFUSED, dossier_digest, write_pieces
from .curation_overview import OverviewPieces, overview_pieces
from .curation_sections import publish_dossier_sections
from .curation_store import source_aliases, write_evidence, write_media_and_terms
from .curation_writes import stored_values, sync_rows
from .monograph_generated_sections import SectionOwner

__all__ = [
    "CategoryImportReport",
    "CategoryOutcome",
    "category_curated_claims",
    "import_categories",
    "import_category",
    "import_category_path",
]

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class CategoryOutcome:
    file: str
    status: str
    category_slug: str | None = None
    version: int | None = None
    changed: dict[str, int] = field(default_factory=dict)
    problems: tuple[str, ...] = ()
    dropped_sentences: tuple[str, ...] = ()

    def summary(self) -> dict[str, Any]:
        return {
            "file": self.file,
            "status": self.status,
            "categorySlug": self.category_slug,
            "version": self.version,
            "changed": self.changed,
            "problems": list(self.problems),
            "droppedSentences": list(self.dropped_sentences),
        }


@dataclass(frozen=True)
class CategoryImportReport:
    outcomes: tuple[CategoryOutcome, ...]

    @property
    def refused(self) -> list[CategoryOutcome]:
        return [outcome for outcome in self.outcomes if outcome.status == REFUSED]

    def summary(self) -> dict[str, Any]:
        return {
            "imported": sum(1 for outcome in self.outcomes if outcome.status == IMPORTED),
            "refused": len(self.refused),
            "dossiers": [outcome.summary() for outcome in self.outcomes],
        }


def category_curated_claims(category_id: uuid.UUID) -> Select[tuple[uuid.UUID]]:
    return select(CuratedCategoryClaim.claimId).where(CuratedCategoryClaim.categoryId == category_id)


async def import_categories(
    session: AsyncSession, *, directory: Path = CURATION_DIR, context: CheckContext | None = None
) -> CategoryImportReport:
    checking = context or default_context()
    outcomes = [await import_category_path(session, path, checking) for path in category_paths(directory)]
    return CategoryImportReport(outcomes=tuple(outcomes))


async def import_category_path(session: AsyncSession, path: Path, context: CheckContext) -> CategoryOutcome:
    file = f"{CATEGORIES_DIR_NAME}/{path.name}"
    result = checked_dossier(path, context)
    if result.problems or result.dossier is None or result.check is None:
        lines = tuple(problem.line(file) for problem in result.problems) or ("the check file is missing",)
        return CategoryOutcome(file=file, status=REFUSED, problems=lines)
    digest = dossier_digest(path, check_path(path, result.dossier.slug))
    try:
        async with session.begin_nested():
            return await import_category(session, result.dossier, result.check, digest=digest)
    except (AppError, DBAPIError, ValidationError) as refused:
        logger.warning("category dossier %s was not imported: %s", file, refused)
        return CategoryOutcome(
            file=file, status=REFUSED, category_slug=result.dossier.slug, problems=(str(refused),)
        )


async def import_category(
    session: AsyncSession, dossier: Dossier, check: CheckFile, *, digest: str
) -> CategoryOutcome:
    category = await _category(session, dossier.slug)
    stored = await stored_values(
        session, CuratedCategory, [category.id], ["digest", "page"], key="categoryId"
    )
    previous = stored_category_page(category.id, (stored.get(category.id) or {}).get("page"))
    plan = category_plan(dossier, check, category)
    plan = plan.with_sources(await source_aliases(session, plan))
    marked = category_curated_claims(category.id)
    note = f"curation import {dossier.slug} v{dossier.version}"
    changed = {"claims": await write_claims(session, marked, plan.part("claims"), note)}
    changed |= await write_evidence(session, plan, marker=CuratedCategoryClaim)
    shown = {picture.media_ref_id for picture in previous.pictures} if previous else set()
    changed |= await write_media_and_terms(session, plan, previous_media=shown, marked=marked)
    await session.flush()
    changed["sections"] = await publish_dossier_sections(session, dossier, SectionOwner.category(category.id))
    overview = await _overview(session, plan)
    changed["pieces"] = await write_pieces(session, overview, previous.piece_ids() if previous else {})
    index = indexed_category_overview(plan.index, overview)
    changed["curatedCategory"] = await _write_page(session, plan, index, (digest, stored.get(category.id)))
    return CategoryOutcome(
        file=f"{CATEGORIES_DIR_NAME}/{dossier.slug}.json",
        status=IMPORTED,
        category_slug=dossier.slug,
        version=dossier.version,
        changed={key: value for key, value in changed.items() if value},
        dropped_sentences=overview.dropped,
    )


async def _category(session: AsyncSession, slug: str) -> CategoryTarget:
    row = await session.scalar(select(CraftCategory).where(CraftCategory.slug == slug))
    if row is None:
        raise InvalidInput(f"category {slug} is not in the database; run seed_crafts first")
    return CategoryTarget(id=row.id, slug=row.slug, name=row.name)


async def _overview(session: AsyncSession, plan: CategoryPlan) -> OverviewPieces:
    views, sources = await knowledge_view.claims_by_id(session, plan.claim_ids())
    cited = cited_claims(list(views.values()), sources)
    return overview_pieces(plan.dossier, cited, craft_id=None, districts=())


async def _write_page(
    session: AsyncSession,
    plan: CategoryPlan,
    index: CuratedCategoryPage,
    digests: tuple[str, dict[str, Any] | None],
) -> int:
    digest, stored = digests
    row: dict[str, Any] = {
        "categoryId": plan.category.id,
        "version": plan.dossier.version,
        "curatedAt": plan.dossier.curated_at,
        "coverage": plan.dossier.coverage,
        "digest": digest,
        "page": index.model_dump(mode="json", by_alias=True),
    }
    if stored is None or stored["digest"] != digest:
        row["importedAt"] = datetime.now(UTC)
    return await sync_rows(session, CuratedCategory, [row], key="categoryId")
