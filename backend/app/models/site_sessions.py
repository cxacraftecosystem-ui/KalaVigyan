import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, created_at, uuid_pk

__all__ = ["SiteSession"]


class SiteSession(Base):
    __tablename__ = "SiteSession"

    id: Mapped[uuid.UUID] = uuid_pk()
    userId: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("User.id", ondelete="CASCADE"), nullable=False
    )
    createdAt: Mapped[datetime] = created_at()
    renewedAt: Mapped[datetime] = created_at()
    endedAt: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (Index(None, "userId"),)
