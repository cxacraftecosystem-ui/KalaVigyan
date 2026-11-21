import uuid
from datetime import date, datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Date,
    DateTime,
    Index,
    Integer,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, created_at, one_of, updated_at, uuid_pk

__all__ = [
    "DEPOSIT_TARGETS",
    "DOI_CHARS",
    "RELEASE_STATES",
    "VERSION_CHARS",
    "OpenDataRelease",
]

DEPOSIT_TARGETS = ("SANDBOX", "ZENODO")
RELEASE_STATES = ("DRAFT", "PUBLISHED")
VERSION_CHARS = 20
DOI_CHARS = 255
STATE_CHARS = 16
SHA256_CHARS = 64


def _json(default: str) -> Mapped[Any]:
    return mapped_column(JSONB, nullable=False, server_default=text(default))


class OpenDataRelease(Base):
    __tablename__ = "OpenDataRelease"

    id: Mapped[uuid.UUID] = uuid_pk()
    target: Mapped[str] = mapped_column(String(STATE_CHARS), nullable=False)
    version: Mapped[str] = mapped_column(String(VERSION_CHARS), nullable=False)
    releasedOn: Mapped[date] = mapped_column(Date, nullable=False)
    state: Mapped[str] = mapped_column(String(STATE_CHARS), nullable=False, server_default="DRAFT")
    doi: Mapped[str] = mapped_column(String(DOI_CHARS), nullable=False)
    conceptDoi: Mapped[str] = mapped_column(String(DOI_CHARS), nullable=False)
    recordId: Mapped[int] = mapped_column(Integer, nullable=False)
    conceptRecordId: Mapped[int] = mapped_column(Integer, nullable=False)
    recordUrl: Mapped[str | None] = mapped_column(String(DOI_CHARS))
    files: Mapped[list[dict[str, Any]]] = _json("'[]'::jsonb")
    counts: Mapped[dict[str, int]] = _json("'{}'::jsonb")
    changes: Mapped[dict[str, dict[str, int]]] = _json("'{}'::jsonb")
    rowDigests: Mapped[dict[str, dict[str, str]]] = _json("'{}'::jsonb")
    totalBytes: Mapped[int] = mapped_column(BigInteger, nullable=False, server_default=text("0"))
    manifestSha256: Mapped[str] = mapped_column(String(SHA256_CHARS), nullable=False)
    publishedAt: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    createdAt: Mapped[datetime] = created_at()
    updatedAt: Mapped[datetime] = updated_at()

    __table_args__ = (
        CheckConstraint(one_of("target", DEPOSIT_TARGETS), name="target"),
        CheckConstraint(one_of("state", RELEASE_STATES), name="state"),
        CheckConstraint("\"manifestSha256\" ~ '^[0-9a-f]{64}$'", name="manifestSha256"),
        CheckConstraint('"totalBytes" >= 0', name="totalBytes"),
        CheckConstraint('("state" = \'PUBLISHED\') = ("publishedAt" IS NOT NULL)', name="published"),
        UniqueConstraint("target", "version"),
        Index(None, "target", "state", "releasedOn"),
    )
