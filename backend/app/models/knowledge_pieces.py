import uuid
from collections.abc import Mapping
from datetime import datetime
from types import MappingProxyType
from typing import Any

from pgvector.sqlalchemy import Vector
from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, String, Text, text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, created_at, one_of, subset_of, updated_at, uuid_pk
from app.models.component_kinds import PIECE_KINDS
from app.models.crafts import EMBEDDING_DIMENSIONS, EMBEDDING_MODEL_CHARS
from app.models.enums import (
    DISCIPLINES,
    EXPLAINER_DEPTHS,
    PIECE_SUBJECT_KINDS,
    PLACE_KEY_PREFIXES,
    READING_STYLES,
)

TOPIC_KEY_COLUMN_CHARS = 200
LABEL_COLUMN_CHARS = 200
TITLE_COLUMN_CHARS = 200
DESCRIPTION_MAX_CHARS = 600
PLACE_KEY_COLUMN_CHARS = 64
LABEL_PATTERN = "^[a-z0-9]+(-[a-z0-9]+)*(/[a-z0-9]+(-[a-z0-9]+)*){2,}$"
PLACE_KEY_PATTERN = "^(" + "|".join(PLACE_KEY_PREFIXES) + "):[A-Za-z0-9_-]+$"
SUBJECT_COLUMNS: Mapping[str, str] = MappingProxyType(
    {"CRAFT": "craftId", "CONCEPT": "conceptId", "PLACE": "placeKey", "COMPOUND": "compoundId"}
)


class KnowledgePiece(Base):
    __tablename__ = "KnowledgePiece"

    id: Mapped[uuid.UUID] = uuid_pk()
    craftId: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("Craft.id", ondelete="CASCADE")
    )
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    facet: Mapped[str] = mapped_column(String(16), nullable=False)
    topicKey: Mapped[str] = mapped_column(String(TOPIC_KEY_COLUMN_CHARS), nullable=False)
    language: Mapped[str] = mapped_column(String(16), nullable=False)
    depth: Mapped[str] = mapped_column(String(16), nullable=False)
    readingStyle: Mapped[str | None] = mapped_column(String(16))
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    claimIds: Mapped[list[uuid.UUID]] = mapped_column(ARRAY(UUID(as_uuid=True)), nullable=False)
    sourceIds: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False)
    contentHash: Mapped[str] = mapped_column(String(64), nullable=False)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(EMBEDDING_DIMENSIONS))
    embeddingModel: Mapped[str | None] = mapped_column(String(EMBEDDING_MODEL_CHARS))
    createdFromAnswerId: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("Answer.id", ondelete="SET NULL")
    )
    staleSince: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    rebuildTriedAt: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    supersededById: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("KnowledgePiece.id", ondelete="SET NULL")
    )
    hiddenAt: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    hiddenById: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("User.id", ondelete="SET NULL")
    )
    label: Mapped[str | None] = mapped_column(String(LABEL_COLUMN_CHARS))
    title: Mapped[str | None] = mapped_column(String(TITLE_COLUMN_CHARS))
    description: Mapped[str | None] = mapped_column(Text)
    fields: Mapped[list[str]] = mapped_column(
        ARRAY(Text), nullable=False, server_default=text("ARRAY[]::text[]")
    )
    districtLgds: Mapped[list[int]] = mapped_column(
        ARRAY(Integer), nullable=False, server_default=text("ARRAY[]::integer[]")
    )
    createdAt: Mapped[datetime] = created_at()
    updatedAt: Mapped[datetime] = updated_at()

    __table_args__ = (
        CheckConstraint(one_of("kind", PIECE_KINDS), name="kind"),
        CheckConstraint(one_of("facet", DISCIPLINES), name="facet"),
        CheckConstraint(one_of("depth", EXPLAINER_DEPTHS), name="depth"),
        CheckConstraint(
            '"readingStyle" IS NULL OR ' + one_of("readingStyle", READING_STYLES), name="readingStyle"
        ),
        CheckConstraint('cardinality("claimIds") > 0 AND cardinality("sourceIds") > 0', name="rests_on"),
        CheckConstraint('"hiddenById" IS NULL OR "hiddenAt" IS NOT NULL', name="hidden_by"),
        Index(None, "craftId", "facet", "topicKey"),
        Index("KnowledgePiece_claimIds_gin_idx", "claimIds", postgresql_using="gin"),
        Index("KnowledgePiece_districtLgds_gin_idx", "districtLgds", postgresql_using="gin"),
        Index(None, "createdFromAnswerId"),
        Index(None, "supersededById"),
        Index(None, "hiddenById"),
        Index(None, "contentHash"),
        Index(None, "staleSince", postgresql_where=text('"staleSince" IS NOT NULL')),
        CheckConstraint(subset_of("fields", DISCIPLINES), name="fields"),
        CheckConstraint('NOT ("facet" = ANY ("fields"))', name="facet_once"),
        CheckConstraint(
            f'"label" IS NULL OR ("label" ~ \'{LABEL_PATTERN}\' AND "title" IS NOT NULL AND "description" IS NOT NULL)',
            name="label",
        ),
        CheckConstraint(
            f'"description" IS NULL OR char_length("description") <= {DESCRIPTION_MAX_CHARS}',
            name="description",
        ),
        Index("KnowledgePiece_label_key", "label", unique=True, postgresql_where=text('"label" IS NOT NULL')),
        Index("KnowledgePiece_fields_gin_idx", "fields", postgresql_using="gin"),
    )


def _one_subject() -> str:
    return " AND ".join(
        f'("kind" = \'{kind}\') = ("{column}" IS NOT NULL)' for kind, column in SUBJECT_COLUMNS.items()
    )


def _subject_key(column: str) -> Index:
    return Index(
        f"KnowledgePieceSubject_pieceId_{column}_key",
        "pieceId",
        column,
        unique=True,
        postgresql_where=text(f'"{column}" IS NOT NULL'),
    )


class KnowledgePieceSubject(Base):
    __tablename__ = "KnowledgePieceSubject"

    id: Mapped[uuid.UUID] = uuid_pk()
    pieceId: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("KnowledgePiece.id", ondelete="CASCADE"), nullable=False
    )
    kind: Mapped[str] = mapped_column(String(16), nullable=False)
    craftId: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("Craft.id", ondelete="CASCADE")
    )
    conceptId: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("Concept.id", ondelete="CASCADE")
    )
    compoundId: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("Compound.id", ondelete="CASCADE")
    )
    placeKey: Mapped[str | None] = mapped_column(String(PLACE_KEY_COLUMN_CHARS))
    createdAt: Mapped[datetime] = created_at()

    __table_args__ = (
        CheckConstraint(one_of("kind", PIECE_SUBJECT_KINDS), name="kind"),
        CheckConstraint(_one_subject(), name="one_subject"),
        CheckConstraint(f'"placeKey" IS NULL OR "placeKey" ~ \'{PLACE_KEY_PATTERN}\'', name="placeKey"),
        *(_subject_key(column) for column in SUBJECT_COLUMNS.values()),
        Index(None, "craftId"),
        Index(None, "conceptId"),
        Index(None, "compoundId"),
        Index(None, "placeKey"),
    )
