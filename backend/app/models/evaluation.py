import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    text as sql_text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models import enums as e
from app.models.base import Base, created_at, one_of, updated_at, uuid_pk

EVAL_RUN_KINDS = ("ANSWERS", "RETRIEVAL", "RELEASE_CHECK")


class EvalCase(Base):
    __tablename__ = "EvalCase"

    id: Mapped[uuid.UUID] = uuid_pk()
    suite: Mapped[str] = mapped_column(String(60), nullable=False)
    externalId: Mapped[str] = mapped_column(String(120), nullable=False)
    craftSlug: Mapped[str | None] = mapped_column(String(200))
    input: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    expected: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    authorId: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("User.id", ondelete="SET NULL")
    )
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=sql_text("true"))
    createdAt: Mapped[datetime] = created_at()
    updatedAt: Mapped[datetime] = updated_at()

    __table_args__ = (UniqueConstraint("suite", "externalId"),)


class EvalRun(Base):
    __tablename__ = "EvalRun"

    id: Mapped[uuid.UUID] = uuid_pk()
    suite: Mapped[str] = mapped_column(String(60), nullable=False)
    gitSha: Mapped[str | None] = mapped_column(String(40))
    status: Mapped[str] = mapped_column(e.EvalRunStatus, nullable=False, server_default="QUEUED")
    budgetUsd: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))
    costUsd: Mapped[Decimal] = mapped_column(Numeric(10, 6), nullable=False, server_default=sql_text("0"))
    summary: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    reportKey: Mapped[str | None] = mapped_column(Text)
    startedAt: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finishedAt: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    floorsHeld: Mapped[bool | None] = mapped_column(Boolean)
    fresh: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=sql_text("false"))
    createdAt: Mapped[datetime] = created_at()
    updatedAt: Mapped[datetime] = updated_at()

    __table_args__ = (
        CheckConstraint(one_of("suite", EVAL_RUN_KINDS), name="suite"),
        Index(None, "suite", "finishedAt"),
    )


class EvalResult(Base):
    __tablename__ = "EvalResult"

    id: Mapped[uuid.UUID] = uuid_pk()
    runId: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("EvalRun.id", ondelete="CASCADE"), nullable=False
    )
    caseId: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("EvalCase.id", ondelete="CASCADE"), nullable=False
    )
    passed: Mapped[bool | None] = mapped_column(Boolean)
    score: Mapped[float | None] = mapped_column(Float)
    metrics: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default=sql_text("'{}'::jsonb")
    )
    output: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    createdAt: Mapped[datetime] = created_at()

    __table_args__ = (UniqueConstraint("runId", "caseId"),)
