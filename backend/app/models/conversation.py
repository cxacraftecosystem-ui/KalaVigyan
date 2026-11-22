import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

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
    text as sql_text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models import enums as e
from app.models.base import Base, created_at, one_of, updated_at, uuid_pk
from app.models.knowledge import QUOTE_MAX_CHARS
from app.models.sharing import SharedByLink, shared_together

REQUEST_ID_MAX_CHARS = 64
EXPLAINER_VERSION_CHECK = (
    '("explainerId" IS NULL AND "explainerVersion" IS NULL) OR '
    '("explainerVersion" >= 1 AND ("explainerVersion" = 1) = ("explainerId" = "id"))'
)


class Conversation(Base):
    __tablename__ = "Conversation"

    id: Mapped[uuid.UUID] = uuid_pk()
    userId: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("User.id", ondelete="CASCADE"), nullable=False
    )
    craftId: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("Craft.id", ondelete="SET NULL")
    )
    mode: Mapped[str] = mapped_column(e.AnswerMode, nullable=False, server_default="HYBRID")
    channel: Mapped[str] = mapped_column(e.Channel, nullable=False, server_default="TEXT")
    title: Mapped[str | None] = mapped_column(String(300))
    language: Mapped[str] = mapped_column(String(16), nullable=False, server_default="en")
    createdAt: Mapped[datetime] = created_at()
    updatedAt: Mapped[datetime] = updated_at()

    __table_args__ = (Index(None, "userId", "updatedAt"),)


class Answer(SharedByLink, Base):
    __tablename__ = "Answer"

    id: Mapped[uuid.UUID] = uuid_pk()
    conversationId: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("Conversation.id", ondelete="CASCADE")
    )
    userId: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("User.id", ondelete="SET NULL")
    )
    question: Mapped[str] = mapped_column(Text, nullable=False)
    language: Mapped[str] = mapped_column(String(16), nullable=False, server_default="en")
    mode: Mapped[str] = mapped_column(e.AnswerMode, nullable=False)
    craftId: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("Craft.id", ondelete="SET NULL")
    )
    plan: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    understanding: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    payload: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    claimIds: Mapped[list[uuid.UUID]] = mapped_column(
        ARRAY(UUID(as_uuid=True)), nullable=False, server_default=sql_text("ARRAY[]::uuid[]")
    )
    tiersUsed: Mapped[list[str]] = mapped_column(
        ARRAY(Text), nullable=False, server_default=sql_text("ARRAY[]::text[]")
    )
    costUsd: Mapped[Decimal] = mapped_column(Numeric(10, 6), nullable=False, server_default=sql_text("0"))
    latencyMs: Mapped[int | None] = mapped_column(Integer)
    requestId: Mapped[str | None] = mapped_column(String(REQUEST_ID_MAX_CHARS))
    route: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    staleSince: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    explainerId: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("Answer.id", ondelete="CASCADE")
    )
    explainerVersion: Mapped[int | None] = mapped_column(Integer)
    createdAt: Mapped[datetime] = created_at()
    updatedAt: Mapped[datetime] = updated_at()

    __table_args__ = (
        Index(None, "conversationId"),
        Index(None, "userId", "createdAt"),
        Index(None, "craftId"),
        Index(None, "requestId"),
        UniqueConstraint("explainerId", "explainerVersion"),
        CheckConstraint(EXPLAINER_VERSION_CHECK, name="explainerVersion"),
        shared_together(),
    )


class Message(Base):
    __tablename__ = "Message"

    id: Mapped[uuid.UUID] = uuid_pk()
    conversationId: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("Conversation.id", ondelete="CASCADE"), nullable=False
    )
    role: Mapped[str] = mapped_column(e.MessageRole, nullable=False)
    content: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    answerId: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("Answer.id", ondelete="SET NULL")
    )
    createdAt: Mapped[datetime] = created_at()
    updatedAt: Mapped[datetime] = updated_at()

    __table_args__ = (Index(None, "conversationId", "createdAt"),)


class AnswerSentence(Base):
    __tablename__ = "AnswerSentence"

    id: Mapped[uuid.UUID] = uuid_pk()
    answerId: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("Answer.id", ondelete="CASCADE"), nullable=False
    )
    sectionOrdinal: Mapped[int] = mapped_column(Integer, nullable=False)
    sectionHeading: Mapped[str | None] = mapped_column(String(300))
    ordinal: Mapped[int] = mapped_column(Integer, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    evidenceLevel: Mapped[str] = mapped_column(e.EvidenceLevel, nullable=False)
    translated: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=sql_text("false"))
    openQuestion: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=sql_text("false"))
    createdAt: Mapped[datetime] = created_at()

    __table_args__ = (UniqueConstraint("answerId", "sectionOrdinal", "ordinal"),)


class AnswerCitation(Base):
    __tablename__ = "AnswerCitation"

    id: Mapped[uuid.UUID] = uuid_pk()
    sentenceId: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("AnswerSentence.id", ondelete="CASCADE"), nullable=False
    )
    claimId: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("Claim.id", ondelete="SET NULL")
    )
    claimSourceId: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ClaimSource.id", ondelete="SET NULL")
    )
    sourceId: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("Source.id", ondelete="SET NULL")
    )
    quote: Mapped[str | None] = mapped_column(String(QUOTE_MAX_CHARS))
    locator: Mapped[str | None] = mapped_column(String(300))
    url: Mapped[str | None] = mapped_column(Text)
    sourceLabel: Mapped[str | None] = mapped_column(String(300))
    ordinal: Mapped[int] = mapped_column(Integer, nullable=False, server_default=sql_text("0"))
    createdAt: Mapped[datetime] = created_at()

    __table_args__ = (Index(None, "sentenceId"), Index(None, "claimId"))


class AnswerTrace(Base):
    __tablename__ = "AnswerTrace"

    id: Mapped[uuid.UUID] = uuid_pk()
    answerId: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("Answer.id", ondelete="CASCADE"), nullable=False
    )
    step: Mapped[str] = mapped_column(String(60), nullable=False)
    ordinal: Mapped[int] = mapped_column(Integer, nullable=False, server_default=sql_text("0"))
    ms: Mapped[int | None] = mapped_column(Integer)
    detail: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    createdAt: Mapped[datetime] = created_at()

    __table_args__ = (Index(None, "answerId", "ordinal"),)


class VoiceSession(Base):
    __tablename__ = "VoiceSession"

    id: Mapped[uuid.UUID] = uuid_pk()
    userId: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("User.id", ondelete="CASCADE"), nullable=False
    )
    elConversationId: Mapped[str | None] = mapped_column(String(120), unique=True)
    agentId: Mapped[str | None] = mapped_column(String(120))
    nonceHash: Mapped[str | None] = mapped_column(String(64))
    language: Mapped[str] = mapped_column(String(16), nullable=False, server_default="en")
    craftId: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("Craft.id", ondelete="SET NULL")
    )
    conversationId: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("Conversation.id", ondelete="SET NULL")
    )
    mode: Mapped[str] = mapped_column(e.AnswerMode, nullable=False, server_default="HYBRID")
    transport: Mapped[str] = mapped_column(String(16), nullable=False, server_default="RELAY")
    startedAt: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    expiresAt: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    maxDurationSeconds: Mapped[int] = mapped_column(Integer, nullable=False, server_default=sql_text("600"))
    endedAt: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    turnCount: Mapped[int] = mapped_column(Integer, nullable=False, server_default=sql_text("0"))
    reservedSeconds: Mapped[int] = mapped_column(Integer, nullable=False, server_default=sql_text("0"))
    billedSeconds: Mapped[int | None] = mapped_column(Integer)
    transcriptEnc: Mapped[str | None] = mapped_column(Text)
    retentionUntil: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    purpose: Mapped[str] = mapped_column(String(16), nullable=False, server_default="ASK")
    createdAt: Mapped[datetime] = created_at()
    updatedAt: Mapped[datetime] = updated_at()

    __table_args__ = (
        CheckConstraint(one_of("purpose", e.VOICE_PURPOSES), name="purpose"),
        Index(None, "userId", "endedAt"),
        Index(None, "retentionUntil"),
        Index(
            "VoiceSession_one_live_per_user_key",
            "userId",
            unique=True,
            postgresql_where=sql_text('"endedAt" IS NULL'),
        ),
        CheckConstraint("transport IN ('AGENT', 'RELAY')", name="transport"),
    )


class MediaJob(Base):
    __tablename__ = "MediaJob"

    id: Mapped[uuid.UUID] = uuid_pk()
    kind: Mapped[str] = mapped_column(e.MediaKind, nullable=False)
    requestedById: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("User.id", ondelete="SET NULL")
    )
    craftId: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("Craft.id", ondelete="SET NULL")
    )
    stageId: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ProcessStage.id", ondelete="SET NULL")
    )
    claimIds: Mapped[list[uuid.UUID]] = mapped_column(
        ARRAY(UUID(as_uuid=True)), nullable=False, server_default=sql_text("ARRAY[]::uuid[]")
    )
    prompt: Mapped[str | None] = mapped_column(Text)
    promptVersion: Mapped[str | None] = mapped_column(String(40))
    promptHash: Mapped[str | None] = mapped_column(String(64))
    model: Mapped[str | None] = mapped_column(String(120))
    params: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default=sql_text("'{}'::jsonb")
    )
    status: Mapped[str] = mapped_column(e.JobStatus, nullable=False, server_default="QUEUED")
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, server_default=sql_text("0"))
    costUsd: Mapped[Decimal] = mapped_column(Numeric(10, 6), nullable=False, server_default=sql_text("0"))
    billedTokens: Mapped[int | None] = mapped_column(Integer)
    idempotencyKey: Mapped[str] = mapped_column(String(160), nullable=False, unique=True)
    bundle: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    providerRef: Mapped[str | None] = mapped_column(String(300))
    error: Mapped[str | None] = mapped_column(Text)
    assetId: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("MediaAsset.id", ondelete="SET NULL", use_alter=True)
    )
    createdAt: Mapped[datetime] = created_at()
    updatedAt: Mapped[datetime] = updated_at()

    __table_args__ = (
        Index(None, "status", "kind"),
        Index(None, "requestedById", "createdAt"),
        Index(None, "promptHash"),
        Index(None, "assetId"),
    )


class MediaAsset(Base):
    __tablename__ = "MediaAsset"

    id: Mapped[uuid.UUID] = uuid_pk()
    jobId: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("MediaJob.id", ondelete="SET NULL")
    )
    s3Key: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    pageKey: Mapped[str | None] = mapped_column(Text)
    mime: Mapped[str] = mapped_column(String(120), nullable=False)
    bytes: Mapped[int | None] = mapped_column(Integer)
    width: Mapped[int | None] = mapped_column(Integer)
    height: Mapped[int | None] = mapped_column(Integer)
    durationS: Mapped[Decimal | None] = mapped_column(Numeric(8, 3))
    label: Mapped[str | None] = mapped_column(Text)
    model: Mapped[str | None] = mapped_column(String(120))
    altText: Mapped[str | None] = mapped_column(Text)
    visibility: Mapped[str] = mapped_column(e.MediaVisibility, nullable=False, server_default="PRIVATE")
    approvedById: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("User.id", ondelete="SET NULL")
    )
    secondApprovedById: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("User.id", ondelete="SET NULL")
    )
    depictsNamedCluster: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=sql_text("false")
    )
    createdAt: Mapped[datetime] = created_at()
    updatedAt: Mapped[datetime] = updated_at()

    __table_args__ = (Index(None, "jobId"), Index(None, "visibility"))
