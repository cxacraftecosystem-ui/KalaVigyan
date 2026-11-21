from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from pydantic import ValidationError
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import session_scope
from app.core.errors import AppError
from app.models import ArticleSection, Craft, CraftCategory, MonographDocument as AuthoredRow
from app.research.page_revalidation import PageOwners

from .app_settings import get_value, set_value
from .monograph_document import CRAFT_SUBJECT
from .open_work_subjects import CATEGORY, WorkSubject, craft_subjects, subject_by_key
from .page_code import page_code_fingerprint
from .page_revalidation import refresh_pages
from .stored_document_stamp import document_stamp
from .stored_documents import Rebuilt, rebuild_document, stored_row, utc_now

__all__ = [
    "DOCUMENT_CODE_SETTING",
    "DocumentsReport",
    "generated_subjects",
    "mark_rebuild_code",
    "rebuild_stale_documents",
    "rebuild_wanted",
    "rebuilds_here",
    "subject_owners",
]

logger = logging.getLogger(__name__)

DOCUMENT_CODE_SETTING = "pages.documentCode"
REBUILD_LOCK = "stored-documents:rebuild"
PUBLISHED = "PUBLISHED"


@dataclass
class DocumentsReport:
    stale: int = 0
    rebuilt: list[str] = field(default_factory=list)
    changed: int = 0
    removed: int = 0
    failed: list[str] = field(default_factory=list)
    moved: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "documentsStale": self.stale,
            "documentsRebuilt": len(self.rebuilt),
            "documentsChanged": self.changed,
            "documentsRemoved": self.removed,
            "documentsFailed": self.failed,
        }


async def mark_rebuild_code(session: AsyncSession) -> None:
    await set_value(session, DOCUMENT_CODE_SETTING, page_code_fingerprint())


async def rebuilds_here(session: AsyncSession) -> bool:
    code = await get_value(session, DOCUMENT_CODE_SETTING)
    return code is None or code == page_code_fingerprint()


async def rebuild_stale_documents(session: AsyncSession, *, report: DocumentsReport, limit: int) -> None:
    await mark_rebuild_code(session)
    await session.commit()
    stale = [subject for subject in await generated_subjects(session) if await _stale(session, subject)]
    report.stale = len(stale)
    for subject in stale[:limit]:
        named = f"{subject.kind}:{subject.slug}"
        try:
            rebuilt = await rebuild_document(session, subject, now=utc_now())
            await session.commit()
        except (AppError, ValidationError) as error:
            await session.rollback()
            logger.error("the document of %s could not be rebuilt: %s", named, error)
            report.failed.append(named)
            continue
        report.rebuilt.append(named)
        report.changed += int(rebuilt == Rebuilt.CHANGED)
        report.removed += int(rebuilt == Rebuilt.REMOVED)
        if rebuilt.moved:
            report.moved.append(named)


async def rebuild_wanted(kind: str, slug: str) -> None:
    try:
        async with session_scope() as session:
            if not await rebuilds_here(session) or not await _rebuild_lock(session):
                return
            rebuilt = await rebuild_document(
                session, await subject_by_key(session, kind, slug), now=utc_now()
            )
    except (AppError, ValidationError) as error:
        logger.error("the document of %s:%s could not be rebuilt after a read: %s", kind, slug, error)
        return
    if rebuilt.moved:
        await refresh_pages(subject_owners(kind, slug))


def subject_owners(kind: str, slug: str) -> PageOwners:
    return PageOwners(categories=(slug,)) if kind == CATEGORY else PageOwners(crafts=(slug,))


async def generated_subjects(session: AsyncSession) -> list[WorkSubject]:
    authored = select(AuthoredRow.subjectSlug).where(AuthoredRow.subjectKind == CRAFT_SUBJECT)
    sectioned = select(ArticleSection.craftId).where(
        ArticleSection.craftId.is_not(None), ArticleSection.status == PUBLISHED
    )
    crafts = await session.scalars(
        select(Craft.slug).where(and_(Craft.id.in_(sectioned), Craft.slug.not_in(authored)))
    )
    shared = select(ArticleSection.categoryId).where(ArticleSection.status == PUBLISHED)
    categories = await session.scalars(select(CraftCategory.slug).where(CraftCategory.id.in_(shared)))
    found = [
        *await craft_subjects(session, sorted(crafts.all())),
        *[await subject_by_key(session, CATEGORY, slug) for slug in sorted(categories.all())],
    ]
    return sorted(found, key=lambda subject: (not subject.curated, subject.kind != CATEGORY, subject.slug))


async def _stale(session: AsyncSession, subject: WorkSubject) -> bool:
    row = await stored_row(session, subject)
    return row is None or row.wantedAt is not None or row.stamp != await document_stamp(session, subject)


async def _rebuild_lock(session: AsyncSession) -> bool:
    taken = await session.scalar(
        select(func.pg_try_advisory_xact_lock(func.hashtextextended(REBUILD_LOCK, 0)))
    )
    return bool(taken)
