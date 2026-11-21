import uuid
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, String, Text, text
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, created_at, one_of, subset_of, updated_at, uuid_pk
from app.models.crafts import EMBEDDING_DIMENSIONS, EMBEDDING_MODEL_CHARS
from app.models.enums import DISCIPLINES

__all__ = [
    "ANSWER_VERDICTS",
    "GAP_LACKS",
    "GAP_PRIORITIES",
    "GAP_STATES",
    "AnswerGap",
    "AnswerVerdict",
]

ANSWER_VERDICTS = ("ANSWERED", "THIN", "UNANSWERED")
GAP_LACKS = ("NO_CITED_EVIDENCE", "MISSING_FIELD", "FEW_SENTENCES", "LOW_RETRIEVAL", "FAILED_QUOTE")
GAP_STATES = ("OPEN", "ANSWERED", "LAPSED")
GAP_PRIORITIES = ("HIGH", "MEDIUM", "LOW")
STATE_CHARS = 16
LANGUAGE_CHARS = 16


def _texts() -> Mapped[list[str]]:
    return mapped_column(ARRAY(Text), nullable=False, server_default=text("ARRAY[]::text[]"))


class AnswerGap(Base):
    __tablename__ = "AnswerGap"

    id: Mapped[uuid.UUID] = uuid_pk()
    craftId: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("Craft.id", ondelete="CASCADE"), nullable=False
    )
    question: Mapped[str] = mapped_column(Text, nullable=False)
    language: Mapped[str] = mapped_column(String(LANGUAGE_CHARS), nullable=False, server_default="en")
    fields: Mapped[list[str]] = _texts()
    lacks: Mapped[list[str]] = _texts()
    askers: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    firstAskedAt: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    lastAskedAt: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    priority: Mapped[str] = mapped_column(String(STATE_CHARS), nullable=False, server_default="LOW")
    state: Mapped[str] = mapped_column(String(STATE_CHARS), nullable=False, server_default="OPEN")
    closedAt: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    embedding: Mapped[list[float] | None] = mapped_column(Vector(EMBEDDING_DIMENSIONS))
    embeddingModel: Mapped[str | None] = mapped_column(String(EMBEDDING_MODEL_CHARS))
    createdAt: Mapped[datetime] = created_at()
    updatedAt: Mapped[datetime] = updated_at()

    __table_args__ = (
        CheckConstraint(one_of("state", GAP_STATES), name="state"),
        CheckConstraint(one_of("priority", GAP_PRIORITIES), name="priority"),
        CheckConstraint(subset_of("fields", DISCIPLINES), name="fields"),
        CheckConstraint(subset_of("lacks", GAP_LACKS), name="lacks"),
        CheckConstraint('"askers" >= 0', name="askers"),
        CheckConstraint('("state" = \'OPEN\') = ("closedAt" IS NULL)', name="closed"),
        Index(None, "craftId", "state"),
    )


class AnswerVerdict(Base):
    __tablename__ = "AnswerVerdict"

    id: Mapped[uuid.UUID] = uuid_pk()
    answerId: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("Answer.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    craftId: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("Craft.id", ondelete="SET NULL")
    )
    verdict: Mapped[str] = mapped_column(String(STATE_CHARS), nullable=False)
    fields: Mapped[list[str]] = _texts()
    lacking: Mapped[list[str]] = _texts()
    lacks: Mapped[list[str]] = _texts()
    sentences: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    gapId: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("AnswerGap.id", ondelete="SET NULL")
    )
    embedding: Mapped[list[float] | None] = mapped_column(Vector(EMBEDDING_DIMENSIONS))
    embeddingModel: Mapped[str | None] = mapped_column(String(EMBEDDING_MODEL_CHARS))
    createdAt: Mapped[datetime] = created_at()

    __table_args__ = (
        CheckConstraint(one_of("verdict", ANSWER_VERDICTS), name="verdict"),
        CheckConstraint(subset_of("fields", DISCIPLINES), name="fields"),
        CheckConstraint(subset_of("lacking", DISCIPLINES), name="lacking"),
        CheckConstraint(subset_of("lacks", GAP_LACKS), name="lacks"),
        CheckConstraint('"sentences" >= 0', name="sentences"),
        CheckConstraint('("verdict" = \'ANSWERED\') = (cardinality("lacks") = 0)', name="judged"),
        Index(None, "craftId", "verdict", "createdAt"),
        Index(None, "gapId"),
    )
