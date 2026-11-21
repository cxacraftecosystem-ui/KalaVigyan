import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    SmallInteger,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, one_of, uuid_pk
from .field_voices import SHA256_CHECK
from .image_screens import SCREEN_VERDICT_VALUES

__all__ = ["HIDE_REASON_VALUES", "PHOTO_DECISION_VALUES", "FieldPhotoReview", "FieldPhotoScreen"]

PHOTO_DECISION_VALUES = ("SHOW", "HIDE", "CROP")
HIDE_REASON_VALUES = (
    "IDENTITY_DOCUMENT",
    "NOT_AGREED",
    "PRIVATE_PLACE",
    "POOR_QUALITY",
    "NOT_THIS_CRAFT",
    "OTHER",
)
CROP_COLUMNS = '"cropLeft", "cropTop", "cropWidth", "cropHeight", "cropKey", "cropSha256", "cropMime"'
FLAG_CHARS = 32
STAMP = DateTime(timezone=True)


class FieldPhotoReview(Base):
    __tablename__ = "FieldPhotoReview"

    id: Mapped[uuid.UUID] = uuid_pk()
    imageId: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("FieldImage.id", ondelete="SET NULL"), unique=True
    )
    imageSha256: Mapped[str] = mapped_column(String(64), nullable=False)
    decision: Mapped[str] = mapped_column(String(8), nullable=False)
    reason: Mapped[str | None] = mapped_column(String(24))
    note: Mapped[str | None] = mapped_column(Text)
    clearedFlags: Mapped[list[str]] = mapped_column(
        ARRAY(String(FLAG_CHARS)), nullable=False, server_default=text("ARRAY[]::varchar[]")
    )
    cropLeft: Mapped[int | None] = mapped_column(Integer)
    cropTop: Mapped[int | None] = mapped_column(Integer)
    cropWidth: Mapped[int | None] = mapped_column(Integer)
    cropHeight: Mapped[int | None] = mapped_column(Integer)
    cropKey: Mapped[str | None] = mapped_column(Text)
    cropSha256: Mapped[str | None] = mapped_column(String(64))
    cropMime: Mapped[str | None] = mapped_column(String(16))
    deciderId: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("User.id", ondelete="SET NULL")
    )
    deciderRole: Mapped[str] = mapped_column(String(20), nullable=False)
    decidedAt: Mapped[datetime] = mapped_column(STAMP, nullable=False, server_default=func.now())

    __table_args__ = (
        CheckConstraint(one_of("decision", PHOTO_DECISION_VALUES), name="decision"),
        CheckConstraint(f'"reason" IS NULL OR {one_of("reason", HIDE_REASON_VALUES)}', name="reason"),
        CheckConstraint('("decision" = \'HIDE\') = ("reason" IS NOT NULL)', name="reasoned"),
        CheckConstraint('"reason" IS DISTINCT FROM \'OTHER\' OR "note" IS NOT NULL', name="noted"),
        CheckConstraint('("decision" = \'CROP\') = ("cropKey" IS NOT NULL)', name="cropped"),
        CheckConstraint(f"num_nonnulls({CROP_COLUMNS}) IN (0, 7)", name="crop"),
        CheckConstraint(f'"imageSha256" {SHA256_CHECK}', name="imageSha256"),
        Index(None, "deciderId"),
    )


class FieldPhotoScreen(Base):
    __tablename__ = "FieldPhotoScreen"

    imageId: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("FieldImage.id", ondelete="CASCADE"), primary_key=True
    )
    imageSha256: Mapped[str] = mapped_column(String(64), nullable=False)
    fingerprint: Mapped[int | None] = mapped_column(BigInteger)
    nearestAssetId: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("MediaAsset.id", ondelete="SET NULL")
    )
    nearestImageId: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("FieldImage.id", ondelete="SET NULL")
    )
    nearestDistance: Mapped[int | None] = mapped_column(SmallInteger)
    verdict: Mapped[str] = mapped_column(String(16), nullable=False)
    flags: Mapped[list[str]] = mapped_column(
        ARRAY(String(FLAG_CHARS)), nullable=False, server_default=text("ARRAY[]::varchar[]")
    )
    reasons: Mapped[list[str]] = mapped_column(
        ARRAY(Text), nullable=False, server_default=text("ARRAY[]::text[]")
    )
    provider: Mapped[str | None] = mapped_column(String(64))
    model: Mapped[str | None] = mapped_column(String(120))
    usageEventId: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("UsageEvent.id", ondelete="SET NULL")
    )
    inputTokens: Mapped[int | None] = mapped_column(Integer)
    outputTokens: Mapped[int | None] = mapped_column(Integer)
    costUsd: Mapped[Decimal] = mapped_column(Numeric(12, 6), nullable=False, server_default=text("0"))
    screenedAt: Mapped[datetime] = mapped_column(STAMP, nullable=False, server_default=func.now())

    __table_args__ = (
        CheckConstraint(one_of("verdict", SCREEN_VERDICT_VALUES), name="verdict"),
        CheckConstraint('"costUsd" >= 0', name="cost"),
        CheckConstraint('"verdict" = \'CLEAR\' OR cardinality("reasons") > 0', name="reasoned"),
        CheckConstraint(f'"imageSha256" {SHA256_CHECK}', name="imageSha256"),
        Index(None, "nearestAssetId"),
        Index(None, "nearestImageId"),
        Index(None, "usageEventId"),
    )
