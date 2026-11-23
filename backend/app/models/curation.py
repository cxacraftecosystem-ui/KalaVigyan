import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, created_at, one_of, updated_at, uuid_pk
from app.models.enums import COVERAGE_CLASSES, DISCIPLINES

CURATED_KEY_COLUMN_CHARS = 8
DIGEST_COLUMN_CHARS = 64
PARTIAL_DATE_COLUMN_CHARS = 10
PARTIAL_DATE_CHECK = "~ '^[0-9]{4}(-[0-9]{2}(-[0-9]{2})?)?$'"
YEAR_RANGE = (1000, 2100)


class CuratedCraft(Base):
    __tablename__ = "CuratedCraft"

    craftId: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("Craft.id", ondelete="CASCADE"), primary_key=True
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    curatedAt: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    coverage: Mapped[str] = mapped_column(String(8), nullable=False)
    digest: Mapped[str] = mapped_column(String(DIGEST_COLUMN_CHARS), nullable=False)
    page: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    importedAt: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    createdAt: Mapped[datetime] = created_at()
    updatedAt: Mapped[datetime] = updated_at()

    __table_args__ = (
        CheckConstraint('"version" >= 1', name="version"),
        CheckConstraint(one_of("coverage", COVERAGE_CLASSES), name="coverage"),
        CheckConstraint("\"digest\" ~ '^[0-9a-f]{64}$'", name="digest"),
    )


class CuratedClaim(Base):
    __tablename__ = "CuratedClaim"

    claimId: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("Claim.id", ondelete="CASCADE"), primary_key=True
    )
    craftId: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("Craft.id", ondelete="CASCADE"), nullable=False
    )
    key: Mapped[str] = mapped_column(String(CURATED_KEY_COLUMN_CHARS), nullable=False)
    discipline: Mapped[str] = mapped_column(String(16), nullable=False)
    createdAt: Mapped[datetime] = created_at()
    updatedAt: Mapped[datetime] = updated_at()

    __table_args__ = (
        CheckConstraint(one_of("discipline", DISCIPLINES), name="discipline"),
        UniqueConstraint("craftId", "key"),
    )


class CuratedCategory(Base):
    __tablename__ = "CuratedCategory"

    categoryId: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("CraftCategory.id", ondelete="CASCADE"), primary_key=True
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    curatedAt: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    coverage: Mapped[str] = mapped_column(String(8), nullable=False)
    digest: Mapped[str] = mapped_column(String(DIGEST_COLUMN_CHARS), nullable=False)
    page: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    importedAt: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    createdAt: Mapped[datetime] = created_at()
    updatedAt: Mapped[datetime] = updated_at()

    __table_args__ = (
        CheckConstraint('"version" >= 1', name="version"),
        CheckConstraint(one_of("coverage", COVERAGE_CLASSES), name="coverage"),
        CheckConstraint("\"digest\" ~ '^[0-9a-f]{64}$'", name="digest"),
    )


class CuratedCategoryClaim(Base):
    __tablename__ = "CuratedCategoryClaim"

    claimId: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("Claim.id", ondelete="CASCADE"), primary_key=True
    )
    categoryId: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("CraftCategory.id", ondelete="CASCADE"), nullable=False
    )
    key: Mapped[str] = mapped_column(String(CURATED_KEY_COLUMN_CHARS), nullable=False)
    discipline: Mapped[str] = mapped_column(String(16), nullable=False)
    createdAt: Mapped[datetime] = created_at()
    updatedAt: Mapped[datetime] = updated_at()

    __table_args__ = (
        CheckConstraint(one_of("discipline", DISCIPLINES), name="discipline"),
        UniqueConstraint("categoryId", "key"),
    )


class CraftGiRecord(Base):
    __tablename__ = "CraftGiRecord"

    craftId: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("Craft.id", ondelete="CASCADE"), primary_key=True
    )
    applicationNumber: Mapped[str | None] = mapped_column(String(40))
    certificateNumber: Mapped[str | None] = mapped_column(String(40))
    filedOn: Mapped[str | None] = mapped_column(String(PARTIAL_DATE_COLUMN_CHARS))
    registeredOn: Mapped[str | None] = mapped_column(String(PARTIAL_DATE_COLUMN_CHARS))
    journalIssue: Mapped[str | None] = mapped_column(String(100))
    proprietors: Mapped[list[str]] = mapped_column(
        ARRAY(Text), nullable=False, server_default=text("ARRAY[]::text[]")
    )
    authorisedUserCount: Mapped[int | None] = mapped_column(Integer)
    claimIds: Mapped[list[uuid.UUID]] = mapped_column(ARRAY(UUID(as_uuid=True)), nullable=False)
    imitationClaimIds: Mapped[list[uuid.UUID]] = mapped_column(
        ARRAY(UUID(as_uuid=True)), nullable=False, server_default=text("ARRAY[]::uuid[]")
    )
    createdAt: Mapped[datetime] = created_at()
    updatedAt: Mapped[datetime] = updated_at()

    __table_args__ = (
        CheckConstraint(f'"filedOn" {PARTIAL_DATE_CHECK}', name="filedOn"),
        CheckConstraint(f'"registeredOn" {PARTIAL_DATE_CHECK}', name="registeredOn"),
        CheckConstraint('"authorisedUserCount" >= 0', name="authorisedUserCount"),
        CheckConstraint('cardinality("claimIds") > 0', name="claimIds"),
    )


class CraftPrice(Base):
    __tablename__ = "CraftPrice"

    id: Mapped[uuid.UUID] = uuid_pk()
    craftId: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("Craft.id", ondelete="CASCADE"), nullable=False
    )
    claimId: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("Claim.id", ondelete="CASCADE"), nullable=False
    )
    pricedOn: Mapped[str] = mapped_column(String(PARTIAL_DATE_COLUMN_CHARS), nullable=False)
    placeName: Mapped[str] = mapped_column(String(300), nullable=False)
    stateLgd: Mapped[int | None] = mapped_column(Integer, ForeignKey("AdminState.lgd", ondelete="SET NULL"))
    districtLgd: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("AdminDistrict.lgd", ondelete="SET NULL")
    )
    createdAt: Mapped[datetime] = created_at()
    updatedAt: Mapped[datetime] = updated_at()

    __table_args__ = (
        CheckConstraint(f'"pricedOn" {PARTIAL_DATE_CHECK}', name="pricedOn"),
        Index(None, "craftId"),
        Index(None, "claimId"),
    )


class CraftWorkforce(Base):
    __tablename__ = "CraftWorkforce"

    id: Mapped[uuid.UUID] = uuid_pk()
    craftId: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("Craft.id", ondelete="CASCADE"), nullable=False
    )
    claimId: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("Claim.id", ondelete="CASCADE"), nullable=False
    )
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    createdAt: Mapped[datetime] = created_at()
    updatedAt: Mapped[datetime] = updated_at()

    __table_args__ = (
        CheckConstraint(f'"year" BETWEEN {YEAR_RANGE[0]} AND {YEAR_RANGE[1]}', name="year"),
        Index(None, "craftId"),
        Index(None, "claimId"),
    )
