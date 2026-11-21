import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, created_at, uuid_pk

__all__ = ["DIGEST_CHARS", "DatasetTable", "DatasetUpload"]

DIGEST_CHARS = 64
SHA256_CHECK = "~ '^[0-9a-f]{64}$'"


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
