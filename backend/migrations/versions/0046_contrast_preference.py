from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0046_contrast_preference"
down_revision: str | Sequence[str] | None = "0045_document_language"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLE = "UserPreference"
COLUMN = "highContrast"
SYSTEM = "system"
CHOICE_FROM_FLAG = f"""CASE WHEN "{COLUMN}" THEN 'high' ELSE '{SYSTEM}' END"""
FLAG_FROM_CHOICE = f""""{COLUMN}" = 'high'"""


def upgrade() -> None:
    op.alter_column(TABLE, COLUMN, server_default=None, existing_type=sa.Boolean(), existing_nullable=False)
    op.alter_column(
        TABLE,
        COLUMN,
        type_=sa.String(length=16),
        existing_type=sa.Boolean(),
        existing_nullable=False,
        postgresql_using=CHOICE_FROM_FLAG,
    )
    op.alter_column(
        TABLE, COLUMN, server_default=SYSTEM, existing_type=sa.String(length=16), existing_nullable=False
    )


def downgrade() -> None:
    op.alter_column(
        TABLE, COLUMN, server_default=None, existing_type=sa.String(length=16), existing_nullable=False
    )
    op.alter_column(
        TABLE,
        COLUMN,
        type_=sa.Boolean(),
        existing_type=sa.String(length=16),
        existing_nullable=False,
        postgresql_using=FLAG_FROM_CHOICE,
    )
    op.alter_column(
        TABLE, COLUMN, server_default=sa.text("false"), existing_type=sa.Boolean(), existing_nullable=False
    )
