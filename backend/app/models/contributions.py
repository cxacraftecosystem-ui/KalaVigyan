import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, Numeric, String, Text, text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, created_at, one_of, updated_at, uuid_pk
from app.models.open_work import TASK_KEY_COLUMN_CHARS

__all__ = [
    "IDEMPOTENCY_KEY_CHARS",
    "QUEUE_FAILURE_CHARS",
    "QUEUE_KINDS",
    "QUEUE_ORIGINS",
    "QUEUE_OUTCOMES",
    "QUEUE_STATES",
    "TIER_NOTE_CHARS",
    "TRUST_TIERS",
    "CraftSteward",
    "QueuedProposal",
    "TrustTierOverride",
]

QUEUE_STATES = ("QUEUED", "CHECKING", "DONE", "FAILED")
QUEUE_KINDS = ("FACT",)
QUEUE_ORIGINS = ("CONTRIBUTION", "AGENT")
QUEUE_OUTCOMES = ("PUBLISHED", "WAITING", "REFUSED")
TRUST_TIERS = ("NEW", "ESTABLISHED", "PROVEN")
IDEMPOTENCY_KEY_CHARS = 120
FINGERPRINT_CHARS = 64
QUEUE_FAILURE_CHARS = 500
TIER_NOTE_CHARS = 500
CODE_CHARS = 16


def _stamp() -> Mapped[datetime | None]:
    return mapped_column(DateTime(timezone=True))


class QueuedProposal(Base):
    __tablename__ = "QueuedProposal"

    id: Mapped[uuid.UUID] = uuid_pk()
    proposerId: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("User.id", ondelete="CASCADE"), nullable=False
    )
    kind: Mapped[str] = mapped_column(String(CODE_CHARS), nullable=False, server_default="FACT")
    origin: Mapped[str] = mapped_column(String(CODE_CHARS), nullable=False)
    idempotencyKey: Mapped[str] = mapped_column(String(IDEMPOTENCY_KEY_CHARS), nullable=False)
    fingerprint: Mapped[str] = mapped_column(String(FINGERPRINT_CHARS), nullable=False)
    subjectKey: Mapped[str] = mapped_column(String(TASK_KEY_COLUMN_CHARS), nullable=False)
    taskKey: Mapped[str | None] = mapped_column(String(TASK_KEY_COLUMN_CHARS))
    proposal: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    state: Mapped[str] = mapped_column(String(CODE_CHARS), nullable=False, server_default="QUEUED")
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    availableAt: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    leaseUntil: Mapped[datetime | None] = _stamp()
    startedAt: Mapped[datetime | None] = _stamp()
    finishedAt: Mapped[datetime | None] = _stamp()
    outcome: Mapped[str | None] = mapped_column(String(CODE_CHARS))
    claimId: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("Claim.id", ondelete="SET NULL")
    )
    reply: Mapped[dict[str, Any] | None] = mapped_column(JSONB(none_as_null=True))
    failure: Mapped[str | None] = mapped_column(String(QUEUE_FAILURE_CHARS))
    modelCalls: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    costUsd: Mapped[Decimal] = mapped_column(Numeric(10, 6), nullable=False, server_default=text("0"))
    createdAt: Mapped[datetime] = created_at()
    updatedAt: Mapped[datetime] = updated_at()

    __table_args__ = (
        CheckConstraint(one_of("kind", QUEUE_KINDS), name="kind"),
        CheckConstraint(one_of("origin", QUEUE_ORIGINS), name="origin"),
        CheckConstraint(one_of("state", QUEUE_STATES), name="state"),
        CheckConstraint('"outcome" IS NULL OR ' + one_of("outcome", QUEUE_OUTCOMES), name="outcome"),
        CheckConstraint('("state" = \'DONE\') = ("outcome" IS NOT NULL)', name="done"),
        CheckConstraint("jsonb_typeof(\"proposal\") = 'object'", name="proposal"),
        CheckConstraint('"attempts" >= 0 AND "modelCalls" >= 0', name="counts"),
        Index("QueuedProposal_proposerId_idempotencyKey_key", "proposerId", "idempotencyKey", unique=True),
        Index(None, "state", "availableAt"),
        Index(None, "proposerId", "createdAt"),
        Index(None, "subjectKey", "state"),
        Index(None, "claimId"),
    )


class CraftSteward(Base):
    __tablename__ = "CraftSteward"

    id: Mapped[uuid.UUID] = uuid_pk()
    userId: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("User.id", ondelete="CASCADE"), nullable=False
    )
    craftId: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("Craft.id", ondelete="CASCADE"), nullable=False
    )
    adoptedAt: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    droppedAt: Mapped[datetime | None] = _stamp()
    seenTaskKeys: Mapped[list[str]] = mapped_column(
        ARRAY(Text), nullable=False, server_default=text("ARRAY[]::text[]")
    )
    seenAt: Mapped[datetime | None] = _stamp()
    createdAt: Mapped[datetime] = created_at()
    updatedAt: Mapped[datetime] = updated_at()

    __table_args__ = (
        CheckConstraint('"droppedAt" IS NULL OR "droppedAt" >= "adoptedAt"', name="dropped"),
        Index(
            "CraftSteward_userId_craftId_live_key",
            "userId",
            "craftId",
            unique=True,
            postgresql_where=text('"droppedAt" IS NULL'),
        ),
        Index(None, "craftId", "droppedAt"),
        Index(None, "userId", "droppedAt"),
    )


class TrustTierOverride(Base):
    __tablename__ = "TrustTierOverride"

    userId: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("User.id", ondelete="CASCADE"), primary_key=True
    )
    tier: Mapped[str] = mapped_column(String(CODE_CHARS), nullable=False)
    note: Mapped[str | None] = mapped_column(String(TIER_NOTE_CHARS))
    setById: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("User.id", ondelete="SET NULL")
    )
    setAt: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    createdAt: Mapped[datetime] = created_at()
    updatedAt: Mapped[datetime] = updated_at()

    __table_args__ = (
        CheckConstraint(one_of("tier", TRUST_TIERS), name="tier"),
        Index(None, "setById"),
    )
