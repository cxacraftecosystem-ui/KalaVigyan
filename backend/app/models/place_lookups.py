from datetime import datetime
from typing import Any

from sqlalchemy import CheckConstraint, DateTime, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base

LOOKUP_KEY_COLUMN_CHARS = 320
LOOKUP_KEY_PATTERN = "^(name|item):.+$"


class PlaceLookup(Base):
    __tablename__ = "PlaceLookup"

    lookupKey: Mapped[str] = mapped_column(String(LOOKUP_KEY_COLUMN_CHARS), primary_key=True)
    answer: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    askedAt: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (CheckConstraint(f"\"lookupKey\" ~ '{LOOKUP_KEY_PATTERN}'", name="lookupKey"),)
