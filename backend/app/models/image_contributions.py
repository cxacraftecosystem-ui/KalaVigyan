import uuid
from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Index, String, Text, text
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, created_at, one_of, updated_at, uuid_pk
from app.models.enums import IMAGE_CONTRIBUTION_STATUSES, IMAGE_ORIGINS
from app.models.open_work import TASK_KEY_COLUMN_CHARS

IMAGE_TEXT_CHARS = 300
GENERATOR_CHARS = 120
TERMS_VERSION_CHARS = 40
REVIEW_NOTE_CHARS = 500
DIGEST_CHARS = 64
SLOT_CHARS = 16
ONE_TARGET = 'num_nonnulls("stageId", "materialId", "slot") <= 1'
AI_GENERATED = "AI_GENERATED"
WITH_FILE = ("PENDING", "APPROVED")
REVIEWED = ("APPROVED", "REJECTED")


class ImageContribution(Base):
    __tablename__ = "ImageContribution"

    id: Mapped[uuid.UUID] = uuid_pk()
    contributorId: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("User.id", ondelete="SET NULL")
    )
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
    declarationId: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("PictureDeclaration.id", ondelete="SET NULL")
    )
    claimIds: Mapped[list[uuid.UUID]] = mapped_column(
        ARRAY(UUID(as_uuid=True)), nullable=False, server_default=text("ARRAY[]::uuid[]")
    )
    origin: Mapped[str] = mapped_column(String(16), nullable=False)
    generator: Mapped[str | None] = mapped_column(String(GENERATOR_CHARS))
    prompt: Mapped[str | None] = mapped_column(Text)
    caption: Mapped[str] = mapped_column(String(IMAGE_TEXT_CHARS), nullable=False)
    altText: Mapped[str] = mapped_column(String(IMAGE_TEXT_CHARS), nullable=False)
    termsVersion: Mapped[str] = mapped_column(String(TERMS_VERSION_CHARS), nullable=False)
    rightsConfirmedAt: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, server_default="AWAITING_FILE")
    assetId: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("MediaAsset.id", ondelete="SET NULL")
    )
    sha256: Mapped[str | None] = mapped_column(String(DIGEST_CHARS))
    aiMarked: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    reviewedById: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("User.id", ondelete="SET NULL")
    )
    reviewedAt: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reviewNote: Mapped[str | None] = mapped_column(String(REVIEW_NOTE_CHARS))
    createdAt: Mapped[datetime] = created_at()
    updatedAt: Mapped[datetime] = updated_at()

    __table_args__ = (
        CheckConstraint(one_of("origin", IMAGE_ORIGINS), name="origin"),
        CheckConstraint(one_of("status", IMAGE_CONTRIBUTION_STATUSES), name="status"),
        CheckConstraint(
            f'"origin" <> \'{AI_GENERATED}\' OR ("generator" IS NOT NULL AND "prompt" IS NOT NULL '
            'AND cardinality("claimIds") > 0)',
            name="ai_declared",
        ),
        CheckConstraint(f'NOT {one_of("status", WITH_FILE)} OR "assetId" IS NOT NULL', name="file"),
        CheckConstraint(f'NOT {one_of("status", REVIEWED)} OR "reviewedAt" IS NOT NULL', name="reviewed"),
        CheckConstraint(ONE_TARGET, name="one_target"),
        Index(None, "status", "createdAt"),
        Index(None, "craftId"),
        Index(None, "contributorId"),
        Index(None, "assetId"),
        Index(None, "sha256"),
        Index(None, "declarationId"),
        Index(None, "taskKey"),
    )
