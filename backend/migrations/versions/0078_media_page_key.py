from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0078_media_page_key"
down_revision: str | Sequence[str] | None = "0074_mcp_activity"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

ASSETS = "MediaAsset"
PAGE_KEY = "pageKey"


def upgrade() -> None:
    op.add_column(ASSETS, sa.Column(PAGE_KEY, sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column(ASSETS, PAGE_KEY)
