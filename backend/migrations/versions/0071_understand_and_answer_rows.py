from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0071_understand_and_answer_rows"
down_revision: str | Sequence[str] | None = "0067_seed_rows_retired"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UNDERSTAND = "UNDERSTAND"
PLAN = "PLAN"
ENUM_ADDITIONS: tuple[tuple[str, tuple[str, ...]], ...] = (("AiTask", ("UNDERSTAND",)),)
ENUM_REMOVALS: tuple[str, ...] = ("LiveTier",)
LIVE_TIERS = ("T3", "T4")
TASK_COLUMNS = (("RoutePolicy", "task"), ("UsageEvent", "task"))
REQUEST_ID_CHARS = 64
LIVE = "LiveCandidate"
COPY_PLAN_ROUTES = (
    'INSERT INTO "RoutePolicy" (task, ordinal, "providerId", model, "maxOutputTokens", temperature, enabled, params) '
    'SELECT CAST(:understand AS "AiTask"), ordinal, "providerId", model, "maxOutputTokens", temperature, enabled, '
    'params FROM "RoutePolicy" WHERE task = CAST(:plan AS "AiTask") '
    "ON CONFLICT (task, ordinal) DO NOTHING"
)
DELETE_UNDERSTAND_ROUTES = 'DELETE FROM "RoutePolicy" WHERE task::text = :understand'
UNDERSTAND_USAGE_AS_PLAN = (
    'UPDATE "UsageEvent" SET task = CAST(:plan AS "AiTask") WHERE task::text = :understand'
)


def upgrade() -> None:
    with op.get_context().autocommit_block():
        for enum_name, values in ENUM_ADDITIONS:
            for value in values:
                op.execute(f"ALTER TYPE \"{enum_name}\" ADD VALUE IF NOT EXISTS '{value}'")
    op.execute(sa.text(COPY_PLAN_ROUTES).bindparams(understand=UNDERSTAND, plan=PLAN))
    op.add_column("Answer", sa.Column("requestId", sa.String(length=REQUEST_ID_CHARS), nullable=True))
    op.create_index(op.f("Answer_requestId_idx"), "Answer", ["requestId"], unique=False)
    op.drop_constraint(op.f("AnswerCitation_liveCandidateId_fkey"), "AnswerCitation", type_="foreignkey")
    op.drop_column("AnswerCitation", "liveCandidateId")
    op.drop_column("Answer", "liveCandidateIds")
    op.drop_table("LiveCandidate")
    for enum_name in ENUM_REMOVALS:
        op.execute(f'DROP TYPE "{enum_name}"')


def downgrade() -> None:
    listed = ", ".join(f"'{tier}'" for tier in LIVE_TIERS)
    op.execute(f'CREATE TYPE "LiveTier" AS ENUM ({listed})')
    _live_candidates()
    op.add_column(
        "Answer",
        sa.Column(
            "liveCandidateIds",
            postgresql.ARRAY(sa.UUID()),
            server_default=sa.text("ARRAY[]::uuid[]"),
            nullable=False,
        ),
    )
    op.add_column("AnswerCitation", sa.Column("liveCandidateId", sa.UUID(), nullable=True))
    op.create_foreign_key(
        op.f("AnswerCitation_liveCandidateId_fkey"),
        "AnswerCitation",
        LIVE,
        ["liveCandidateId"],
        ["id"],
        ondelete="SET NULL",
    )
    op.drop_index(op.f("Answer_requestId_idx"), table_name="Answer")
    op.drop_column("Answer", "requestId")
    op.execute(sa.text(DELETE_UNDERSTAND_ROUTES).bindparams(understand=UNDERSTAND))
    op.execute(sa.text(UNDERSTAND_USAGE_AS_PLAN).bindparams(understand=UNDERSTAND, plan=PLAN))
    _recreate_tasks_without_understand()


def _live_candidates() -> None:
    op.create_table(
        LIVE, *_live_columns(), *_live_keys(), sa.PrimaryKeyConstraint("id", name=op.f(f"{LIVE}_pkey"))
    )
    for column in ("answerId", "expiresAt", "userId"):
        op.create_index(op.f(f"{LIVE}_{column}_idx"), LIVE, [column], unique=False)
    op.execute(f'ALTER TABLE "{LIVE}" ENABLE ROW LEVEL SECURITY')


def _live_columns() -> list[sa.Column]:
    return [
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("answerId", sa.UUID(), nullable=True),
        sa.Column("userId", sa.UUID(), nullable=True),
        sa.Column("tier", postgresql.ENUM("T3", "T4", name="LiveTier", create_type=False), nullable=False),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("webFetchId", sa.UUID(), nullable=True),
        sa.Column("sourceLabel", sa.String(length=300), nullable=True),
        sa.Column("quote", sa.String(length=300), nullable=False),
        sa.Column(
            "quoteCheck",
            postgresql.ENUM("PASS", "FAIL", "NA", name="QuoteCheck", create_type=False),
            server_default="NA",
            nullable=False,
        ),
        sa.Column("facet", sa.String(length=120), nullable=True),
        sa.Column("writtenBackClaimId", sa.UUID(), nullable=True),
        sa.Column(
            "expiresAt",
            sa.DateTime(timezone=True),
            server_default=sa.text("now() + interval '30 days'"),
            nullable=False,
        ),
        sa.Column("createdAt", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    ]


def _live_keys() -> list[sa.ForeignKeyConstraint]:
    keys = (
        ("answerId", "Answer.id", "CASCADE"),
        ("userId", "User.id", "CASCADE"),
        ("webFetchId", "WebFetch.id", "SET NULL"),
        ("writtenBackClaimId", "Claim.id", "SET NULL"),
    )
    return [
        sa.ForeignKeyConstraint([column], [target], name=op.f(f"{LIVE}_{column}_fkey"), ondelete=ondelete)
        for column, target, ondelete in keys
    ]


def _recreate_tasks_without_understand() -> None:
    query = sa.text('SELECT unnest(enum_range(NULL::"AiTask"))::text')
    kept = [value for (value,) in op.get_bind().execute(query) if value != UNDERSTAND]
    listed = ", ".join(f"'{value}'" for value in kept)
    op.execute('ALTER TYPE "AiTask" RENAME TO "AiTask_before_0071"')
    op.execute(f'CREATE TYPE "AiTask" AS ENUM ({listed})')
    for table, column in TASK_COLUMNS:
        op.execute(
            f'ALTER TABLE "{table}" ALTER COLUMN "{column}" TYPE "AiTask" USING "{column}"::text::"AiTask"'
        )
    op.execute('DROP TYPE "AiTask_before_0071"')
