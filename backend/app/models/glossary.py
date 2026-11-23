import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, created_at, one_of, updated_at, uuid_pk
from app.models.enums import TERM_BASES, TERM_ZOOM_LEVELS

TERM_TEXT_COLUMN_CHARS = 120
TERM_ZOOM_LEVEL_CHARS = 16


class Term(Base):
    __tablename__ = "Term"

    id: Mapped[uuid.UUID] = uuid_pk()
    key: Mapped[str] = mapped_column(String(TERM_TEXT_COLUMN_CHARS), nullable=False, unique=True)
    label: Mapped[str] = mapped_column(String(TERM_TEXT_COLUMN_CHARS), nullable=False)
    sentenceName: Mapped[str | None] = mapped_column(String(TERM_TEXT_COLUMN_CHARS))
    meaning: Mapped[str | None] = mapped_column(Text)
    localNames: Mapped[list[str]] = mapped_column(
        ARRAY(Text), nullable=False, server_default=text("ARRAY[]::text[]")
    )
    aliases: Mapped[list[str]] = mapped_column(
        ARRAY(Text), nullable=False, server_default=text("ARRAY[]::text[]")
    )
    wikidataId: Mapped[str | None] = mapped_column(String(20))
    zoomLevel: Mapped[str | None] = mapped_column(String(TERM_ZOOM_LEVEL_CHARS))
    createdAt: Mapped[datetime] = created_at()
    updatedAt: Mapped[datetime] = updated_at()

    __table_args__ = (CheckConstraint(one_of("zoomLevel", TERM_ZOOM_LEVELS), name="zoomLevel"),)


class TermCraft(Base):
    __tablename__ = "TermCraft"

    termId: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("Term.id", ondelete="CASCADE"), primary_key=True
    )
    craftId: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("Craft.id", ondelete="CASCADE"), primary_key=True
    )
    createdAt: Mapped[datetime] = created_at()

    __table_args__ = (Index(None, "craftId"),)


class TermConcept(Base):
    __tablename__ = "TermConcept"

    termId: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("Term.id", ondelete="CASCADE"), primary_key=True
    )
    conceptId: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("Concept.id", ondelete="CASCADE"), primary_key=True
    )
    createdAt: Mapped[datetime] = created_at()

    __table_args__ = (Index(None, "conceptId"),)


class TermSummary(Base):
    __tablename__ = "TermSummary"

    id: Mapped[uuid.UUID] = uuid_pk()
    termId: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("Term.id", ondelete="CASCADE"), nullable=False
    )
    language: Mapped[str] = mapped_column(String(16), nullable=False)
    basis: Mapped[str] = mapped_column(String(16), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    claimIds: Mapped[list[uuid.UUID]] = mapped_column(
        ARRAY(UUID(as_uuid=True)), nullable=False, server_default=text("ARRAY[]::uuid[]")
    )
    checkedAt: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    createdAt: Mapped[datetime] = created_at()
    updatedAt: Mapped[datetime] = updated_at()

    __table_args__ = (
        UniqueConstraint("termId", "language"),
        CheckConstraint(one_of("basis", TERM_BASES), name="basis"),
    )


class SharedTermCraft(Base):
    __tablename__ = "SharedTermCraft"

    termId: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("Term.id", ondelete="CASCADE"), primary_key=True
    )
    craftId: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("Craft.id", ondelete="CASCADE"), primary_key=True
    )
    conceptIds: Mapped[list[uuid.UUID]] = mapped_column(ARRAY(UUID(as_uuid=True)), nullable=False)
    claimIds: Mapped[list[uuid.UUID]] = mapped_column(ARRAY(UUID(as_uuid=True)), nullable=False)
    refreshedAt: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        Index(None, "craftId"),
        CheckConstraint('cardinality("conceptIds") > 0', name="concepts"),
        CheckConstraint('cardinality("claimIds") > 0', name="claims"),
    )
