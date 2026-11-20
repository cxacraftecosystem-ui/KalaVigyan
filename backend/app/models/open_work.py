import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String, Text, text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, created_at, one_of, subset_of, updated_at, uuid_pk
from app.models.component_kinds import PIECE_KINDS
from app.models.enums import DISCIPLINES
from app.models.knowledge_pieces import DESCRIPTION_MAX_CHARS, LABEL_COLUMN_CHARS, TITLE_COLUMN_CHARS

TASK_KEY_COLUMN_CHARS = 240
STATUS_COLUMN_CHARS = 16
REVIEW_NOTE_CHARS = 500
RESERVATION_ENDINGS = ("RELEASED", "EXPIRED", "COMPLETED")
PROPOSAL_STATUSES = ("PENDING", "APPROVED", "REJECTED", "WITHDRAWN")
PROPOSAL_EXTENSIONS = ("SUBJECT_LINK", "VARIANT")
LIVE_PROPOSALS = ("PENDING", "APPROVED")
REVIEWED_PROPOSALS = ("APPROVED", "REJECTED")
NEW_COMPONENT = "\"extension\" IS DISTINCT FROM 'SUBJECT_LINK'"
DELIVERED_SPEC = (
    '("spec" IS NULL AND "units" IS NULL) OR '
    "(jsonb_typeof(\"spec\") = 'object' AND jsonb_typeof(\"units\") = 'object')"
)


class TaskReservation(Base):
    __tablename__ = "TaskReservation"

    id: Mapped[uuid.UUID] = uuid_pk()
    taskKey: Mapped[str] = mapped_column(String(TASK_KEY_COLUMN_CHARS), nullable=False)
    userId: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("User.id", ondelete="CASCADE"), nullable=False
    )
    reservedAt: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expiresAt: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    endedAt: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ending: Mapped[str | None] = mapped_column(String(STATUS_COLUMN_CHARS))
    createdAt: Mapped[datetime] = created_at()
    updatedAt: Mapped[datetime] = updated_at()

    __table_args__ = (
        CheckConstraint('"expiresAt" > "reservedAt"', name="expires"),
        CheckConstraint('"ending" IS NULL OR ' + one_of("ending", RESERVATION_ENDINGS), name="ending"),
        CheckConstraint('("endedAt" IS NULL) = ("ending" IS NULL)', name="ended"),
        Index(
            "TaskReservation_taskKey_live_key",
            "taskKey",
            unique=True,
            postgresql_where=text('"endedAt" IS NULL'),
        ),
        Index(None, "userId", "endedAt"),
    )


class ComponentProposal(Base):
    __tablename__ = "ComponentProposal"

    id: Mapped[uuid.UUID] = uuid_pk()
    proposerId: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("User.id", ondelete="SET NULL")
    )
    label: Mapped[str] = mapped_column(String(LABEL_COLUMN_CHARS), nullable=False)
    title: Mapped[str] = mapped_column(String(TITLE_COLUMN_CHARS), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    field: Mapped[str] = mapped_column(String(16), nullable=False)
    fields: Mapped[list[str]] = mapped_column(
        ARRAY(Text), nullable=False, server_default=text("ARRAY[]::text[]")
    )
    craftId: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("Craft.id", ondelete="CASCADE")
    )
    subjects: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False)
    consideredLabels: Mapped[list[str]] = mapped_column(
        ARRAY(Text), nullable=False, server_default=text("ARRAY[]::text[]")
    )
    extendsLabel: Mapped[str | None] = mapped_column(String(LABEL_COLUMN_CHARS))
    extension: Mapped[str | None] = mapped_column(String(STATUS_COLUMN_CHARS))
    taskKey: Mapped[str | None] = mapped_column(String(TASK_KEY_COLUMN_CHARS))
    status: Mapped[str] = mapped_column(String(STATUS_COLUMN_CHARS), nullable=False, server_default="PENDING")
    reviewedById: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("User.id", ondelete="SET NULL")
    )
    reviewedAt: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reviewNote: Mapped[str | None] = mapped_column(String(REVIEW_NOTE_CHARS))
    spec: Mapped[dict[str, Any] | None] = mapped_column(JSONB(none_as_null=True))
    units: Mapped[dict[str, Any] | None] = mapped_column(JSONB(none_as_null=True))
    claimIds: Mapped[list[uuid.UUID]] = mapped_column(
        ARRAY(UUID(as_uuid=True)), nullable=False, server_default=text("ARRAY[]::uuid[]")
    )
    createdAt: Mapped[datetime] = created_at()
    updatedAt: Mapped[datetime] = updated_at()

    __table_args__ = (
        CheckConstraint(one_of("kind", PIECE_KINDS), name="kind"),
        CheckConstraint(DELIVERED_SPEC, name="delivered"),
        CheckConstraint(one_of("field", DISCIPLINES), name="field"),
        CheckConstraint(subset_of("fields", DISCIPLINES), name="fields"),
        CheckConstraint('NOT ("field" = ANY ("fields"))', name="field_once"),
        CheckConstraint(one_of("status", PROPOSAL_STATUSES), name="status"),
        CheckConstraint(f'char_length("description") <= {DESCRIPTION_MAX_CHARS}', name="description"),
        CheckConstraint(
            'jsonb_typeof("subjects") = \'array\' AND jsonb_array_length("subjects") > 0', name="subjects"
        ),
        CheckConstraint(
            '("extendsLabel" IS NULL) = ("extension" IS NULL) AND ("extension" IS NULL OR '
            + one_of("extension", PROPOSAL_EXTENSIONS)
            + ")",
            name="extension",
        ),
        CheckConstraint(
            f'NOT {one_of("status", REVIEWED_PROPOSALS)} OR "reviewedAt" IS NOT NULL', name="reviewed"
        ),
        Index(
            "ComponentProposal_label_live_key",
            "label",
            unique=True,
            postgresql_where=text(f"{one_of('status', LIVE_PROPOSALS)} AND {NEW_COMPONENT}"),
        ),
        Index(None, "status", "createdAt"),
        Index(None, "proposerId"),
        Index(None, "craftId"),
        Index(None, "reviewedById"),
        Index(None, "taskKey"),
    )
