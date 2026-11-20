import uuid
from datetime import date, datetime
from typing import Any

from sqlalchemy import CheckConstraint, Date, DateTime, ForeignKey, Index, Integer, String, Text, text as sql
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, created_at, one_of, updated_at, uuid_pk
from app.models.monograph_documents import SLUG_CHARS, SUBJECT_KIND_CHARS

__all__ = [
    "ACCESS_KIND_CHARS",
    "CITE_URL_CHARS",
    "DRAFT_ROW_STATES",
    "DRAFT_SUBJECT_KINDS",
    "SUPPLIED_ACCESS_KINDS",
    "SUPPLIED_ROW_STATES",
    "PageDraft",
    "SuppliedSource",
]

DRAFT_SUBJECT_KINDS = ("craft", "family", "category")
DRAFT_ROW_STATES = ("OPEN", "SUBMITTED")
SUPPLIED_ROW_STATES = ("READY", "AWAITING_FILE")
SUPPLIED_ACCESS_KINDS = ("SUBSCRIPTION", "INSTITUTION", "OWN_COPY", "ARCHIVE", "BLOCKED_SITE")
SUPPLIED_UPLOADS = ("pdf", "text")
GRADES = ("A", "B", "C", "D")
ACCESS_KIND_CHARS = 20
CITE_URL_CHARS = 2048
HASH_CHARS = 64


def _stamp() -> Mapped[datetime | None]:
    return mapped_column(DateTime(timezone=True), nullable=True)


class PageDraft(Base):
    __tablename__ = "PageDraft"
    __mapper_args__ = {"eager_defaults": True}

    id: Mapped[uuid.UUID] = uuid_pk()
    userId: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("User.id", ondelete="CASCADE"), nullable=False
    )
    subjectKind: Mapped[str] = mapped_column(String(SUBJECT_KIND_CHARS), nullable=False)
    subjectSlug: Mapped[str] = mapped_column(String(SLUG_CHARS), nullable=False)
    state: Mapped[str] = mapped_column(String(20), nullable=False, server_default=sql("'OPEN'"))
    parts: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, server_default=sql("'{}'::jsonb"))
    bytes: Mapped[int] = mapped_column(Integer, nullable=False, server_default=sql("0"))
    version: Mapped[int] = mapped_column(Integer, nullable=False, server_default=sql("1"))
    previewUrl: Mapped[str | None] = mapped_column(Text, nullable=True)
    previewExpiresAt: Mapped[datetime | None] = _stamp()
    report: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    result: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    submittedAt: Mapped[datetime | None] = _stamp()
    expiresAt: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    createdAt: Mapped[datetime] = created_at()
    updatedAt: Mapped[datetime] = updated_at()

    __table_args__ = (
        CheckConstraint(one_of("subjectKind", DRAFT_SUBJECT_KINDS), name="subjectKind"),
        CheckConstraint(one_of("state", DRAFT_ROW_STATES), name="state"),
        CheckConstraint("jsonb_typeof(\"parts\") = 'object'", name="parts"),
        CheckConstraint('"bytes" >= 0 AND "version" >= 1', name="counts"),
        CheckConstraint(
            '("state" = \'SUBMITTED\') = ("submittedAt" IS NOT NULL AND "result" IS NOT NULL)',
            name="submitted",
        ),
        Index(
            "PageDraft_userId_subject_open_key",
            "userId",
            "subjectKind",
            "subjectSlug",
            unique=True,
            postgresql_where=sql("\"state\" = 'OPEN'"),
        ),
        Index(None, "userId", "expiresAt"),
    )


class SuppliedSource(Base):
    __tablename__ = "SuppliedSource"
    __mapper_args__ = {"eager_defaults": True}

    id: Mapped[uuid.UUID] = uuid_pk()
    userId: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("User.id", ondelete="CASCADE"), nullable=False
    )
    userTokenVersion: Mapped[int] = mapped_column(Integer, nullable=False, server_default=sql("0"))
    state: Mapped[str] = mapped_column(String(20), nullable=False)
    citeUrl: Mapped[str] = mapped_column(String(CITE_URL_CHARS), nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    doi: Mapped[str | None] = mapped_column(String(255), nullable=True)
    isbn: Mapped[str | None] = mapped_column(String(13), nullable=True)
    identity: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    confirmation: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    accessKind: Mapped[str] = mapped_column(String(ACCESS_KIND_CHARS), nullable=False)
    accessedOn: Mapped[date] = mapped_column(Date, nullable=False)
    accessNote: Mapped[str | None] = mapped_column(String(300), nullable=True)
    licence: Mapped[str | None] = mapped_column(String(200), nullable=True)
    grade: Mapped[str] = mapped_column(String(1), nullable=False)
    gradeReason: Mapped[str] = mapped_column(String(400), nullable=False)
    passages: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB, nullable=False, server_default=sql("'[]'::jsonb")
    )
    text: Mapped[str | None] = mapped_column(Text, nullable=True)
    textSha256: Mapped[str | None] = mapped_column(String(HASH_CHARS), nullable=True)
    fileSha256: Mapped[str | None] = mapped_column(String(HASH_CHARS), nullable=True)
    characters: Mapped[int] = mapped_column(Integer, nullable=False, server_default=sql("0"))
    upload: Mapped[str | None] = mapped_column(String(10), nullable=True)
    slotHash: Mapped[str | None] = mapped_column(String(HASH_CHARS), nullable=True, unique=True)
    slotExpiresAt: Mapped[datetime | None] = _stamp()
    sourceIds: Mapped[list[uuid.UUID]] = mapped_column(
        ARRAY(UUID(as_uuid=True)), nullable=False, server_default=sql("ARRAY[]::uuid[]")
    )
    createdAt: Mapped[datetime] = created_at()
    updatedAt: Mapped[datetime] = updated_at()

    __table_args__ = (
        CheckConstraint(one_of("state", SUPPLIED_ROW_STATES), name="state"),
        CheckConstraint(one_of("accessKind", SUPPLIED_ACCESS_KINDS), name="accessKind"),
        CheckConstraint(one_of("grade", GRADES), name="grade"),
        CheckConstraint('"upload" IS NULL OR ' + one_of("upload", SUPPLIED_UPLOADS), name="upload"),
        CheckConstraint(
            '("state" = \'READY\') = ("text" IS NOT NULL AND "textSha256" IS NOT NULL)', name="ready"
        ),
        CheckConstraint('("slotHash" IS NULL) = ("slotExpiresAt" IS NULL)', name="slot"),
        CheckConstraint("jsonb_typeof(\"passages\") = 'array'", name="passages"),
        CheckConstraint('"characters" >= 0', name="characters"),
        Index(None, "userId", "citeUrl"),
        Index(None, "userId", "createdAt"),
    )
