import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, created_at, one_of, updated_at, uuid_pk

__all__ = [
    "DIGEST_CHARS",
    "LAYER_REVIEW_NOTE_CHARS",
    "LAYER_STATUSES",
    "DatasetTable",
    "DatasetUpload",
    "MapLayerProposal",
]

DIGEST_CHARS = 64
SHA256_CHECK = "~ '^[0-9a-f]{64}$'"
LAYER_STATUSES = ("PENDING", "APPROVED", "REJECTED")
LAYER_REVIEW_NOTE_CHARS = 500
STATUS_CHARS = 16


class DatasetTable(Base):
    __tablename__ = "DatasetTable"

    id: Mapped[uuid.UUID] = uuid_pk()
    datasetId: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("EnvDataset.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    columns: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False)
    rows: Mapped[list[Any]] = mapped_column(JSONB, nullable=False)
    rowCount: Mapped[int] = mapped_column(Integer, nullable=False)
    byteSize: Mapped[int] = mapped_column(Integer, nullable=False)
    sha256: Mapped[str] = mapped_column(String(DIGEST_CHARS), nullable=False)
    createdAt: Mapped[datetime] = created_at()

    __table_args__ = (
        CheckConstraint(f'"sha256" {SHA256_CHECK}', name="sha256"),
        CheckConstraint("jsonb_typeof(\"rows\") = 'array'", name="rows"),
        CheckConstraint('"rowCount" >= 1 AND "byteSize" >= 1', name="size"),
    )


class DatasetUpload(Base):
    __tablename__ = "DatasetUpload"

    id: Mapped[uuid.UUID] = uuid_pk()
    userId: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("User.id", ondelete="CASCADE"), nullable=False
    )
    userTokenVersion: Mapped[int] = mapped_column(Integer, nullable=False)
    slotHash: Mapped[str] = mapped_column(String(DIGEST_CHARS), nullable=False, unique=True)
    record: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    sha256: Mapped[str] = mapped_column(String(DIGEST_CHARS), nullable=False)
    expiresAt: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    usedAt: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    datasetId: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("EnvDataset.id", ondelete="SET NULL")
    )
    createdAt: Mapped[datetime] = created_at()

    __table_args__ = (
        CheckConstraint(f'"sha256" {SHA256_CHECK}', name="sha256"),
        CheckConstraint("jsonb_typeof(\"record\") = 'object'", name="record"),
        CheckConstraint('"datasetId" IS NULL OR "usedAt" IS NOT NULL', name="used"),
        Index(None, "userId", "expiresAt"),
        Index(None, "datasetId"),
    )


class MapLayerProposal(Base):
    __tablename__ = "MapLayerProposal"

    id: Mapped[uuid.UUID] = uuid_pk()
    datasetId: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("EnvDataset.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    proposerId: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("User.id", ondelete="SET NULL")
    )
    plan: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    layer: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    featureCount: Mapped[int] = mapped_column(Integer, nullable=False)
    byteSize: Mapped[int] = mapped_column(Integer, nullable=False)
    sha256: Mapped[str] = mapped_column(String(DIGEST_CHARS), nullable=False)
    status: Mapped[str] = mapped_column(String(STATUS_CHARS), nullable=False, server_default="PENDING")
    reviewedById: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("User.id", ondelete="SET NULL")
    )
    reviewedAt: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reviewNote: Mapped[str | None] = mapped_column(String(LAYER_REVIEW_NOTE_CHARS))
    createdAt: Mapped[datetime] = created_at()
    updatedAt: Mapped[datetime] = updated_at()

    __table_args__ = (
        CheckConstraint(f'"sha256" {SHA256_CHECK}', name="sha256"),
        CheckConstraint(one_of("status", LAYER_STATUSES), name="status"),
        CheckConstraint("jsonb_typeof(\"plan\") = 'object'", name="plan"),
        CheckConstraint("jsonb_typeof(\"layer\") = 'object'", name="layer"),
        CheckConstraint('"featureCount" >= 1 AND "byteSize" >= 1', name="size"),
        CheckConstraint('"status" = \'PENDING\' OR "reviewedAt" IS NOT NULL', name="reviewed"),
        Index(None, "status", "createdAt"),
        Index(None, "proposerId"),
        Index(None, "reviewedById"),
    )
