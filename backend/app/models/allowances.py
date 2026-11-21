from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base

__all__ = ["ALLOWANCE_HOLDER_CHARS", "ALLOWANCE_KIND_CHARS", "AllowanceBucket"]

ALLOWANCE_HOLDER_CHARS = 80
ALLOWANCE_KIND_CHARS = 40


class AllowanceBucket(Base):
    __tablename__ = "AllowanceBucket"
    __table_args__ = (
        CheckConstraint('"used" >= 0', name="used"),
        CheckConstraint('"lastTaken" >= 0 AND "lastTaken" <= "used"', name="last_taken"),
        Index("AllowanceBucket_hourStart_idx", "hourStart"),
    )

    holder: Mapped[str] = mapped_column(String(ALLOWANCE_HOLDER_CHARS), primary_key=True)
    kind: Mapped[str] = mapped_column(String(ALLOWANCE_KIND_CHARS), primary_key=True)
    hourStart: Mapped[datetime] = mapped_column(DateTime(timezone=True), primary_key=True)
    used: Mapped[int] = mapped_column(Integer, nullable=False)
    lastTaken: Mapped[int] = mapped_column(Integer, nullable=False)
