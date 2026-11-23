from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0078_media_page_key"
down_revision: str | Sequence[str] | None = "0079_shared_export_files"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("MediaAsset", sa.Column("pageKey", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("MediaAsset", "pageKey")
