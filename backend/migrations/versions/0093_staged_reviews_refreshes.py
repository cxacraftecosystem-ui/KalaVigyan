from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0093_staged_reviews_refreshes"
down_revision: str | Sequence[str] | None = "0092_readings_layers_categories"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

BATCHES = "StagedReview"
ITEMS = "StagedReviewItem"
JOBS = "PageRefreshJob"
STAMP = sa.DateTime(timezone=True)
CODE_CHARS = 16
NAME_CHARS = 120
LABEL_CHARS = 300
OUTCOME_CHARS = 500
STAGED_KINDS = (
    "FACTS",
    "COMPONENTS",
    "LAYOUTS",
    "STRUCTURE",
    "READINGS",
    "LAYERS",
    "STAGES",
    "SOURCES",
    "SOURCES_DIFFER",
)
STAGED_ACTIONS = ("approve", "reject", "raise", "retract", "correct", "clear")
BATCH_STATUSES = ("OPEN", "CONFIRMED", "DISCARDED")
ITEM_STATES = ("STAGED", "APPLIED", "REFUSED", "SKIPPED")
REFRESH_SCOPES = ("CHANGED", "EVERY", "NAMED")
REFRESH_ORIGINS = ("WEB", "MCP", "NIGHT", "REVIEW")
REFRESH_STATUSES = ("RUNNING", "DONE", "FAILED")
REFRESH_PHASES = ("PAGES", "DOCUMENTS", "REFRESHING", "FINISHED")
REVOKE_PUBLIC_ROLES = """
DO $do$
DECLARE grantee text;
BEGIN
    FOREACH grantee IN ARRAY ARRAY['anon', 'authenticated'] LOOP
        IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = grantee) THEN
            EXECUTE format('REVOKE ALL ON "StagedReview" FROM %I', grantee);
            EXECUTE format('REVOKE ALL ON "StagedReviewItem" FROM %I', grantee);
            EXECUTE format('REVOKE ALL ON "PageRefreshJob" FROM %I', grantee);
        END IF;
    END LOOP;
END
$do$
"""


def upgrade() -> None:
    _batches()
    _items()
    _jobs()
    for table in (BATCHES, ITEMS, JOBS):
        op.execute(f'ALTER TABLE "{table}" ENABLE ROW LEVEL SECURITY')
    op.execute(REVOKE_PUBLIC_ROLES)


def downgrade() -> None:
    op.drop_table(JOBS)
    op.drop_table(ITEMS)
    op.drop_table(BATCHES)


def _batches() -> None:
    op.create_table(
        "StagedReview",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("proposerId", sa.UUID(), nullable=True),
        sa.Column("grantId", sa.UUID(), nullable=True),
        sa.Column("tokenId", sa.UUID(), nullable=True),
        sa.Column("clientName", sa.String(length=NAME_CHARS), nullable=False),
        sa.Column("status", sa.String(length=CODE_CHARS), server_default="OPEN", nullable=False),
        sa.Column("decidedById", sa.UUID(), nullable=True),
        sa.Column("decidedAt", STAMP, nullable=True),
        sa.Column("createdAt", STAMP, server_default=sa.text("now()"), nullable=False),
        sa.Column("expiresAt", STAMP, nullable=False),
        _check(BATCHES, "status", _listed("status", BATCH_STATUSES)),
        _check(BATCHES, "decided", '"status" = \'OPEN\' OR "decidedAt" IS NOT NULL'),
        _check(BATCHES, "expires", '"expiresAt" > "createdAt"'),
        _fk(BATCHES, "proposerId", "User"),
        _fk(BATCHES, "grantId", "OAuthGrant"),
        _fk(BATCHES, "tokenId", "OAuthToken"),
        _fk(BATCHES, "decidedById", "User"),
        sa.PrimaryKeyConstraint("id", name=op.f(f"{BATCHES}_pkey")),
    )
    op.create_index(op.f(f"{BATCHES}_status_createdAt_idx"), BATCHES, ["status", "createdAt"])
    op.create_index(op.f(f"{BATCHES}_proposerId_createdAt_idx"), BATCHES, ["proposerId", "createdAt"])
    for column in ("decidedById", "grantId", "tokenId"):
        op.create_index(op.f(f"{BATCHES}_{column}_idx"), BATCHES, [column])


def _items() -> None:
    op.create_table(
        "StagedReviewItem",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("batchId", sa.UUID(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(length=CODE_CHARS), nullable=False),
        sa.Column("itemId", sa.UUID(), nullable=False),
        sa.Column("action", sa.String(length=CODE_CHARS), nullable=False),
        sa.Column("decision", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("label", sa.String(length=LABEL_CHARS), nullable=False),
        sa.Column("state", sa.String(length=CODE_CHARS), server_default="STAGED", nullable=False),
        sa.Column("applied", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("outcome", sa.String(length=OUTCOME_CHARS), nullable=True),
        _check(ITEMS, "kind", _listed("kind", STAGED_KINDS)),
        _check(ITEMS, "action", _listed("action", STAGED_ACTIONS)),
        _check(ITEMS, "state", _listed("state", ITEM_STATES)),
        _check(ITEMS, "position", '"position" >= 0'),
        _check(ITEMS, "decision", "jsonb_typeof(\"decision\") = 'object'"),
        sa.ForeignKeyConstraint(
            ["batchId"], [f"{BATCHES}.id"], name=op.f(f"{ITEMS}_batchId_fkey"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f(f"{ITEMS}_pkey")),
        sa.UniqueConstraint("batchId", "position", name=op.f(f"{ITEMS}_batchId_position_key")),
    )
    op.create_index(op.f(f"{ITEMS}_kind_itemId_idx"), ITEMS, ["kind", "itemId"])


def _jobs() -> None:
    op.create_table(
        "PageRefreshJob",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("scope", sa.String(length=CODE_CHARS), nullable=False),
        sa.Column("origin", sa.String(length=CODE_CHARS), nullable=False),
        sa.Column("startedById", sa.UUID(), nullable=True),
        sa.Column("clientName", sa.String(length=NAME_CHARS), nullable=True),
        sa.Column("owners", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("status", sa.String(length=CODE_CHARS), server_default="RUNNING", nullable=False),
        sa.Column("phase", sa.String(length=CODE_CHARS), server_default="PAGES", nullable=False),
        sa.Column(
            "progress",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("startedAt", STAMP, nullable=False),
        sa.Column("finishedAt", STAMP, nullable=True),
        _check(JOBS, "scope", _listed("scope", REFRESH_SCOPES)),
        _check(JOBS, "origin", _listed("origin", REFRESH_ORIGINS)),
        _check(JOBS, "status", _listed("status", REFRESH_STATUSES)),
        _check(JOBS, "phase", _listed("phase", REFRESH_PHASES)),
        _check(JOBS, "finished", '"status" = \'RUNNING\' OR "finishedAt" IS NOT NULL'),
        _fk(JOBS, "startedById", "User"),
        sa.PrimaryKeyConstraint("id", name=op.f(f"{JOBS}_pkey")),
    )
    op.create_index(
        "PageRefreshJob_one_running_idx",
        JOBS,
        ["status"],
        unique=True,
        postgresql_where=sa.text("\"status\" = 'RUNNING'"),
    )
    op.create_index(op.f(f"{JOBS}_startedAt_idx"), JOBS, ["startedAt"])
    op.create_index(op.f(f"{JOBS}_startedById_idx"), JOBS, ["startedById"])


def _listed(column: str, values: Sequence[str]) -> str:
    named = ", ".join(f"'{value}'" for value in values)
    return f'"{column}" IN ({named})'


def _check(table: str, name: str, condition: str) -> sa.CheckConstraint:
    return sa.CheckConstraint(condition, name=op.f(f"{table}_{name}_check"))


def _fk(table: str, column: str, target: str) -> sa.ForeignKeyConstraint:
    return sa.ForeignKeyConstraint(
        [column], [f"{target}.id"], name=op.f(f"{table}_{column}_fkey"), ondelete="SET NULL"
    )
