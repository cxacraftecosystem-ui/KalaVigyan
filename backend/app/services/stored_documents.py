from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Any

from sqlalchemy import delete, func, or_, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ArticleSection, StoredDocument
from app.research.document_parts import compact_json
from app.research.monograph_document import ENGLISH, MonographDocument

from .monograph_document import document_body, document_hash
from .monograph_generated import enough_sections, generated_document_of
from .open_work_subjects import CATEGORY, WorkSubject, subject_by_key
from .stored_document_stamp import document_stamp

__all__ = [
    "REBUILD_RETRY",
    "GeneratedRead",
    "Rebuilt",
    "StoredCopy",
    "claim_rebuild",
    "generated_read",
    "has_sections",
    "read_generated",
    "rebuild_document",
    "stored_copy",
    "stored_row",
    "utc_now",
]

logger = logging.getLogger(__name__)

PUBLISHED = "PUBLISHED"
REBUILD_RETRY = timedelta(minutes=10)
BUILD_LOCK = "stored-document:{kind}:{slug}"


class Rebuilt(StrEnum):
    BUILT = "built"
    CHANGED = "changed"
    UNCHANGED = "unchanged"
    REMOVED = "removed"
    ABSENT = "absent"

    @property
    def moved(self) -> bool:
        return self in (Rebuilt.BUILT, Rebuilt.CHANGED, Rebuilt.REMOVED)


@dataclass(frozen=True)
class StoredCopy:
    text: str
    version: int
    content_hash: str
    language: str
    current: bool

    @property
    def etag(self) -> str:
        return f"v{self.version}-{self.content_hash}"

    def body(self) -> dict[str, Any]:
        found: dict[str, Any] = json.loads(self.text)
        return found


@dataclass(frozen=True)
class GeneratedRead:
    subject: WorkSubject
    copy: StoredCopy | None
    rebuild: bool = False


async def generated_read(session: AsyncSession, kind: str, slug: str) -> GeneratedRead:
    return await read_generated(session, await subject_by_key(session, kind, slug), now=utc_now())


async def read_generated(session: AsyncSession, subject: WorkSubject, *, now: datetime) -> GeneratedRead:
    copy = await stored_copy(session, subject)
    if copy is None or copy.current:
        return GeneratedRead(subject, copy)
    return GeneratedRead(subject, copy, rebuild=await claim_rebuild(session, subject, now=now))


async def stored_copy(
    session: AsyncSession, subject: WorkSubject, *, language: str = ENGLISH
) -> StoredCopy | None:
    if not await has_sections(session, subject):
        return None
    row = await stored_row(session, subject, language)
    stamp = await document_stamp(session, subject)
    if row is not None:
        return _copy(row, stamp)
    await session.execute(select(func.pg_advisory_xact_lock(func.hashtextextended(_lock_key(subject), 0))))
    row = await stored_row(session, subject, language)
    if row is None:
        document = await generated_document_of(session, subject)
        row = None if document is None else (await _store(session, document, stamp, now=utc_now()))[0]
    await session.commit()
    return None if row is None else _copy(row, stamp)


async def claim_rebuild(
    session: AsyncSession, subject: WorkSubject, *, now: datetime, language: str = ENGLISH
) -> bool:
    claimed = await session.execute(
        update(StoredDocument)
        .where(
            StoredDocument.subjectKind == subject.kind,
            StoredDocument.subjectSlug == subject.slug,
            StoredDocument.language == language,
            or_(StoredDocument.wantedAt.is_(None), StoredDocument.wantedAt < now - REBUILD_RETRY),
        )
        .values(wantedAt=now)
        .returning(StoredDocument.subjectSlug)
    )
    taken = claimed.first() is not None
    await session.commit()
    return taken


async def rebuild_document(session: AsyncSession, subject: WorkSubject, *, now: datetime) -> Rebuilt:
    stamp = await document_stamp(session, subject)
    document = await generated_document_of(session, subject) if await has_sections(session, subject) else None
    if document is None:
        removed = await session.execute(
            delete(StoredDocument)
            .where(StoredDocument.subjectKind == subject.kind, StoredDocument.subjectSlug == subject.slug)
            .returning(StoredDocument.subjectSlug)
        )
        return Rebuilt.REMOVED if removed.first() is not None else Rebuilt.ABSENT
    before = await stored_row(session, subject, document.language)
    held = None if before is None else before.stamp
    _, rebuilt = await _store(session, document, stamp, now=now)
    if rebuilt == Rebuilt.CHANGED and held == stamp:
        logger.error(
            "the document of %s:%s changed under an unchanged stamp; an input the stamp misses moved",
            subject.kind,
            subject.slug,
        )
    return rebuilt


async def has_sections(session: AsyncSession, subject: WorkSubject) -> bool:
    column = ArticleSection.categoryId if subject.kind == CATEGORY else ArticleSection.craftId
    published = await session.scalar(
        select(func.count(ArticleSection.id)).where(column == subject.id, ArticleSection.status == PUBLISHED)
    )
    count = int(published or 0)
    return count > 0 and enough_sections(subject.kind, count)


async def stored_row(
    session: AsyncSession, subject: WorkSubject, language: str = ENGLISH
) -> StoredDocument | None:
    return await session.get(StoredDocument, (subject.kind, subject.slug, language), populate_existing=True)


def utc_now() -> datetime:
    return datetime.now(UTC)


async def _store(
    session: AsyncSession, document: MonographDocument, stamp: str, *, now: datetime
) -> tuple[StoredDocument, Rebuilt]:
    key = (document.subject_kind, document.subject_slug, document.language)
    row = await session.get(StoredDocument, key, populate_existing=True)
    digest = document_hash(document)
    if row is not None and row.contentHash == digest:
        row.stamp, row.wantedAt, row.builtAt = stamp, None, now
        await session.flush()
        return row, Rebuilt.UNCHANGED
    version = document.version if row is None else max(row.version + 1, document.version)
    values = {
        "subjectKind": key[0],
        "subjectSlug": key[1],
        "language": key[2],
        "stamp": stamp,
        "version": version,
        "contentHash": digest,
        "document": compact_json(document_body(document.model_copy(update={"version": version}))),
        "builtAt": now,
        "wantedAt": None,
    }
    statement = insert(StoredDocument).values(**values)
    await session.execute(
        statement.on_conflict_do_update(
            index_elements=[StoredDocument.subjectKind, StoredDocument.subjectSlug, StoredDocument.language],
            set_={
                name: statement.excluded[name]
                for name in values
                if name not in ("subjectKind", "subjectSlug", "language")
            },
        )
    )
    stored = await session.get(StoredDocument, key, populate_existing=True)
    if stored is None:
        raise RuntimeError(f"the document of {key[0]}:{key[1]} was written but cannot be read back")
    return stored, Rebuilt.BUILT if row is None else Rebuilt.CHANGED


def _copy(row: StoredDocument, stamp: str) -> StoredCopy:
    return StoredCopy(
        text=row.document,
        version=row.version,
        content_hash=row.contentHash,
        language=row.language,
        current=row.stamp == stamp and row.wantedAt is None,
    )


def _lock_key(subject: WorkSubject) -> str:
    return BUILD_LOCK.format(kind=subject.kind, slug=subject.slug)
