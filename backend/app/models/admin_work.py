from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, created_at, one_of, uuid_pk
from app.models.oauth import CLIENT_NAME_CHARS

__all__ = [
    "BATCH_STATUSES",
    "ITEM_STATES",
    "REFRESH_ORIGINS",
    "REFRESH_PHASES",
    "REFRESH_SCOPES",
    "REFRESH_STATUSES",
    "RUNNING_JOB_INDEX",
    "STAGED_ACTION_VALUES",
    "STAGED_KIND_VALUES",
    "PageRefreshJob",
    "StagedReview",
    "StagedReviewItem",
]

STAGED_KIND_VALUES = (
    "FACTS",
    "COMPONENTS",
    "LAYOUTS",
    "STRUCTURE",
    "READINGS",
    "LAYERS",
    "STAGES",
    "SOURCES",
    "SOURCES_DIFFER",
)
STAGED_ACTION_VALUES = ("approve", "reject", "raise", "retract", "correct", "clear")
BATCH_STATUSES = ("OPEN", "CONFIRMED", "DISCARDED")
ITEM_STATES = ("STAGED", "APPLIED", "REFUSED", "SKIPPED")
REFRESH_SCOPES = ("CHANGED", "EVERY", "NAMED")
REFRESH_ORIGINS = ("WEB", "MCP", "NIGHT", "REVIEW")
REFRESH_STATUSES = ("RUNNING", "DONE", "FAILED")
REFRESH_PHASES = ("PAGES", "DOCUMENTS", "REFRESHING", "FINISHED")
RUNNING_JOB_INDEX = "PageRefreshJob_one_running_idx"
CODE_CHARS = 16
LABEL_CHARS = 300
OUTCOME_CHARS = 500


def _person(ondelete: str = "SET NULL") -> Mapped[uuid.UUID | None]:
    return mapped_column(UUID(as_uuid=True), ForeignKey("User.id", ondelete=ondelete))


def _code(default: str | None = None) -> Mapped[str]:
    if default is None:
        return mapped_column(String(CODE_CHARS), nullable=False)
    return mapped_column(String(CODE_CHARS), nullable=False, server_default=default)


class StagedReview(Base):
    __tablename__ = "StagedReview"

    id: Mapped[uuid.UUID] = uuid_pk()
    proposerId: Mapped[uuid.UUID | None] = _person()
    grantId: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("OAuthGrant.id", ondelete="SET NULL")
    )
    tokenId: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("OAuthToken.id", ondelete="SET NULL")
    )
    clientName: Mapped[str] = mapped_column(String(CLIENT_NAME_CHARS), nullable=False)
    status: Mapped[str] = _code("OPEN")
    decidedById: Mapped[uuid.UUID | None] = _person()
    decidedAt: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    createdAt: Mapped[datetime] = created_at()
    expiresAt: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        CheckConstraint(one_of("status", BATCH_STATUSES), name="status"),
        CheckConstraint('"status" = \'OPEN\' OR "decidedAt" IS NOT NULL', name="decided"),
        CheckConstraint('"expiresAt" > "createdAt"', name="expires"),
        Index(None, "status", "createdAt"),
        Index(None, "proposerId", "createdAt"),
        Index(None, "decidedById"),
        Index(None, "grantId"),
        Index(None, "tokenId"),
    )


class StagedReviewItem(Base):
    __tablename__ = "StagedReviewItem"

    id: Mapped[uuid.UUID] = uuid_pk()
    batchId: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("StagedReview.id", ondelete="CASCADE"), nullable=False
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    kind: Mapped[str] = _code()
    itemId: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    action: Mapped[str] = _code()
    decision: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    label: Mapped[str] = mapped_column(String(LABEL_CHARS), nullable=False)
    state: Mapped[str] = _code("STAGED")
    applied: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    outcome: Mapped[str | None] = mapped_column(String(OUTCOME_CHARS))

    __table_args__ = (
        CheckConstraint(one_of("kind", STAGED_KIND_VALUES), name="kind"),
        CheckConstraint(one_of("action", STAGED_ACTION_VALUES), name="action"),
        CheckConstraint(one_of("state", ITEM_STATES), name="state"),
        CheckConstraint('"position" >= 0', name="position"),
        CheckConstraint("jsonb_typeof(\"decision\") = 'object'", name="decision"),
        UniqueConstraint("batchId", "position"),
        Index(None, "kind", "itemId"),
    )


class PageRefreshJob(Base):
    __tablename__ = "PageRefreshJob"

    id: Mapped[uuid.UUID] = uuid_pk()
    scope: Mapped[str] = _code()
    origin: Mapped[str] = _code()
    startedById: Mapped[uuid.UUID | None] = _person()
    clientName: Mapped[str | None] = mapped_column(String(CLIENT_NAME_CHARS))
    owners: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    status: Mapped[str] = _code("RUNNING")
    phase: Mapped[str] = _code("PAGES")
    progress: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    note: Mapped[str | None] = mapped_column(Text)
    startedAt: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    finishedAt: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        CheckConstraint(one_of("scope", REFRESH_SCOPES), name="scope"),
        CheckConstraint(one_of("origin", REFRESH_ORIGINS), name="origin"),
        CheckConstraint(one_of("status", REFRESH_STATUSES), name="status"),
        CheckConstraint(one_of("phase", REFRESH_PHASES), name="phase"),
        CheckConstraint('"status" = \'RUNNING\' OR "finishedAt" IS NOT NULL', name="finished"),
        Index(RUNNING_JOB_INDEX, "status", unique=True, postgresql_where=text("\"status\" = 'RUNNING'")),
        Index(None, "startedAt"),
        Index(None, "startedById"),
    )
