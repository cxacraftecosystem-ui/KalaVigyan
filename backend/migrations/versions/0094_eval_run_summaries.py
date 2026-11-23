from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0094_eval_run_summaries"
down_revision: str | Sequence[str] | None = "0097_chunk_kinds"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

RUNS = "EvalRun"
KINDS = ("ANSWERS", "RETRIEVAL", "RELEASE_CHECK")
KIND_CHECK = "EvalRun_suite_check"
FINISHED_INDEX = "EvalRun_suite_finishedAt_idx"


def upgrade() -> None:
    op.add_column("EvalRun", sa.Column("floorsHeld", sa.Boolean(), nullable=True))
    op.add_column(
        "EvalRun", sa.Column("fresh", sa.Boolean(), server_default=sa.text("false"), nullable=False)
    )
    op.create_check_constraint(op.f(KIND_CHECK), RUNS, f'"suite" IN ({_listed(KINDS)})')
    op.create_index(op.f(FINISHED_INDEX), RUNS, ["suite", "finishedAt"])


def downgrade() -> None:
    op.drop_index(op.f(FINISHED_INDEX), table_name=RUNS)
    op.drop_constraint(op.f(KIND_CHECK), RUNS, type_="check")
    op.drop_column(RUNS, "fresh")
    op.drop_column(RUNS, "floorsHeld")


def _listed(values: Sequence[str]) -> str:
    return ", ".join(f"'{value}'" for value in values)
