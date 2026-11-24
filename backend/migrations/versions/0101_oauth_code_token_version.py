from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0101_oauth_code_token_version"
down_revision: str | Sequence[str] | None = "0100_signed_in_chunks_public"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "OAuthCode",
        sa.Column("userTokenVersion", sa.Integer(), nullable=False, server_default=sa.text("0")),
    )


def downgrade() -> None:
    op.drop_column("OAuthCode", "userTokenVersion")
