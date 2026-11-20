import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, created_at, one_of, updated_at, uuid_pk
from app.models.open_work import TASK_KEY_COLUMN_CHARS

__all__ = [
    "STRUCTURE_PROPOSAL_KINDS",
    "STRUCTURE_PROPOSAL_ORIGINS",
    "STRUCTURE_PROPOSAL_STATUSES",
    "STRUCTURE_REVIEW_NOTE_CHARS",
    "StructureProposal",
]

STRUCTURE_PROPOSAL_KINDS = (
    "STAGE_AFTER",
    "STAGE_WHY",
    "NATIVE_NAME",
    "REACTION",
    "BOTANICAL_NAME",
    "GLOSSARY_TERM",
    "CONFLICT",
    "OPEN_QUESTION",
    "GI_RECORD",
)
STRUCTURE_PROPOSAL_STATUSES = ("PENDING", "APPROVED", "REJECTED", "REFUSED")
STRUCTURE_PROPOSAL_ORIGINS = ("CONTRIBUTION", "AGENT")
STRUCTURE_REVIEW_NOTE_CHARS = 500
CODE_CHARS = 16


def _person() -> Mapped[uuid.UUID | None]:
    return mapped_column(UUID(as_uuid=True), ForeignKey("User.id", ondelete="SET NULL"))


class StructureProposal(Base):
    __tablename__ = "StructureProposal"

    id: Mapped[uuid.UUID] = uuid_pk()
    proposerId: Mapped[uuid.UUID | None] = _person()
    craftId: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("Craft.id", ondelete="CASCADE"), nullable=False
    )
    kind: Mapped[str] = mapped_column(String(CODE_CHARS), nullable=False)
    item: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    field: Mapped[str | None] = mapped_column(String(CODE_CHARS))
    statement: Mapped[str | None] = mapped_column(Text)
    sources: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False)
    checks: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False)
    taskKey: Mapped[str | None] = mapped_column(String(TASK_KEY_COLUMN_CHARS))
    note: Mapped[str | None] = mapped_column(String(STRUCTURE_REVIEW_NOTE_CHARS))
    origin: Mapped[str] = mapped_column(String(CODE_CHARS), nullable=False)
    status: Mapped[str] = mapped_column(String(CODE_CHARS), nullable=False, server_default="PENDING")
    reviewedById: Mapped[uuid.UUID | None] = _person()
    reviewedAt: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reviewNote: Mapped[str | None] = mapped_column(String(STRUCTURE_REVIEW_NOTE_CHARS))
    claimId: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("Claim.id", ondelete="SET NULL")
    )
    createdAt: Mapped[datetime] = created_at()
    updatedAt: Mapped[datetime] = updated_at()

    __table_args__ = (
        CheckConstraint(one_of("kind", STRUCTURE_PROPOSAL_KINDS), name="kind"),
        CheckConstraint(one_of("status", STRUCTURE_PROPOSAL_STATUSES), name="status"),
        CheckConstraint(one_of("origin", STRUCTURE_PROPOSAL_ORIGINS), name="origin"),
        CheckConstraint("jsonb_typeof(\"item\") = 'object'", name="item"),
        CheckConstraint("jsonb_typeof(\"sources\") = 'array'", name="sources"),
        CheckConstraint("jsonb_typeof(\"checks\") = 'array'", name="checks"),
        CheckConstraint(
            "\"status\" IN ('PENDING', 'REFUSED') OR \"reviewedAt\" IS NOT NULL", name="reviewed"
        ),
        Index(None, "status", "createdAt"),
        Index(None, "proposerId"),
        Index(None, "craftId"),
        Index(None, "reviewedById"),
        Index(None, "claimId"),
    )
