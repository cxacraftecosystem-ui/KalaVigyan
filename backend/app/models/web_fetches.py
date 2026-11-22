import uuid
from datetime import datetime

from sqlalchemy import DateTime, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, created_at, updated_at, uuid_pk


class WebFetch(Base):
    __tablename__ = "WebFetch"

    id: Mapped[uuid.UUID] = uuid_pk()
    url: Mapped[str] = mapped_column(Text, nullable=False)
    finalUrl: Mapped[str | None] = mapped_column(Text)
    status: Mapped[int | None] = mapped_column(Integer)
    contentType: Mapped[str | None] = mapped_column(String(120))
    bytes: Mapped[int | None] = mapped_column(Integer)
    sha256: Mapped[str | None] = mapped_column(String(64), unique=True)
    snapshotKey: Mapped[str | None] = mapped_column(Text)
    fetchedAt: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    blockedReason: Mapped[str | None] = mapped_column(String(200))
    createdAt: Mapped[datetime] = created_at()
    updatedAt: Mapped[datetime] = updated_at()

    __table_args__ = (Index(None, "url"),)
