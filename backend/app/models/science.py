import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    ColumnElement,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    text as sql_text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models import enums as e
from app.models.base import Base, created_at, updated_at, uuid_pk

CONDITION_KEY_MAX_CHARS = 40


class Process(Base):
    __tablename__ = "Process"

    id: Mapped[uuid.UUID] = uuid_pk()
    craftId: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("Craft.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(300), nullable=False)
    variant: Mapped[str | None] = mapped_column(String(200))
    archivedAt: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    createdAt: Mapped[datetime] = created_at()
    updatedAt: Mapped[datetime] = updated_at()

    __table_args__ = (Index(None, "craftId"),)


def live_process() -> ColumnElement[bool]:
    return Process.archivedAt.is_(None)


class ProcessStage(Base):
    __tablename__ = "ProcessStage"

    id: Mapped[uuid.UUID] = uuid_pk()
    processId: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("Process.id", ondelete="CASCADE"), nullable=False
    )
    ordinal: Mapped[int] = mapped_column(Integer, nullable=False)
    conceptId: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("Concept.id", ondelete="SET NULL")
    )
    name: Mapped[str] = mapped_column(String(300), nullable=False)
    stageType: Mapped[str] = mapped_column(e.StageType, nullable=False, server_default="OTHER")
    ordered: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=sql_text("true"))
    durationText: Mapped[str | None] = mapped_column(String(200))
    tempMinC: Mapped[Decimal | None] = mapped_column(Numeric(8, 2))
    tempMaxC: Mapped[Decimal | None] = mapped_column(Numeric(8, 2))
    phMin: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    phMax: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    medium: Mapped[str | None] = mapped_column(String(200))
    createdAt: Mapped[datetime] = created_at()
    updatedAt: Mapped[datetime] = updated_at()

    __table_args__ = (UniqueConstraint("processId", "ordinal"),)


class Compound(Base):
    __tablename__ = "Compound"

    id: Mapped[uuid.UUID] = uuid_pk()
    pubchemCid: Mapped[int | None] = mapped_column(Integer, unique=True)
    name: Mapped[str] = mapped_column(String(300), nullable=False)
    formula: Mapped[str | None] = mapped_column(String(200))
    iupacName: Mapped[str | None] = mapped_column(Text)
    smiles: Mapped[str | None] = mapped_column(Text)
    inchiKey: Mapped[str | None] = mapped_column(String(27), unique=True)
    molecularWeight: Mapped[Decimal | None] = mapped_column(Numeric(12, 4))
    synonyms: Mapped[list[str]] = mapped_column(
        ARRAY(Text), nullable=False, server_default=sql_text("ARRAY[]::text[]")
    )
    hazards: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    sourceId: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("Source.id", ondelete="SET NULL")
    )
    conformerKeptAt: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    createdAt: Mapped[datetime] = created_at()
    updatedAt: Mapped[datetime] = updated_at()

    __table_args__ = (Index(None, "formula"),)


class Material(Base):
    __tablename__ = "Material"

    id: Mapped[uuid.UUID] = uuid_pk()
    name: Mapped[str] = mapped_column(String(300), nullable=False)
    nameNorm: Mapped[str] = mapped_column(String(300), nullable=False)
    kind: Mapped[str] = mapped_column(e.MaterialKind, nullable=False, server_default="OTHER")
    description: Mapped[str | None] = mapped_column(Text)
    conceptId: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("Concept.id", ondelete="SET NULL")
    )
    compoundId: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("Compound.id", ondelete="SET NULL")
    )
    createdAt: Mapped[datetime] = created_at()
    updatedAt: Mapped[datetime] = updated_at()

    __table_args__ = (UniqueConstraint("nameNorm", "conceptId", postgresql_nulls_not_distinct=True),)


class StageMaterial(Base):
    __tablename__ = "StageMaterial"

    id: Mapped[uuid.UUID] = uuid_pk()
    stageId: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ProcessStage.id", ondelete="CASCADE"), nullable=False
    )
    materialId: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("Material.id", ondelete="CASCADE"), nullable=False
    )
    role: Mapped[str] = mapped_column(e.MaterialRole, nullable=False, server_default="INPUT")
    quantityText: Mapped[str | None] = mapped_column(String(200))
    claimId: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("Claim.id", ondelete="SET NULL")
    )
    createdAt: Mapped[datetime] = created_at()
    updatedAt: Mapped[datetime] = updated_at()

    __table_args__ = (UniqueConstraint("stageId", "materialId", "role"), Index(None, "materialId"))


class Reaction(Base):
    __tablename__ = "Reaction"

    id: Mapped[uuid.UUID] = uuid_pk()
    stageId: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ProcessStage.id", ondelete="CASCADE"), nullable=False
    )
    ordinal: Mapped[int] = mapped_column(Integer, nullable=False, server_default=sql_text("0"))
    kind: Mapped[str] = mapped_column(e.ReactionKind, nullable=False, server_default="OTHER")
    label: Mapped[str] = mapped_column(String(200), nullable=False)
    species: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB, nullable=False, server_default=sql_text("'[]'::jsonb")
    )
    equationInput: Mapped[str | None] = mapped_column(Text)
    equationBalanced: Mapped[str | None] = mapped_column(Text)
    coefficients: Mapped[list[int] | None] = mapped_column(ARRAY(Integer))
    balanced: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=sql_text("false"))
    checkerVersion: Mapped[str | None] = mapped_column(String(40))
    deltaHKjMol: Mapped[Decimal | None] = mapped_column(Numeric(12, 3))
    deltaHClaimId: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("Claim.id", ondelete="SET NULL")
    )
    createdAt: Mapped[datetime] = created_at()
    updatedAt: Mapped[datetime] = updated_at()

    __table_args__ = (Index(None, "stageId"),)


class ReactionCitation(Base):
    __tablename__ = "ReactionCitation"

    id: Mapped[uuid.UUID] = uuid_pk()
    reactionId: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("Reaction.id", ondelete="CASCADE"), nullable=False
    )
    claimSourceId: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ClaimSource.id", ondelete="CASCADE"), nullable=False
    )
    createdAt: Mapped[datetime] = created_at()
    updatedAt: Mapped[datetime] = updated_at()

    __table_args__ = (UniqueConstraint("reactionId", "claimSourceId"), Index(None, "claimSourceId"))


class ProcessCondition(Base):
    __tablename__ = "ProcessCondition"

    id: Mapped[uuid.UUID] = uuid_pk()
    stageId: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ProcessStage.id", ondelete="CASCADE")
    )
    reactionId: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("Reaction.id", ondelete="CASCADE")
    )
    key: Mapped[str] = mapped_column(String(CONDITION_KEY_MAX_CHARS), nullable=False)
    label: Mapped[str] = mapped_column(String(120), nullable=False)
    quantity: Mapped[str] = mapped_column(String(20), nullable=False)
    createdAt: Mapped[datetime] = created_at()
    updatedAt: Mapped[datetime] = updated_at()

    __table_args__ = (
        CheckConstraint('num_nonnulls("stageId", "reactionId") = 1', name="one_owner"),
        UniqueConstraint("stageId", "reactionId", "key", postgresql_nulls_not_distinct=True),
        Index(None, "reactionId"),
    )


class ConditionReading(Base):
    __tablename__ = "ConditionReading"

    id: Mapped[uuid.UUID] = uuid_pk()
    conditionId: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ProcessCondition.id", ondelete="CASCADE"), nullable=False
    )
    claimSourceId: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ClaimSource.id", ondelete="CASCADE"), nullable=False
    )
    stated: Mapped[str] = mapped_column(String(200), nullable=False)
    statedMin: Mapped[Decimal | None] = mapped_column(Numeric(14, 4))
    statedMax: Mapped[Decimal | None] = mapped_column(Numeric(14, 4))
    statedUnit: Mapped[str] = mapped_column(String(40), nullable=False)
    createdAt: Mapped[datetime] = created_at()
    updatedAt: Mapped[datetime] = updated_at()

    __table_args__ = (
        CheckConstraint('num_nonnulls("statedMin", "statedMax") >= 1', name="bounded"),
        UniqueConstraint("conditionId", "claimSourceId", "stated"),
        Index(None, "claimSourceId"),
    )
