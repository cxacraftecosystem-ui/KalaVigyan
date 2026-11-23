import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from geoalchemy2 import Geography, Geometry
from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models import enums as e
from app.models.base import Base, created_at, one_of, updated_at, uuid_pk
from app.models.time_zone import INDIA_TZ_NAME

EMBEDDING_DIMENSIONS = 1536
DATASET_ORIGINS = ("SITE", "CONTRIBUTED")
EMBEDDING_MODEL_CHARS = 120
DESCRIPTOR_HASH_CHARS = 64


class CraftCategory(Base):
    __tablename__ = "CraftCategory"

    id: Mapped[uuid.UUID] = uuid_pk()
    slug: Mapped[str] = mapped_column(String(160), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False, unique=True)
    sortOrder: Mapped[int] = mapped_column(Integer, nullable=False)
    createdAt: Mapped[datetime] = created_at()
    updatedAt: Mapped[datetime] = updated_at()
    createdById: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))


class CraftSubCategory(Base):
    __tablename__ = "CraftSubCategory"

    id: Mapped[uuid.UUID] = uuid_pk()
    slug: Mapped[str] = mapped_column(String(160), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    categoryId: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("CraftCategory.id", ondelete="RESTRICT"), nullable=False
    )
    sortOrder: Mapped[int] = mapped_column(Integer, nullable=False)
    createdAt: Mapped[datetime] = created_at()
    updatedAt: Mapped[datetime] = updated_at()
    createdById: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))

    __table_args__ = (UniqueConstraint("categoryId", "name"), Index(None, "categoryId"))


class CraftCode(Base):
    __tablename__ = "CraftCode"

    code: Mapped[str] = mapped_column(String(40), primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    createdAt: Mapped[datetime] = created_at()
    updatedAt: Mapped[datetime] = updated_at()


class Craft(Base):
    __tablename__ = "Craft"

    id: Mapped[uuid.UUID] = uuid_pk()
    name: Mapped[str] = mapped_column(String(300), nullable=False)
    localName: Mapped[str | None] = mapped_column(String(300))
    category: Mapped[str | None] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text)
    place: Mapped[str | None] = mapped_column(Text)
    extraMetadata: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    recordedAt: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    recordedTimezone: Mapped[str] = mapped_column(String(64), nullable=False, server_default=INDIA_TZ_NAME)
    createdAt: Mapped[datetime] = created_at()
    updatedAt: Mapped[datetime] = updated_at()
    createdById: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("User.id", ondelete="SET NULL")
    )
    craftCode: Mapped[str | None] = mapped_column(
        String(40), ForeignKey("CraftCode.code", ondelete="SET NULL")
    )
    slug: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
        unique=True,
        server_default=text("('craft-'::text || md5((random())::text || (clock_timestamp())::text))"),
    )
    subCategoryId: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("CraftSubCategory.id", ondelete="RESTRICT")
    )
    sourceSerial: Mapped[int | None] = mapped_column(Integer, unique=True)
    stateOfOrigin: Mapped[list[str]] = mapped_column(
        ARRAY(Text), nullable=False, server_default=text("ARRAY[]::text[]")
    )
    stateOfPractice: Mapped[list[str]] = mapped_column(
        ARRAY(Text), nullable=False, server_default=text("ARRAY[]::text[]")
    )
    giStatus: Mapped[str | None] = mapped_column(e.GiStatus)
    isCatchAll: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    sourceNotes: Mapped[list[str]] = mapped_column(
        ARRAY(Text), nullable=False, server_default=text("ARRAY[]::text[]")
    )
    status: Mapped[str] = mapped_column(e.CraftStatus, nullable=False, server_default="ACTIVE")
    mergedIntoId: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("Craft.id", ondelete="SET NULL")
    )
    descriptorEmbedding: Mapped[list[float] | None] = mapped_column(Vector(EMBEDDING_DIMENSIONS))
    embeddingModel: Mapped[str | None] = mapped_column(String(EMBEDDING_MODEL_CHARS))
    descriptorHash: Mapped[str | None] = mapped_column(String(DESCRIPTOR_HASH_CHARS))

    __table_args__ = (
        UniqueConstraint("subCategoryId", "name"),
        Index(None, "subCategoryId"),
        Index(None, "status"),
        Index(None, "craftCode"),
        Index(None, "createdById"),
        Index(
            "Craft_descriptorEmbedding_hnsw_idx",
            "descriptorEmbedding",
            postgresql_using="hnsw",
            postgresql_ops={"descriptorEmbedding": "vector_cosine_ops"},
        ),
    )


class CraftSpelling(Base):
    __tablename__ = "CraftSpelling"

    spelling: Mapped[str] = mapped_column(String(300), primary_key=True)
    label: Mapped[str] = mapped_column(String(300), nullable=False)
    craftCode: Mapped[str] = mapped_column(
        String(40), ForeignKey("CraftCode.code", ondelete="CASCADE"), nullable=False
    )
    source: Mapped[str] = mapped_column(String(40), nullable=False, server_default="SHARED")
    createdById: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    createdAt: Mapped[datetime] = created_at()

    __table_args__ = (Index(None, "craftCode"),)


class CraftAlias(Base):
    __tablename__ = "CraftAlias"

    id: Mapped[uuid.UUID] = uuid_pk()
    craftId: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("Craft.id", ondelete="CASCADE"), nullable=False
    )
    alias: Mapped[str] = mapped_column(String(300), nullable=False)
    aliasNorm: Mapped[str] = mapped_column(String(300), nullable=False)
    script: Mapped[str | None] = mapped_column(String(40))
    lang: Mapped[str | None] = mapped_column(String(16))
    source: Mapped[str] = mapped_column(e.AliasSource, nullable=False)
    status: Mapped[str] = mapped_column(e.AliasStatus, nullable=False, server_default="ACTIVE")
    addedById: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("User.id", ondelete="SET NULL")
    )
    createdAt: Mapped[datetime] = created_at()
    updatedAt: Mapped[datetime] = updated_at()

    __table_args__ = (
        UniqueConstraint("craftId", "aliasNorm"),
        Index(None, "craftId"),
        Index(None, "status"),
        Index(
            "CraftAlias_aliasNorm_trgm_idx",
            "aliasNorm",
            postgresql_using="gin",
            postgresql_ops={"aliasNorm": "gin_trgm_ops"},
        ),
    )


class CxaCraftMap(Base):
    __tablename__ = "CxaCraftMap"

    id: Mapped[uuid.UUID] = uuid_pk()
    cxaSlug: Mapped[str] = mapped_column(String(200), nullable=False, unique=True)
    craftSlug: Mapped[str] = mapped_column(String(200), nullable=False)
    acceptedById: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("User.id", ondelete="SET NULL")
    )
    acceptedAt: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    createdAt: Mapped[datetime] = created_at()
    updatedAt: Mapped[datetime] = updated_at()

    __table_args__ = (Index(None, "craftSlug"),)


class AdminState(Base):
    __tablename__ = "AdminState"

    lgd: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    geom: Mapped[Any] = mapped_column(Geometry("MULTIPOLYGON", srid=4326, spatial_index=False), nullable=True)
    createdAt: Mapped[datetime] = created_at()
    updatedAt: Mapped[datetime] = updated_at()

    __table_args__ = (Index("AdminState_geom_gist_idx", "geom", postgresql_using="gist"),)


class AdminDistrict(Base):
    __tablename__ = "AdminDistrict"

    lgd: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)
    stateLgd: Mapped[int] = mapped_column(
        Integer, ForeignKey("AdminState.lgd", ondelete="RESTRICT"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    geom: Mapped[Any] = mapped_column(Geometry("MULTIPOLYGON", srid=4326, spatial_index=False), nullable=True)
    centroid: Mapped[Any] = mapped_column(Geometry("POINT", srid=4326, spatial_index=False), nullable=True)
    boundarySource: Mapped[str] = mapped_column(
        e.BoundarySource, nullable=False, server_default="KAGGLE_INDICATIVE"
    )
    indicative: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    createdAt: Mapped[datetime] = created_at()
    updatedAt: Mapped[datetime] = updated_at()

    __table_args__ = (
        Index(None, "stateLgd"),
        Index("AdminDistrict_geom_gist_idx", "geom", postgresql_using="gist"),
        Index("AdminDistrict_centroid_gist_idx", "centroid", postgresql_using="gist"),
    )


class CraftLocation(Base):
    __tablename__ = "CraftLocation"

    id: Mapped[uuid.UUID] = uuid_pk()
    craftId: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("Craft.id", ondelete="CASCADE"), nullable=False
    )
    precision: Mapped[str] = mapped_column(e.LocationPrecision, nullable=False)
    stateLgd: Mapped[int | None] = mapped_column(Integer, ForeignKey("AdminState.lgd", ondelete="SET NULL"))
    districtLgd: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("AdminDistrict.lgd", ondelete="SET NULL")
    )
    geom: Mapped[Any] = mapped_column(Geography("POINT", srid=4326, spatial_index=False), nullable=True)
    placeLabel: Mapped[str | None] = mapped_column(String(300))
    sourceId: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("Source.id", ondelete="SET NULL")
    )
    evidenceLevel: Mapped[str] = mapped_column(e.EvidenceLevel, nullable=False, server_default="PROVISIONAL")
    role: Mapped[str | None] = mapped_column(String(20))
    createdAt: Mapped[datetime] = created_at()
    updatedAt: Mapped[datetime] = updated_at()

    __table_args__ = (
        CheckConstraint(one_of("role", e.PLACE_ROLES), name="role"),
        Index(None, "craftId"),
        Index(None, "districtLgd"),
        Index(None, "stateLgd"),
        Index("CraftLocation_geom_gist_idx", "geom", postgresql_using="gist"),
    )


class EnvDataset(Base):
    __tablename__ = "EnvDataset"

    id: Mapped[uuid.UUID] = uuid_pk()
    code: Mapped[str] = mapped_column(String(80), nullable=False, unique=True)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    publisher: Mapped[str | None] = mapped_column(String(300))
    edition: Mapped[str | None] = mapped_column(String(120))
    period: Mapped[str | None] = mapped_column(String(120))
    nativeResolution: Mapped[str | None] = mapped_column(String(120))
    crs: Mapped[str | None] = mapped_column(String(120))
    licence: Mapped[str | None] = mapped_column(String(200))
    licenceUrl: Mapped[str | None] = mapped_column(Text)
    attribution: Mapped[str | None] = mapped_column(Text)
    redistributable: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    retrievedAt: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    sha256: Mapped[str | None] = mapped_column(String(64))
    citation: Mapped[str | None] = mapped_column(Text)
    url: Mapped[str | None] = mapped_column(Text)
    version: Mapped[str | None] = mapped_column(String(120))
    doi: Mapped[str | None] = mapped_column(String(200))
    landingUrl: Mapped[str | None] = mapped_column(Text)
    origin: Mapped[str] = mapped_column(String(20), nullable=False, server_default="SITE")
    proposedById: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("User.id", ondelete="SET NULL")
    )
    createdAt: Mapped[datetime] = created_at()
    updatedAt: Mapped[datetime] = updated_at()

    __table_args__ = (
        CheckConstraint(one_of("origin", DATASET_ORIGINS), name="origin"),
        Index(None, "proposedById"),
    )


class DistrictEnvValue(Base):
    __tablename__ = "DistrictEnvValue"

    id: Mapped[uuid.UUID] = uuid_pk()
    districtLgd: Mapped[int] = mapped_column(
        Integer, ForeignKey("AdminDistrict.lgd", ondelete="CASCADE"), nullable=False
    )
    datasetId: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("EnvDataset.id", ondelete="CASCADE"), nullable=False
    )
    variable: Mapped[str] = mapped_column(String(120), nullable=False)
    depthOrPeriod: Mapped[str] = mapped_column(String(80), nullable=False, server_default="")
    stat: Mapped[str] = mapped_column(e.EnvStat, nullable=False)
    value: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    valueText: Mapped[str | None] = mapped_column(Text)
    unit: Mapped[str | None] = mapped_column(String(40))
    method: Mapped[str | None] = mapped_column(Text)
    resolution: Mapped[str | None] = mapped_column(String(120))
    pixelCount: Mapped[int | None] = mapped_column(Integer)
    createdAt: Mapped[datetime] = created_at()
    updatedAt: Mapped[datetime] = updated_at()

    __table_args__ = (
        UniqueConstraint("districtLgd", "datasetId", "variable", "depthOrPeriod", "stat"),
        Index(None, "datasetId"),
        Index(None, "datasetId", "variable", "depthOrPeriod", "stat"),
    )


class DistrictGeology(Base):
    __tablename__ = "DistrictGeology"

    id: Mapped[uuid.UUID] = uuid_pk()
    districtLgd: Mapped[int] = mapped_column(
        Integer, ForeignKey("AdminDistrict.lgd", ondelete="CASCADE"), nullable=False
    )
    datasetId: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("EnvDataset.id", ondelete="CASCADE"), nullable=False
    )
    lithology: Mapped[str] = mapped_column(String(200), nullable=False)
    lithologyName: Mapped[str | None] = mapped_column(String(300))
    areaShare: Mapped[Decimal | None] = mapped_column(Numeric(8, 6))
    mineralOccurrences: Mapped[list[Any] | None] = mapped_column(JSONB)
    method: Mapped[str | None] = mapped_column(Text)
    createdAt: Mapped[datetime] = created_at()
    updatedAt: Mapped[datetime] = updated_at()

    __table_args__ = (
        UniqueConstraint("districtLgd", "datasetId", "lithology"),
        Index(None, "districtLgd"),
        Index(None, "datasetId"),
    )
