import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, ForeignKey, Index, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, created_at, one_of, uuid_pk

__all__ = [
    "GROUP_NAME_CHARS",
    "GROUP_NAME_KINDS",
    "GROUP_NAME_LOCATOR_CHARS",
    "GROUP_NAME_ORIGINS",
    "CraftGroupName",
]

GROUP_NAME_KINDS = ("COMMUNITY", "PERSON")
GROUP_NAME_ORIGINS = ("DOSSIER", "PROPOSAL")
GROUP_NAME_CHARS = 300
GROUP_NAME_LOCATOR_CHARS = 300
CODE_CHARS = 16


class CraftGroupName(Base):
    __tablename__ = "CraftGroupName"

    id: Mapped[uuid.UUID] = uuid_pk()
    craftId: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("Craft.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(GROUP_NAME_CHARS), nullable=False)
    nameKey: Mapped[str] = mapped_column(String(GROUP_NAME_CHARS), nullable=False)
    kind: Mapped[str] = mapped_column(String(CODE_CHARS), nullable=False)
    origin: Mapped[str] = mapped_column(String(CODE_CHARS), nullable=False)
    sourceTitle: Mapped[str] = mapped_column(Text, nullable=False)
    sourceUrl: Mapped[str] = mapped_column(Text, nullable=False)
    quote: Mapped[str] = mapped_column(Text, nullable=False)
    locator: Mapped[str | None] = mapped_column(String(GROUP_NAME_LOCATOR_CHARS))
    proposalId: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("StructureProposal.id", ondelete="SET NULL")
    )
    createdAt: Mapped[datetime] = created_at()

    __table_args__ = (
        CheckConstraint(one_of("kind", GROUP_NAME_KINDS), name="kind"),
        CheckConstraint(one_of("origin", GROUP_NAME_ORIGINS), name="origin"),
        UniqueConstraint("craftId", "nameKey"),
        Index(None, "proposalId"),
    )
