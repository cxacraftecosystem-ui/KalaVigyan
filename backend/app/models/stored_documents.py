from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base
from .monograph_documents import (
    DEFAULT_DOCUMENT_LANGUAGE,
    DIGEST_CHARS,
    LANGUAGE_CHARS,
    SLUG_CHARS,
    SUBJECT_KIND_CHARS,
)

__all__ = ["StoredDocument"]


class StoredDocument(Base):
    __tablename__ = "StoredDocument"

    subjectKind: Mapped[str] = mapped_column(String(SUBJECT_KIND_CHARS), primary_key=True)
    subjectSlug: Mapped[str] = mapped_column(String(SLUG_CHARS), primary_key=True)
    language: Mapped[str] = mapped_column(
        String(LANGUAGE_CHARS), primary_key=True, server_default=DEFAULT_DOCUMENT_LANGUAGE
    )
    stamp: Mapped[str] = mapped_column(String(DIGEST_CHARS), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    contentHash: Mapped[str] = mapped_column(String(DIGEST_CHARS), nullable=False)
    document: Mapped[str] = mapped_column(Text, nullable=False)
    builtAt: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    wantedAt: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (CheckConstraint('"version" >= 1', name="version"),)
