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
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, created_at, one_of, uuid_pk

__all__ = [
    "DECLARATION_CHANNELS",
    "SCREEN_VERDICT_VALUES",
    "ImageFingerprint",
    "ImageScreen",
    "PictureDeclaration",
]

SCREEN_VERDICT_VALUES = ("CLEAR", "FLAGGED", "UNSCREENED")
DECLARATION_CHANNELS = ("WEB", "LINK", "SLOT", "MCP")
MIME_CHARS = 64
FLAG_CHARS = 32
PROVIDER_CHARS = 64
MODEL_CHARS = 120
GENERATOR_CHARS = 120
TERMS_VERSION_CHARS = 40
CONFIRMATION_CHARS = 500


class PictureDeclaration(Base):
    __tablename__ = "PictureDeclaration"

    id: Mapped[uuid.UUID] = uuid_pk()
    contributorId: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("User.id", ondelete="SET NULL")
    )
    craftId: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("Craft.id", ondelete="CASCADE"), nullable=False
    )
    channel: Mapped[str] = mapped_column(String(8), nullable=False)
    origin: Mapped[str] = mapped_column(String(16), nullable=False)
    generator: Mapped[str | None] = mapped_column(String(GENERATOR_CHARS))
    termsVersion: Mapped[str] = mapped_column(String(TERMS_VERSION_CHARS), nullable=False)
    rightsConfirmedAt: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    confirmation: Mapped[str | None] = mapped_column(String(CONFIRMATION_CHARS))
    pictures: Mapped[int] = mapped_column(Integer, nullable=False)
    createdAt: Mapped[datetime] = created_at()

    __table_args__ = (
        CheckConstraint(one_of("channel", DECLARATION_CHANNELS), name="channel"),
        CheckConstraint('"pictures" >= 1', name="pictures"),
        CheckConstraint('"channel" <> \'MCP\' OR "confirmation" IS NOT NULL', name="confirmed"),
        Index(None, "contributorId"),
        Index(None, "craftId"),
    )


class ImageFingerprint(Base):
    __tablename__ = "ImageFingerprint"

    assetId: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("MediaAsset.id", ondelete="CASCADE"), primary_key=True
    )
    fingerprint: Mapped[int] = mapped_column(BigInteger, nullable=False)
    createdAt: Mapped[datetime] = created_at()


class ImageScreen(Base):
    __tablename__ = "ImageScreen"

    id: Mapped[uuid.UUID] = uuid_pk()
    contributionId: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("ImageContribution.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    receivedMime: Mapped[str] = mapped_column(String(MIME_CHARS), nullable=False)
    receivedBytes: Mapped[int] = mapped_column(Integer, nullable=False)
    fingerprint: Mapped[int | None] = mapped_column(BigInteger)
    nearestAssetId: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("MediaAsset.id", ondelete="SET NULL")
    )
    nearestDistance: Mapped[int | None] = mapped_column(SmallInteger)
    verdict: Mapped[str] = mapped_column(String(16), nullable=False)
    flags: Mapped[list[str]] = mapped_column(
        ARRAY(String(FLAG_CHARS)), nullable=False, server_default=text("ARRAY[]::varchar[]")
    )
    reasons: Mapped[list[str]] = mapped_column(
        ARRAY(Text), nullable=False, server_default=text("ARRAY[]::text[]")
    )
    provider: Mapped[str | None] = mapped_column(String(PROVIDER_CHARS))
    model: Mapped[str | None] = mapped_column(String(MODEL_CHARS))
    usageEventId: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("UsageEvent.id", ondelete="SET NULL")
    )
    inputTokens: Mapped[int | None] = mapped_column(Integer)
    outputTokens: Mapped[int | None] = mapped_column(Integer)
    costUsd: Mapped[Decimal] = mapped_column(Numeric(12, 6), nullable=False, server_default=text("0"))
    createdAt: Mapped[datetime] = created_at()

    __table_args__ = (
        CheckConstraint(one_of("verdict", SCREEN_VERDICT_VALUES), name="verdict"),
        CheckConstraint('"costUsd" >= 0', name="cost"),
        CheckConstraint('"verdict" = \'CLEAR\' OR cardinality("reasons") > 0', name="reasoned"),
        Index(None, "nearestAssetId"),
        Index(None, "usageEventId"),
    )
