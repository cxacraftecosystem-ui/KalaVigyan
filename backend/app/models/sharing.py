from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, created_at

__all__ = [
    "OBJECT_KEY_CHARS",
    "SHARED_TOGETHER",
    "SHARE_TOKEN_CHARS",
    "SharedByLink",
    "SharedExportFile",
    "shared_together",
]

SHARE_TOKEN_CHARS = 64
OBJECT_KEY_CHARS = 1024
SHARED_TOGETHER = '("shareToken" IS NULL) = ("sharedAt" IS NULL)'


class SharedByLink:
    shareToken: Mapped[str | None] = mapped_column(String(SHARE_TOKEN_CHARS), unique=True)
    sharedAt: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


def shared_together() -> CheckConstraint:
    return CheckConstraint(SHARED_TOGETHER, name="shared")


class SharedExportFile(Base):
    __tablename__ = "SharedExportFile"

    key: Mapped[str] = mapped_column(String(OBJECT_KEY_CHARS), primary_key=True)
    shareToken: Mapped[str] = mapped_column(String(SHARE_TOKEN_CHARS), nullable=False)
    createdAt: Mapped[datetime] = created_at()

    __table_args__ = (Index(None, "shareToken"),)
