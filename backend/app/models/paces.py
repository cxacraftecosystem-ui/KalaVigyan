import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, uuid_pk

__all__ = ["PACE_LANE_CHARS", "PACE_SERVICE_CHARS", "SourceLease", "SourcePace"]

PACE_SERVICE_CHARS = 40
PACE_LANE_CHARS = 20


class SourcePace(Base):
    __tablename__ = "SourcePace"
    __table_args__ = (
        CheckConstraint("\"service\" <> ''", name="service"),
        CheckConstraint("\"lane\" <> ''", name="lane"),
    )

    service: Mapped[str] = mapped_column(String(PACE_SERVICE_CHARS), primary_key=True)
    lane: Mapped[str] = mapped_column(String(PACE_LANE_CHARS), primary_key=True)
    freeAt: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    heldUntil: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class SourceLease(Base):
    __tablename__ = "SourceLease"
    __table_args__ = (
        CheckConstraint("\"service\" <> ''", name="service"),
        Index("SourceLease_service_expiresAt_idx", "service", "expiresAt"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    service: Mapped[str] = mapped_column(String(PACE_SERVICE_CHARS), nullable=False)
    expiresAt: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
