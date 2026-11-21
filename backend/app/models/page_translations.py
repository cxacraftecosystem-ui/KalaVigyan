import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, created_at, one_of, uuid_pk
from .monograph_documents import LANGUAGE_CHARS, SLUG_CHARS, SUBJECT_KIND_CHARS
from .open_work import TASK_KEY_COLUMN_CHARS

__all__ = [
    "DOCUMENT_TAG_CHARS",
    "HASH_CHARS",
    "TRANSLATION_ORIGINS",
    "TRANSLATION_ROW_STATUSES",
    "UNIT_KEY_CHARS",
    "PageTextUnit",
    "PageTranslation",
    "TranslationReader",
]

HASH_CHARS = 64
UNIT_KEY_CHARS = 200
DOCUMENT_TAG_CHARS = 160
STATUS_CHARS = 16
CHAPTER_CHARS = 80
TAG_CHARS = 16
NOTE_CHARS = 500
PLACED_CHARS = 16
TRANSLATION_ROW_STATUSES = ("APPROVED", "IN_REVIEW", "DRAFT", "REJECTED", "SUPERSEDED")
TRANSLATION_ORIGINS = ("RESEARCH", "CONTRIBUTION", "AGENT")
HASH_CHECK = "~ '^[0-9a-f]{64}$'"


def _json(default: str) -> Mapped[Any]:
    return mapped_column(JSONB, nullable=False, server_default=text(default))


class PageTranslation(Base):
    __tablename__ = "PageTranslation"

    id: Mapped[uuid.UUID] = uuid_pk()
    batchId: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    subjectKind: Mapped[str] = mapped_column(String(SUBJECT_KIND_CHARS), nullable=False)
    subjectSlug: Mapped[str] = mapped_column(String(SLUG_CHARS), nullable=False)
    language: Mapped[str] = mapped_column(String(LANGUAGE_CHARS), nullable=False)
    unitKey: Mapped[str] = mapped_column(String(UNIT_KEY_CHARS), nullable=False)
    sourceHash: Mapped[str] = mapped_column(String(HASH_CHARS), nullable=False)
    english: Mapped[str] = mapped_column(Text, nullable=False)
    texts: Mapped[list[str]] = _json("'[]'::jsonb")
    checks: Mapped[list[dict[str, Any]]] = _json("'[]'::jsonb")
    status: Mapped[str] = mapped_column(String(STATUS_CHARS), nullable=False)
    placedBy: Mapped[str | None] = mapped_column(String(PLACED_CHARS))
    origin: Mapped[str] = mapped_column(String(STATUS_CHARS), nullable=False)
    proposerId: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("User.id", ondelete="SET NULL")
    )
    taskKey: Mapped[str | None] = mapped_column(String(TASK_KEY_COLUMN_CHARS))
    note: Mapped[str | None] = mapped_column(String(NOTE_CHARS))
    reviewedById: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("User.id", ondelete="SET NULL")
    )
    reviewedAt: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reviewNote: Mapped[str | None] = mapped_column(String(NOTE_CHARS))
    createdAt: Mapped[datetime] = created_at()

    __table_args__ = (
        CheckConstraint(one_of("status", TRANSLATION_ROW_STATUSES), name="status"),
        CheckConstraint(one_of("origin", TRANSLATION_ORIGINS), name="origin"),
        CheckConstraint(f'"sourceHash" {HASH_CHECK}', name="sourceHash"),
        CheckConstraint("\"language\" <> 'en'", name="language"),
        Index(None, "subjectKind", "subjectSlug", "language", "status"),
        Index(None, "language", "status", "createdAt"),
        Index(None, "proposerId"),
    )


class PageTextUnit(Base):
    __tablename__ = "PageTextUnit"

    subjectKind: Mapped[str] = mapped_column(String(SUBJECT_KIND_CHARS), primary_key=True)
    subjectSlug: Mapped[str] = mapped_column(String(SLUG_CHARS), primary_key=True)
    unitKey: Mapped[str] = mapped_column(String(UNIT_KEY_CHARS), primary_key=True)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    sourceHash: Mapped[str] = mapped_column(String(HASH_CHARS), nullable=False)
    chapter: Mapped[str] = mapped_column(String(CHAPTER_CHARS), nullable=False)
    tag: Mapped[str] = mapped_column(String(TAG_CHARS), nullable=False)
    leaves: Mapped[list[dict[str, Any]]] = _json("'[]'::jsonb")
    documentTag: Mapped[str] = mapped_column(String(DOCUMENT_TAG_CHARS), nullable=False)
    refreshedAt: Mapped[datetime] = created_at()

    __table_args__ = (
        CheckConstraint(f'"sourceHash" {HASH_CHECK}', name="sourceHash"),
        CheckConstraint('"position" >= 0', name="position"),
        Index(None, "subjectKind", "subjectSlug", "sourceHash"),
    )


class TranslationReader(Base):
    __tablename__ = "TranslationReader"

    userId: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("User.id", ondelete="CASCADE"), primary_key=True
    )
    language: Mapped[str] = mapped_column(String(LANGUAGE_CHARS), primary_key=True)
    createdAt: Mapped[datetime] = created_at()

    __table_args__ = (CheckConstraint("\"language\" <> 'en'", name="language"),)
