from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0095_candidate_check_differs_on"
down_revision: str | Sequence[str] | None = "0094_eval_run_summaries"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

DIFFERS_ON_CHARS = 300


def upgrade() -> None:
    op.add_column("CandidateCheck", sa.Column("differsOn", sa.String(length=DIFFERS_ON_CHARS), nullable=True))


def downgrade() -> None:
    op.drop_column("CandidateCheck", "differsOn")
