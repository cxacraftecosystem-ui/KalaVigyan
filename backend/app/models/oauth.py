import uuid
from datetime import date, datetime

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, created_at, one_of, subset_of, uuid_pk

__all__ = [
    "CLIENT_NAME_CHARS",
    "MCP_REASON_CHARS",
    "MCP_SCOPE_VALUES",
    "MCP_TOOL_OUTCOMES",
    "OAUTH_TOKEN_KINDS",
    "McpTermsAcceptance",
    "McpToolCall",
    "McpToolCallDay",
    "OAuthClient",
    "OAuthCode",
    "OAuthGrant",
    "OAuthToken",
]

OAUTH_TOKEN_KINDS = ("ACCESS", "REFRESH")
MCP_SCOPE_VALUES = ("read", "ask", "contribute", "review")
MCP_TOOL_OUTCOMES = ("OK", "TOOL_ERROR", "PROTOCOL_ERROR")
DIGEST_CHARS = 64
CHALLENGE_CHARS = 43
CLIENT_NAME_CHARS = 120
SOFTWARE_CHARS = 120
TERMS_VERSION_CHARS = 40
TOOL_NAME_CHARS = 64
OUTCOME_CHARS = 16
MCP_REASON_CHARS = 300
REASON_ONLY_ON_FAILURE = '"outcome" <> \'OK\' OR "reason" IS NULL'
SCOPES_WITHIN = subset_of("scopes", MCP_SCOPE_VALUES)
REDIRECT_URIS_COUNT = 'cardinality("redirectUris") BETWEEN 1 AND 10'


def _stamp() -> Mapped[datetime]:
    return mapped_column(DateTime(timezone=True), nullable=False)


def _optional_stamp() -> Mapped[datetime | None]:
    return mapped_column(DateTime(timezone=True))


def _owner(table: str, ondelete: str = "CASCADE") -> Mapped[uuid.UUID]:
    return mapped_column(UUID(as_uuid=True), ForeignKey(f"{table}.id", ondelete=ondelete), nullable=False)


def _scopes() -> Mapped[list[str]]:
    return mapped_column(ARRAY(Text), nullable=False)


class OAuthClient(Base):
    __tablename__ = "OAuthClient"

    id: Mapped[uuid.UUID] = uuid_pk()
    name: Mapped[str] = mapped_column(String(CLIENT_NAME_CHARS), nullable=False)
    redirectUris: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False)
    clientUri: Mapped[str | None] = mapped_column(Text)
    softwareId: Mapped[str | None] = mapped_column(String(SOFTWARE_CHARS))
    softwareVersion: Mapped[str | None] = mapped_column(String(SOFTWARE_CHARS))
    createdAt: Mapped[datetime] = created_at()

    __table_args__ = (CheckConstraint(REDIRECT_URIS_COUNT, name="redirect_uris"), Index(None, "createdAt"))


class OAuthGrant(Base):
    __tablename__ = "OAuthGrant"

    id: Mapped[uuid.UUID] = uuid_pk()
    clientId: Mapped[uuid.UUID] = _owner("OAuthClient")
    userId: Mapped[uuid.UUID] = _owner("User")
    scopes: Mapped[list[str]] = _scopes()
    resource: Mapped[str] = mapped_column(Text, nullable=False)
    userTokenVersion: Mapped[int] = mapped_column(Integer, nullable=False)
    createdAt: Mapped[datetime] = created_at()
    lastUsedAt: Mapped[datetime | None] = _optional_stamp()
    expiresAt: Mapped[datetime] = _stamp()
    revokedAt: Mapped[datetime | None] = _optional_stamp()

    __table_args__ = (
        CheckConstraint(SCOPES_WITHIN, name="scopes"),
        Index(None, "userId", "revokedAt"),
        Index(None, "clientId"),
    )


class OAuthCode(Base):
    __tablename__ = "OAuthCode"

    id: Mapped[uuid.UUID] = uuid_pk()
    codeHash: Mapped[str] = mapped_column(String(DIGEST_CHARS), nullable=False, unique=True)
    clientId: Mapped[uuid.UUID] = _owner("OAuthClient")
    userId: Mapped[uuid.UUID] = _owner("User")
    redirectUri: Mapped[str] = mapped_column(Text, nullable=False)
    codeChallenge: Mapped[str] = mapped_column(String(CHALLENGE_CHARS), nullable=False)
    scopes: Mapped[list[str]] = _scopes()
    resource: Mapped[str] = mapped_column(Text, nullable=False)
    expiresAt: Mapped[datetime] = _stamp()
    usedAt: Mapped[datetime | None] = _optional_stamp()
    grantId: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("OAuthGrant.id", ondelete="SET NULL")
    )
    createdAt: Mapped[datetime] = created_at()

    __table_args__ = (
        CheckConstraint(SCOPES_WITHIN, name="scopes"),
        Index(None, "clientId"),
        Index(None, "userId"),
        Index(None, "grantId"),
        Index(None, "expiresAt"),
    )


class OAuthToken(Base):
    __tablename__ = "OAuthToken"

    id: Mapped[uuid.UUID] = uuid_pk()
    grantId: Mapped[uuid.UUID] = _owner("OAuthGrant")
    kind: Mapped[str] = mapped_column(String(8), nullable=False)
    tokenHash: Mapped[str] = mapped_column(String(DIGEST_CHARS), nullable=False, unique=True)
    scopes: Mapped[list[str]] = _scopes()
    expiresAt: Mapped[datetime] = _stamp()
    usedAt: Mapped[datetime | None] = _optional_stamp()
    revokedAt: Mapped[datetime | None] = _optional_stamp()
    createdAt: Mapped[datetime] = created_at()

    __table_args__ = (
        CheckConstraint(one_of("kind", OAUTH_TOKEN_KINDS), name="kind"),
        CheckConstraint(SCOPES_WITHIN, name="scopes"),
        Index(None, "grantId"),
        Index(None, "expiresAt"),
    )


class McpTermsAcceptance(Base):
    __tablename__ = "McpTermsAcceptance"

    id: Mapped[uuid.UUID] = uuid_pk()
    userId: Mapped[uuid.UUID] = _owner("User")
    termsVersion: Mapped[str] = mapped_column(String(TERMS_VERSION_CHARS), nullable=False)
    acceptedAt: Mapped[datetime] = _stamp()

    __table_args__ = (UniqueConstraint("userId", "termsVersion"),)


class McpToolCall(Base):
    __tablename__ = "McpToolCall"

    id: Mapped[uuid.UUID] = uuid_pk()
    grantId: Mapped[uuid.UUID] = _owner("OAuthGrant")
    tokenId: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("OAuthToken.id", ondelete="SET NULL")
    )
    clientName: Mapped[str] = mapped_column(String(CLIENT_NAME_CHARS), nullable=False)
    tool: Mapped[str] = mapped_column(String(TOOL_NAME_CHARS), nullable=False)
    outcome: Mapped[str] = mapped_column(String(OUTCOME_CHARS), nullable=False)
    reason: Mapped[str | None] = mapped_column(String(MCP_REASON_CHARS))
    calledAt: Mapped[datetime] = _stamp()

    __table_args__ = (
        CheckConstraint(one_of("outcome", MCP_TOOL_OUTCOMES), name="outcome"),
        CheckConstraint(REASON_ONLY_ON_FAILURE, name="reason"),
        Index(None, "grantId", "calledAt"),
        Index(None, "tokenId"),
        Index(None, "calledAt"),
    )


class McpToolCallDay(Base):
    __tablename__ = "McpToolCallDay"

    day: Mapped[date] = mapped_column(Date, primary_key=True)
    clientName: Mapped[str] = mapped_column(String(CLIENT_NAME_CHARS), primary_key=True)
    tool: Mapped[str] = mapped_column(String(TOOL_NAME_CHARS), primary_key=True)
    outcome: Mapped[str] = mapped_column(String(OUTCOME_CHARS), primary_key=True)
    calls: Mapped[int] = mapped_column(Integer, nullable=False)

    __table_args__ = (
        CheckConstraint(one_of("outcome", MCP_TOOL_OUTCOMES), name="outcome"),
        CheckConstraint('"calls" >= 1', name="calls"),
    )
