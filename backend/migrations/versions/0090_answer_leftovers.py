from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0090_answer_leftovers"
down_revision: str | Sequence[str] | None = "0091_craft_page_archive_dropped"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TERM_TEXT_CHARS = 120
STOPPED_BEFORE = """
UPDATE "Answer" SET "stoppedAt" = "updatedAt"
WHERE "payload" IS NULL
  AND "latencyMs" IS NULL
  AND "stoppedAt" IS NULL
  AND "createdAt" < now() - interval '1 hour'
"""


def upgrade() -> None:
    op.add_column("Answer", sa.Column("stoppedAt", sa.DateTime(timezone=True), nullable=True))
    op.add_column("Term", sa.Column("sentenceName", sa.String(TERM_TEXT_CHARS), nullable=True))
    op.add_column(
        "CraftGiRecord",
        sa.Column(
            "imitationClaimIds",
            postgresql.ARRAY(postgresql.UUID(as_uuid=True)),
            nullable=False,
            server_default=sa.text("ARRAY[]::uuid[]"),
        ),
    )
    op.execute(STOPPED_BEFORE)


def downgrade() -> None:
    op.drop_column("CraftGiRecord", "imitationClaimIds")
    op.drop_column("Term", "sentenceName")
    op.drop_column("Answer", "stoppedAt")
