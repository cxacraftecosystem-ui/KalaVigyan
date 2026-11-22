import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, created_at, uuid_pk


class StateEnvValue(Base):
    __tablename__ = "StateEnvValue"

    id: Mapped[uuid.UUID] = uuid_pk()
    stateLgd: Mapped[int] = mapped_column(
        Integer, ForeignKey("AdminState.lgd", ondelete="CASCADE"), nullable=False
    )
    datasetId: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("EnvDataset.id", ondelete="CASCADE"), nullable=False
    )
    variable: Mapped[str] = mapped_column(String(120), nullable=False)
    depthOrPeriod: Mapped[str] = mapped_column(String(80), nullable=False)
    stat: Mapped[str] = mapped_column(String(40), nullable=False)
    unit: Mapped[str | None] = mapped_column(String(40))
    valueText: Mapped[str | None] = mapped_column(Text)
    districts: Mapped[int] = mapped_column(Integer, nullable=False)
    weightedSum: Mapped[float] = mapped_column(Float, nullable=False)
    area: Mapped[float] = mapped_column(Float, nullable=False)
    total: Mapped[float] = mapped_column(Float, nullable=False)
    low: Mapped[float] = mapped_column(Float, nullable=False)
    high: Mapped[float] = mapped_column(Float, nullable=False)
    resolutions: Mapped[list[str | None]] = mapped_column(ARRAY(Text), nullable=False)
    methods: Mapped[list[str | None]] = mapped_column(ARRAY(Text), nullable=False)
    datasetDistricts: Mapped[int] = mapped_column(Integer, nullable=False)
    datasetArea: Mapped[float] = mapped_column(Float, nullable=False)
    createdAt: Mapped[datetime] = created_at()

    __table_args__ = (
        CheckConstraint('"districts" >= 1 AND "datasetDistricts" >= "districts"', name="districts"),
        Index(None, "stateLgd"),
        Index(None, "datasetId"),
    )
