import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, String
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, created_at, updated_at, uuid_pk
from .image_contributions import SLOT_CHARS
from .open_work import TASK_KEY_COLUMN_CHARS

__all__ = ["DIGEST_CHARS", "UploadLink"]

DIGEST_CHARS = 64


class UploadLink(Base):
    __tablename__ = "UploadLink"

    id: Mapped[uuid.UUID] = uuid_pk()
    userId: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("User.id", ondelete="CASCADE"), nullable=False
    )
    userTokenVersion: Mapped[int] = mapped_column(Integer, nullable=False)
    craftId: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("Craft.id", ondelete="CASCADE"), nullable=False
    )
    stageId: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ProcessStage.id", ondelete="SET NULL")
    )
    materialId: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("Material.id", ondelete="SET NULL")
    )
    slot: Mapped[str | None] = mapped_column(String(SLOT_CHARS))
    taskKey: Mapped[str | None] = mapped_column(String(TASK_KEY_COLUMN_CHARS))
    claimIds: Mapped[list[uuid.UUID]] = mapped_column(ARRAY(UUID(as_uuid=True)), nullable=False)
    linkHash: Mapped[str] = mapped_column(String(DIGEST_CHARS), nullable=False, unique=True)
    slotHash: Mapped[str | None] = mapped_column(String(DIGEST_CHARS), unique=True)
    declaration: Mapped[dict[str, Any] | None] = mapped_column(JSONB(none_as_null=True))
    expiresAt: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    usedAt: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    contributionId: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ImageContribution.id", ondelete="SET NULL")
    )
    createdAt: Mapped[datetime] = created_at()
    updatedAt: Mapped[datetime] = updated_at()

    __table_args__ = (
        CheckConstraint('("slotHash" IS NULL) = ("declaration" IS NULL)', name="slot_declared"),
        CheckConstraint('cardinality("claimIds") >= 1', name="facts"),
        CheckConstraint('"contributionId" IS NULL OR "usedAt" IS NOT NULL', name="used"),
        Index(None, "userId", "expiresAt"),
        Index(None, "contributionId"),
    )
