import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models import enums as e
from app.models.base import Base, created_at, updated_at, uuid_pk

SAVED_ANSWER_INDEX = "SavedItem_userId_answerId_key"
SAVED_ANSWER_CHECK = (
    '("answerId" IS NULL) = ("seenVersion" IS NULL) AND ("seenVersion" IS NULL OR "seenVersion" >= 1)'
)


class User(Base):
    __tablename__ = "User"

    id: Mapped[uuid.UUID] = uuid_pk()
    email: Mapped[str] = mapped_column(String(320), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    passwordHash: Mapped[str | None] = mapped_column(String(60))
    avatarUrl: Mapped[str | None] = mapped_column(Text)
    role: Mapped[str] = mapped_column(e.UserRole, nullable=False, server_default="STUDENT")
    authProvider: Mapped[str] = mapped_column(e.AuthProvider, nullable=False, server_default="LOCAL")
    canManageQuestionnaire: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )
    canManageCrafts: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    canManageWorkshops: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    canReview: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    canViewProvenance: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    canDownloadDataset: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    passwordSetAt: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    mustChangePassword: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    passwordIssuerKnown: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    firstLoginAt: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    lastLoginAt: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    sessionsValidFrom: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    tokenVersion: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    twoFactorEnabled: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    twoFactorSecret: Mapped[str | None] = mapped_column(Text)
    twoFactorPendingSecret: Mapped[str | None] = mapped_column(Text)
    twoFactorPendingSince: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    twoFactorRecoveryCodes: Mapped[list[str]] = mapped_column(
        ARRAY(Text), nullable=False, server_default=text("ARRAY[]::text[]")
    )
    twoFactorLastStep: Mapped[int | None] = mapped_column(Integer)
    twoFactorEnabledAt: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    twoFactorFailedAttempts: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    twoFactorFailureWindowStartedAt: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    twoFactorLockedUntil: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    twoFactorLockouts: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    twoFactorRecoveryFailedAttempts: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )
    twoFactorRecoveryWindowStartedAt: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    twoFactorRecoveryLockedUntil: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    twoFactorRecoveryLockouts: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    emailVerifiedAt: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    affiliation: Mapped[str | None] = mapped_column(String(300))
    ageAttestedAt: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    deletedAt: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    createdAt: Mapped[datetime] = created_at()
    updatedAt: Mapped[datetime] = updated_at()

    __table_args__ = (Index(None, "role"), Index(None, "createdAt"))


class AccessRoster(Base):
    __tablename__ = "AccessRoster"

    id: Mapped[uuid.UUID] = uuid_pk()
    email: Mapped[str] = mapped_column(String(320), nullable=False, unique=True)
    status: Mapped[str] = mapped_column(e.AccessStatus, nullable=False, server_default="PENDING")
    admitRole: Mapped[str | None] = mapped_column(e.UserRole)
    joinedAt: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    requestedAt: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    attemptCount: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    lastAttemptAt: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    decidedAt: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    decidedById: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("User.id", ondelete="SET NULL")
    )
    firstSeenAt: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    fullName: Mapped[str | None] = mapped_column(String(180))
    notes: Mapped[str | None] = mapped_column(Text)
    affiliation: Mapped[str | None] = mapped_column(String(300))
    createdAt: Mapped[datetime] = created_at()
    updatedAt: Mapped[datetime] = updated_at()
    addedById: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("User.id", ondelete="SET NULL")
    )

    __table_args__ = (
        Index(None, "status"),
        Index(None, "status", "requestedAt"),
        Index(None, "addedById"),
        Index(None, "decidedById"),
        Index(None, "createdAt"),
    )


class PasswordResetToken(Base):
    __tablename__ = "PasswordResetToken"

    id: Mapped[uuid.UUID] = uuid_pk()
    userId: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("User.id", ondelete="CASCADE"), nullable=False
    )
    tokenHash: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    purpose: Mapped[str] = mapped_column(e.CredentialLinkPurpose, nullable=False, server_default="RESET")
    expiresAt: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    usedAt: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revokedAt: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    createdAt: Mapped[datetime] = created_at()
    issuedById: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("User.id", ondelete="SET NULL")
    )

    __table_args__ = (Index(None, "userId", "createdAt"), Index(None, "issuedById"))


class PasswordResetRequest(Base):
    __tablename__ = "PasswordResetRequest"

    id: Mapped[uuid.UUID] = uuid_pk()
    createdAt: Mapped[datetime] = created_at()
    email: Mapped[str] = mapped_column(String(320), nullable=False)
    accountId: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    outcome: Mapped[str] = mapped_column(String(40), nullable=False)
    ipHash: Mapped[str | None] = mapped_column(String(64))
    userAgent: Mapped[str | None] = mapped_column(String(400))

    __table_args__ = (Index(None, "email", "createdAt"), Index(None, "accountId"), Index(None, "createdAt"))


class TwoFactorChallenge(Base):
    __tablename__ = "TwoFactorChallenge"

    id: Mapped[uuid.UUID] = uuid_pk()
    userId: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("User.id", ondelete="CASCADE"), nullable=False
    )
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    usedAt: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    expiresAt: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    createdAt: Mapped[datetime] = created_at()

    __table_args__ = (Index(None, "userId"), Index(None, "expiresAt"))


class AuthNonce(Base):
    __tablename__ = "AuthNonce"

    id: Mapped[uuid.UUID] = uuid_pk()
    purpose: Mapped[str] = mapped_column(e.AuthNoncePurpose, nullable=False)
    nonceHash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    userId: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("User.id", ondelete="CASCADE")
    )
    ipHash: Mapped[str | None] = mapped_column(String(64))
    expiresAt: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    usedAt: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    createdAt: Mapped[datetime] = created_at()

    __table_args__ = (Index(None, "expiresAt"),)


class Invite(Base):
    __tablename__ = "Invite"

    id: Mapped[uuid.UUID] = uuid_pk()
    email: Mapped[str] = mapped_column(String(320), nullable=False)
    role: Mapped[str] = mapped_column(e.UserRole, nullable=False)
    invitedById: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("User.id", ondelete="SET NULL")
    )
    tokenHash: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    expiresAt: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    acceptedAt: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revokedAt: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    createdAt: Mapped[datetime] = created_at()
    updatedAt: Mapped[datetime] = updated_at()

    __table_args__ = (Index(None, "email"), Index(None, "invitedById"))


class RoleRequest(Base):
    __tablename__ = "RoleRequest"

    id: Mapped[uuid.UUID] = uuid_pk()
    userId: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("User.id", ondelete="CASCADE"), nullable=False
    )
    requestedRole: Mapped[str] = mapped_column(e.UserRole, nullable=False)
    affiliation: Mapped[str | None] = mapped_column(String(300))
    profileUrl: Mapped[str | None] = mapped_column(Text)
    note: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(e.RoleRequestStatus, nullable=False, server_default="PENDING")
    decidedById: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("User.id", ondelete="SET NULL")
    )
    decidedAt: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    createdAt: Mapped[datetime] = created_at()
    updatedAt: Mapped[datetime] = updated_at()

    __table_args__ = (Index(None, "userId"), Index(None, "status"))


class ConsentRecord(Base):
    __tablename__ = "ConsentRecord"

    id: Mapped[uuid.UUID] = uuid_pk()
    userId: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("User.id", ondelete="CASCADE"), nullable=False
    )
    kind: Mapped[str] = mapped_column(e.ConsentKind, nullable=False)
    noticeVersion: Mapped[str] = mapped_column(String(40), nullable=False)
    acceptedAt: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    recordedById: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("User.id", ondelete="SET NULL")
    )
    withdrawnAt: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    createdAt: Mapped[datetime] = created_at()
    updatedAt: Mapped[datetime] = updated_at()

    __table_args__ = (Index(None, "userId", "kind"), Index(None, "recordedById"))


class DataRequest(Base):
    __tablename__ = "DataRequest"

    id: Mapped[uuid.UUID] = uuid_pk()
    userId: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("User.id", ondelete="SET NULL")
    )
    kind: Mapped[str] = mapped_column(e.DataRequestKind, nullable=False)
    status: Mapped[str] = mapped_column(e.DataRequestStatus, nullable=False, server_default="PENDING")
    exportKey: Mapped[str | None] = mapped_column(Text)
    error: Mapped[str | None] = mapped_column(Text)
    completedAt: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    createdAt: Mapped[datetime] = created_at()
    updatedAt: Mapped[datetime] = updated_at()

    __table_args__ = (Index(None, "userId"), Index(None, "status"))


class AuditLog(Base):
    __tablename__ = "AuditLog"

    id: Mapped[uuid.UUID] = uuid_pk()
    actorId: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("User.id", ondelete="SET NULL")
    )
    actorKind: Mapped[str] = mapped_column(e.ActorKind, nullable=False, server_default="USER")
    action: Mapped[str] = mapped_column(String(120), nullable=False)
    targetType: Mapped[str | None] = mapped_column(String(80))
    targetId: Mapped[str | None] = mapped_column(String(120))
    detail: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    ipHash: Mapped[str | None] = mapped_column(String(64))
    requestId: Mapped[str | None] = mapped_column(String(64))
    createdAt: Mapped[datetime] = created_at()

    __table_args__ = (
        Index(None, "actorId"),
        Index(None, "action", "createdAt"),
        Index(None, "targetType", "targetId"),
        Index(None, "createdAt"),
    )


class SavedItem(Base):
    __tablename__ = "SavedItem"

    id: Mapped[uuid.UUID] = uuid_pk()
    userId: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("User.id", ondelete="CASCADE"), nullable=False
    )
    answerId: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("Answer.id", ondelete="CASCADE")
    )
    craftId: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("Craft.id", ondelete="CASCADE")
    )
    mediaAssetId: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("MediaAsset.id", ondelete="CASCADE")
    )
    note: Mapped[str | None] = mapped_column(Text)
    seenVersion: Mapped[int | None] = mapped_column(Integer)
    checkedAt: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    createdAt: Mapped[datetime] = created_at()
    updatedAt: Mapped[datetime] = updated_at()

    __table_args__ = (
        Index(None, "userId", "createdAt"),
        Index(
            SAVED_ANSWER_INDEX,
            "userId",
            "answerId",
            unique=True,
            postgresql_where=text('"answerId" IS NOT NULL'),
        ),
        CheckConstraint(SAVED_ANSWER_CHECK, name="seenVersion"),
    )


class UserPreference(Base):
    __tablename__ = "UserPreference"

    id: Mapped[uuid.UUID] = uuid_pk()
    userId: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("User.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    theme: Mapped[str] = mapped_column(String(16), nullable=False, server_default="system")
    reducedMotion: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    largerText: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    highContrast: Mapped[str] = mapped_column(String(16), nullable=False, server_default="system")
    answerLanguage: Mapped[str] = mapped_column(String(16), nullable=False, server_default="auto")
    alertDigest: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    createdAt: Mapped[datetime] = created_at()
    updatedAt: Mapped[datetime] = updated_at()
