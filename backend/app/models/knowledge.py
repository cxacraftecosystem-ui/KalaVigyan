import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Computed,
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
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, TSVECTOR, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models import enums as e
from app.models.base import Base, created_at, one_of, subset_of, updated_at, uuid_pk
from app.models.crafts import EMBEDDING_DIMENSIONS, EMBEDDING_MODEL_CHARS

QUOTE_MAX_CHARS = 300
CONTAINER_TITLE_CHARS = 300
FIELD_COLUMN_CHARS = 16
CHUNK_KIND_CHARS = 16
DIFFERS_ON_CHARS = 300


class Source(Base):
    __tablename__ = "Source"

    id: Mapped[uuid.UUID] = uuid_pk()
    kind: Mapped[str] = mapped_column(e.SourceKind, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    authors: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, server_default=sql_text("'[]'::jsonb"))
    year: Mapped[int | None] = mapped_column(Integer)
    doi: Mapped[str | None] = mapped_column(String(255))
    url: Mapped[str | None] = mapped_column(Text)
    publisher: Mapped[str | None] = mapped_column(String(300))
    containerTitle: Mapped[str | None] = mapped_column(String(CONTAINER_TITLE_CHARS))
    licence: Mapped[str | None] = mapped_column(String(200))
    reliability: Mapped[str] = mapped_column(e.Reliability, nullable=False, server_default="C")
    storage: Mapped[str] = mapped_column(e.SourceStorage, nullable=False, server_default="LINK_ONLY")
    snapshotKey: Mapped[str | None] = mapped_column(Text)
    sha256: Mapped[str | None] = mapped_column(String(64))
    retrievedAt: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    addedById: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("User.id", ondelete="SET NULL")
    )
    origin: Mapped[str] = mapped_column(e.SourceOrigin, nullable=False, server_default="IMPORT")
    sensitivity: Mapped[str] = mapped_column(e.Sensitivity, nullable=False, server_default="OPEN")
    attribution: Mapped[str | None] = mapped_column(Text)
    evidenceKind: Mapped[str | None] = mapped_column(String(80))
    notes: Mapped[str | None] = mapped_column(Text)
    externalIds: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default=sql_text("'{}'::jsonb")
    )
    createdAt: Mapped[datetime] = created_at()
    updatedAt: Mapped[datetime] = updated_at()

    __table_args__ = (
        Index("Source_doi_key", "doi", unique=True, postgresql_where=sql_text("doi IS NOT NULL")),
        Index(None, "url"),
        Index(None, "origin"),
        CheckConstraint('"containerTitle" IS NULL OR "containerTitle" <> \'\'', name="containerTitle"),
    )


class Chunk(Base):
    __tablename__ = "Chunk"

    id: Mapped[uuid.UUID] = uuid_pk()
    sourceId: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("Source.id", ondelete="CASCADE"), nullable=False
    )
    ordinal: Mapped[int] = mapped_column(Integer, nullable=False)
    locator: Mapped[str | None] = mapped_column(String(300))
    text: Mapped[str] = mapped_column(Text, nullable=False)
    tsv: Mapped[Any] = mapped_column(
        TSVECTOR, Computed("to_tsvector('english'::regconfig, coalesce(\"text\", ''))", persisted=True)
    )
    embedding: Mapped[list[float] | None] = mapped_column(Vector(EMBEDDING_DIMENSIONS))
    embeddingModel: Mapped[str | None] = mapped_column(String(EMBEDDING_MODEL_CHARS))
    lang: Mapped[str] = mapped_column(String(16), nullable=False, server_default="en")
    acl: Mapped[str] = mapped_column(e.ChunkAcl, nullable=False, server_default="PUBLIC")
    kind: Mapped[str] = mapped_column(String(CHUNK_KIND_CHARS), nullable=False, server_default="PASSAGE")
    sensitivity: Mapped[str] = mapped_column(e.Sensitivity, nullable=False, server_default="OPEN")
    createdAt: Mapped[datetime] = created_at()
    updatedAt: Mapped[datetime] = updated_at()

    __table_args__ = (
        UniqueConstraint("sourceId", "ordinal"),
        CheckConstraint(one_of("kind", e.CHUNK_KINDS), name="kind"),
        Index("Chunk_tsv_gin_idx", "tsv", postgresql_using="gin"),
        Index(
            "Chunk_embedding_hnsw_idx",
            "embedding",
            postgresql_using="hnsw",
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
        Index(None, "acl", "sensitivity"),
    )


class Concept(Base):
    __tablename__ = "Concept"

    id: Mapped[uuid.UUID] = uuid_pk()
    craftId: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("Craft.id", ondelete="CASCADE")
    )
    subCategoryId: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("CraftSubCategory.id", ondelete="CASCADE")
    )
    type: Mapped[str] = mapped_column(e.ConceptType, nullable=False)
    name: Mapped[str] = mapped_column(String(300), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    originRef: Mapped[str | None] = mapped_column(Text)
    sensitivity: Mapped[str] = mapped_column(e.Sensitivity, nullable=False, server_default="OPEN")
    createdAt: Mapped[datetime] = created_at()
    updatedAt: Mapped[datetime] = updated_at()

    __table_args__ = (Index(None, "craftId", "type"), Index(None, "subCategoryId"))


class ConceptEdge(Base):
    __tablename__ = "ConceptEdge"

    id: Mapped[uuid.UUID] = uuid_pk()
    srcId: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("Concept.id", ondelete="CASCADE"), nullable=False
    )
    dstId: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("Concept.id", ondelete="CASCADE"), nullable=False
    )
    relation: Mapped[str] = mapped_column(e.ConceptRelation, nullable=False)
    sourceRelation: Mapped[str | None] = mapped_column(String(80))
    claimId: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("Claim.id", ondelete="SET NULL")
    )
    createdAt: Mapped[datetime] = created_at()
    updatedAt: Mapped[datetime] = updated_at()

    __table_args__ = (UniqueConstraint("srcId", "dstId", "relation"), Index(None, "dstId"))


class Claim(Base):
    __tablename__ = "Claim"

    id: Mapped[uuid.UUID] = uuid_pk()
    subjectType: Mapped[str] = mapped_column(String(40), nullable=False)
    subjectId: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    predicate: Mapped[str] = mapped_column(String(120), nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    textLang: Mapped[str] = mapped_column(String(16), nullable=False, server_default="en")
    valueNum: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    valueUnit: Mapped[str | None] = mapped_column(String(40))
    evidenceLevel: Mapped[str] = mapped_column(e.EvidenceLevel, nullable=False)
    levelReason: Mapped[str | None] = mapped_column(Text)
    origin: Mapped[str] = mapped_column(e.ClaimOrigin, nullable=False)
    status: Mapped[str] = mapped_column(e.ClaimStatus, nullable=False, server_default="APPROVED")
    version: Mapped[int] = mapped_column(Integer, nullable=False, server_default=sql_text("1"))
    supersedesId: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("Claim.id", ondelete="SET NULL")
    )
    createdById: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("User.id", ondelete="SET NULL")
    )
    createdByKind: Mapped[str] = mapped_column(e.ActorKind, nullable=False, server_default="SYSTEM")
    sensitivity: Mapped[str] = mapped_column(e.Sensitivity, nullable=False, server_default="OPEN")
    sourcesDiffer: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=sql_text("false"))
    differsOn: Mapped[str | None] = mapped_column(String(DIFFERS_ON_CHARS))
    field: Mapped[str | None] = mapped_column(String(FIELD_COLUMN_CHARS))
    fields: Mapped[list[str]] = mapped_column(
        ARRAY(Text), nullable=False, server_default=sql_text("ARRAY[]::text[]")
    )
    embedding: Mapped[list[float] | None] = mapped_column(Vector(EMBEDDING_DIMENSIONS))
    embeddingModel: Mapped[str | None] = mapped_column(String(EMBEDDING_MODEL_CHARS))
    tsv: Mapped[Any] = mapped_column(
        TSVECTOR, Computed("to_tsvector('english'::regconfig, coalesce(\"text\", ''))", persisted=True)
    )
    createdAt: Mapped[datetime] = created_at()
    updatedAt: Mapped[datetime] = updated_at()

    __table_args__ = (
        Index(None, "subjectType", "subjectId", "evidenceLevel", "status"),
        Index("Claim_tsv_gin_idx", "tsv", postgresql_using="gin"),
        Index(
            "Claim_embedding_hnsw_idx",
            "embedding",
            postgresql_using="hnsw",
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
        Index(None, "supersedesId"),
        CheckConstraint('"field" IS NULL OR ' + one_of("field", e.DISCIPLINES), name="field"),
        CheckConstraint(subset_of("fields", e.DISCIPLINES), name="fields"),
        CheckConstraint('"field" IS NOT NULL OR cardinality("fields") = 0', name="fields_need_field"),
        CheckConstraint('NOT ("field" = ANY ("fields"))', name="field_once"),
        Index(None, "field"),
        Index("Claim_fields_gin_idx", "fields", postgresql_using="gin"),
    )


class ClaimSource(Base):
    __tablename__ = "ClaimSource"

    id: Mapped[uuid.UUID] = uuid_pk()
    claimId: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("Claim.id", ondelete="CASCADE"), nullable=False
    )
    sourceId: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("Source.id", ondelete="RESTRICT"), nullable=False
    )
    chunkId: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("Chunk.id", ondelete="SET NULL")
    )
    locator: Mapped[str | None] = mapped_column(String(300))
    quote: Mapped[str | None] = mapped_column(String(QUOTE_MAX_CHARS))
    quoteCheck: Mapped[str] = mapped_column(e.QuoteCheck, nullable=False, server_default="NA")
    checkedAt: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    relation: Mapped[str] = mapped_column(e.SourceRelation, nullable=False, server_default="DIRECT")
    foundBy: Mapped[str | None] = mapped_column(String(20))
    answerId: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("Answer.id", ondelete="SET NULL")
    )
    retrievedAt: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    createdAt: Mapped[datetime] = created_at()
    updatedAt: Mapped[datetime] = updated_at()

    __table_args__ = (Index(None, "claimId"), Index(None, "sourceId"), Index(None, "answerId"))


class ReviewEvent(Base):
    __tablename__ = "ReviewEvent"

    id: Mapped[uuid.UUID] = uuid_pk()
    claimId: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("Claim.id", ondelete="CASCADE"), nullable=False
    )
    actorId: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("User.id", ondelete="SET NULL")
    )
    actorKind: Mapped[str] = mapped_column(e.ActorKind, nullable=False)
    systemActor: Mapped[str | None] = mapped_column(String(40))
    fromStatus: Mapped[str | None] = mapped_column(e.ClaimStatus)
    toStatus: Mapped[str | None] = mapped_column(e.ClaimStatus)
    fromLevel: Mapped[str | None] = mapped_column(e.EvidenceLevel)
    toLevel: Mapped[str | None] = mapped_column(e.EvidenceLevel)
    note: Mapped[str | None] = mapped_column(Text)
    createdAt: Mapped[datetime] = created_at()

    __table_args__ = (Index(None, "claimId", "createdAt"), Index(None, "actorId"))


class EnrichmentJob(Base):
    __tablename__ = "EnrichmentJob"

    id: Mapped[uuid.UUID] = uuid_pk()
    craftId: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("Craft.id", ondelete="CASCADE"), nullable=False
    )
    requestedById: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("User.id", ondelete="SET NULL")
    )
    mode: Mapped[str] = mapped_column(String(40), nullable=False, server_default="T3")
    facets: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, server_default=sql_text("'[]'::jsonb"))
    budgetUsd: Mapped[Decimal] = mapped_column(Numeric(10, 4), nullable=False, server_default=sql_text("2"))
    spentUsd: Mapped[Decimal] = mapped_column(Numeric(10, 4), nullable=False, server_default=sql_text("0"))
    status: Mapped[str] = mapped_column(e.JobStatus, nullable=False, server_default="QUEUED")
    error: Mapped[str | None] = mapped_column(Text)
    startedAt: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finishedAt: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    createdAt: Mapped[datetime] = created_at()
    updatedAt: Mapped[datetime] = updated_at()

    __table_args__ = (
        CheckConstraint('"budgetUsd" <= 10', name="budget_max"),
        Index(None, "craftId", "status"),
    )


class EnrichmentProposal(Base):
    __tablename__ = "EnrichmentProposal"

    id: Mapped[uuid.UUID] = uuid_pk()
    jobId: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("EnrichmentJob.id", ondelete="CASCADE"), nullable=False
    )
    claimId: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("Claim.id", ondelete="CASCADE"), nullable=False
    )
    dedupeOfClaimId: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("Claim.id", ondelete="SET NULL")
    )
    checks: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default=sql_text("'{}'::jsonb")
    )
    createdAt: Mapped[datetime] = created_at()
    updatedAt: Mapped[datetime] = updated_at()

    __table_args__ = (Index(None, "jobId"), Index(None, "claimId"))


class Objection(Base):
    __tablename__ = "Objection"

    id: Mapped[uuid.UUID] = uuid_pk()
    craftId: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("Craft.id", ondelete="SET NULL")
    )
    claimId: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("Claim.id", ondelete="SET NULL")
    )
    mediaAssetId: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("MediaAsset.id", ondelete="SET NULL")
    )
    answerId: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("Answer.id", ondelete="SET NULL")
    )
    raisedById: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("User.id", ondelete="SET NULL")
    )
    contactEmail: Mapped[str | None] = mapped_column(String(320))
    kind: Mapped[str] = mapped_column(e.ObjectionKind, nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(e.ObjectionStatus, nullable=False, server_default="OPEN")
    ackDueAt: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    decideDueAt: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    decidedById: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("User.id", ondelete="SET NULL")
    )
    decidedAt: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    decisionNote: Mapped[str | None] = mapped_column(Text)
    createdAt: Mapped[datetime] = created_at()
    updatedAt: Mapped[datetime] = updated_at()

    __table_args__ = (Index(None, "status"), Index(None, "craftId"))


class ClaimTranslation(Base):
    __tablename__ = "ClaimTranslation"

    id: Mapped[uuid.UUID] = uuid_pk()
    claimId: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("Claim.id", ondelete="CASCADE"), nullable=False
    )
    language: Mapped[str] = mapped_column(String(16), nullable=False)
    sourceSha256: Mapped[str] = mapped_column(String(64), nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    createdAt: Mapped[datetime] = created_at()
    updatedAt: Mapped[datetime] = updated_at()

    __table_args__ = (UniqueConstraint("claimId", "language"),)
