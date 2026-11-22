import uuid
from datetime import datetime
from typing import Any

from geoalchemy2 import Geometry
from sqlalchemy import CheckConstraint, Float, ForeignKey, Index, Integer, SmallInteger, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, created_at, updated_at

STRAHLER_MAX = 15


class RiverBasin(Base):
    __tablename__ = "RiverBasin"

    mainRiv: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)
    datasetId: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("EnvDataset.id", ondelete="RESTRICT"), nullable=False
    )
    reachCount: Mapped[int] = mapped_column(Integer, nullable=False)
    topologySha256: Mapped[str] = mapped_column(String(64), nullable=False)
    createdAt: Mapped[datetime] = created_at()
    updatedAt: Mapped[datetime] = updated_at()

    __table_args__ = (
        CheckConstraint('"reachCount" > 0', name="reachCount"),
        CheckConstraint("\"topologySha256\" ~ '^[0-9a-f]{64}$'", name="topologySha256"),
        Index(None, "datasetId"),
    )


class RiverReach(Base):
    __tablename__ = "RiverReach"

    hyrivId: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)
    nextDown: Mapped[int] = mapped_column(Integer, nullable=False)
    mainRiv: Mapped[int] = mapped_column(
        Integer, ForeignKey("RiverBasin.mainRiv", ondelete="CASCADE"), nullable=False
    )
    ordStra: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    uplandSkm: Mapped[float] = mapped_column(Float, nullable=False)
    disAvCms: Mapped[float] = mapped_column(Float, nullable=False)
    lengthKm: Mapped[float] = mapped_column(Float, nullable=False)
    geom: Mapped[Any] = mapped_column(Geometry("LINESTRING", srid=4326, spatial_index=False), nullable=False)
    createdAt: Mapped[datetime] = created_at()
    updatedAt: Mapped[datetime] = updated_at()

    __table_args__ = (
        CheckConstraint('"nextDown" >= 0 AND "nextDown" <> "hyrivId"', name="flows_on"),
        CheckConstraint('("nextDown" = 0) = ("hyrivId" = "mainRiv")', name="outlet"),
        CheckConstraint(f'"ordStra" BETWEEN 1 AND {STRAHLER_MAX}', name="ordStra"),
        CheckConstraint('"uplandSkm" >= 0 AND "disAvCms" >= 0 AND "lengthKm" > 0', name="measures"),
        Index(None, "mainRiv"),
        Index(None, "nextDown"),
        Index("RiverReach_geom_gist_idx", "geom", postgresql_using="gist"),
    )


class RiverReachDistrict(Base):
    __tablename__ = "RiverReachDistrict"

    hyrivId: Mapped[int] = mapped_column(
        Integer, ForeignKey("RiverReach.hyrivId", ondelete="CASCADE"), primary_key=True, autoincrement=False
    )
    districtLgd: Mapped[int] = mapped_column(
        Integer, ForeignKey("AdminDistrict.lgd", ondelete="CASCADE"), primary_key=True, autoincrement=False
    )
    entry: Mapped[float] = mapped_column(Float, nullable=False)

    __table_args__ = (
        CheckConstraint('"entry" >= 0 AND "entry" <= 1', name="entry"),
        Index(None, "districtLgd"),
    )
