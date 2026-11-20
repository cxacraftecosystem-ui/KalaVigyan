import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, created_at, one_of, uuid_pk
from app.models.monograph_documents import SLUG_CHARS, SUBJECT_KIND_CHARS

__all__ = ["PREVIEW_SUBJECT_KINDS", "PagePreview"]

PREVIEW_SUBJECT_KINDS = ("craft", "family", "category")


class PagePreview(Base):
    __tablename__ = "PagePreview"

    id: Mapped[uuid.UUID] = uuid_pk()
    userId: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("User.id", ondelete="CASCADE"), nullable=False
    )
    subjectKind: Mapped[str] = mapped_column(String(SUBJECT_KIND_CHARS), nullable=False)
    subjectSlug: Mapped[str] = mapped_column(String(SLUG_CHARS), nullable=False)
    document: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    expiresAt: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    createdAt: Mapped[datetime] = created_at()

    __table_args__ = (
        CheckConstraint(one_of("subjectKind", PREVIEW_SUBJECT_KINDS), name="subjectKind"),
        CheckConstraint('"expiresAt" > "createdAt"', name="expires"),
        CheckConstraint("jsonb_typeof(\"document\") = 'object'", name="document"),
        Index(None, "userId", "expiresAt"),
    )
