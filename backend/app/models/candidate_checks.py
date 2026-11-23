import uuid
from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, String, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, created_at, one_of, uuid_pk
from app.models.knowledge import DIFFERS_ON_CHARS

CANDIDATE_GATES = ("QUOTES", "SOURCE", "DUPLICATE", "NOVELTY")
GATE_COLUMN_CHARS = 16
MODEL_COLUMN_CHARS = 120


class CandidateCheck(Base):
    __tablename__ = "CandidateCheck"

    id: Mapped[uuid.UUID] = uuid_pk()
    claimId: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("Claim.id", ondelete="CASCADE"), nullable=False
    )
    gate: Mapped[str] = mapped_column(String(GATE_COLUMN_CHARS), nullable=False)
    passed: Mapped[bool] = mapped_column(Boolean, nullable=False)
    reasons: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    relatedClaimIds: Mapped[list[uuid.UUID]] = mapped_column(
        ARRAY(UUID(as_uuid=True)), nullable=False, server_default=text("ARRAY[]::uuid[]")
    )
    model: Mapped[str | None] = mapped_column(String(MODEL_COLUMN_CHARS))
    differsOn: Mapped[str | None] = mapped_column(String(DIFFERS_ON_CHARS))
    checkedAt: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    createdAt: Mapped[datetime] = created_at()

    __table_args__ = (
        CheckConstraint(one_of("gate", CANDIDATE_GATES), name="gate"),
        CheckConstraint(
            'jsonb_typeof("reasons") = \'array\' AND jsonb_array_length("reasons") > 0', name="reasons"
        ),
        UniqueConstraint("claimId", "gate"),
    )
