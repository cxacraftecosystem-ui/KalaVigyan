import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base

CRAFT_PAGE_VARIANTS = ("OPEN", "RESEARCHER")


class CraftPageSnapshot(Base):
    __tablename__ = "CraftPageSnapshot"

    craftId: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("Craft.id", ondelete="CASCADE"), primary_key=True
    )
    variant: Mapped[str] = mapped_column(Text, primary_key=True)
    stamp: Mapped[str] = mapped_column(Text, nullable=False)
    schemaVersion: Mapped[int] = mapped_column(Integer, nullable=False)
    body: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    etag: Mapped[str] = mapped_column(Text, nullable=False)
    builtAt: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class WikidataPoint(Base):
    __tablename__ = "WikidataPoint"

    wikidataId: Mapped[str] = mapped_column(String(20), primary_key=True)
    latitude: Mapped[float] = mapped_column(Float, nullable=False)
    longitude: Mapped[float] = mapped_column(Float, nullable=False)
    keptAt: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
