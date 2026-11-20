from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0048_contribution_queue"
down_revision: str | Sequence[str] | None = "0047_structure_proposals"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

QUEUE = "QueuedProposal"
STEWARD = "CraftSteward"
OVERRIDE = "TrustTierOverride"
TABLES = (QUEUE, STEWARD, OVERRIDE)
STAMP = sa.DateTime(timezone=True)
STATES = ("QUEUED", "CHECKING", "DONE", "FAILED")
KINDS = ("FACT",)
ORIGINS = ("CONTRIBUTION", "AGENT")
OUTCOMES = ("PUBLISHED", "WAITING", "REFUSED")
TIERS = ("NEW", "ESTABLISHED", "PROVEN")
REVOKE_PUBLIC_ROLES = """
DO $do$
DECLARE grantee text;
BEGIN
    FOREACH grantee IN ARRAY ARRAY['anon', 'authenticated'] LOOP
        IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = grantee) THEN
            EXECUTE format('REVOKE ALL ON %I FROM %I', '{table}', grantee);
        END IF;
    END LOOP;
END
$do$
"""


def upgrade() -> None:
    _queue()
    _stewards()
    _overrides()
    for table in TABLES:
        op.execute(f'ALTER TABLE "{table}" ENABLE ROW LEVEL SECURITY')
        op.execute(REVOKE_PUBLIC_ROLES.replace("{table}", table))


def downgrade() -> None:
    for table in reversed(TABLES):
        op.drop_table(table)


def _queue() -> None:
    op.create_table(
        "QueuedProposal",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("proposerId", sa.UUID(), nullable=False),
        sa.Column("kind", sa.String(length=16), server_default="FACT", nullable=False),
        sa.Column("origin", sa.String(length=16), nullable=False),
        sa.Column("idempotencyKey", sa.String(length=120), nullable=False),
        sa.Column("fingerprint", sa.String(length=64), nullable=False),
        sa.Column("subjectKey", sa.String(length=240), nullable=False),
        sa.Column("taskKey", sa.String(length=240), nullable=True),
        sa.Column("proposal", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("state", sa.String(length=16), server_default="QUEUED", nullable=False),
        sa.Column("attempts", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("availableAt", STAMP, server_default=sa.text("now()"), nullable=False),
        sa.Column("leaseUntil", STAMP, nullable=True),
        sa.Column("startedAt", STAMP, nullable=True),
        sa.Column("finishedAt", STAMP, nullable=True),
        sa.Column("outcome", sa.String(length=16), nullable=True),
        sa.Column("claimId", sa.UUID(), nullable=True),
        sa.Column("reply", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("failure", sa.String(length=500), nullable=True),
        sa.Column("modelCalls", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("costUsd", sa.Numeric(10, 6), server_default=sa.text("0"), nullable=False),
        sa.Column("createdAt", STAMP, server_default=sa.text("now()"), nullable=False),
        sa.Column("updatedAt", STAMP, server_default=sa.text("now()"), nullable=False),
        *_queue_rules(),
    )
    op.create_index(
        "QueuedProposal_proposerId_idempotencyKey_key", QUEUE, ["proposerId", "idempotencyKey"], unique=True
    )
    for columns in (
        ["state", "availableAt"],
        ["proposerId", "createdAt"],
        ["subjectKey", "state"],
        ["claimId"],
    ):
        op.create_index(op.f(f"{QUEUE}_{'_'.join(columns)}_idx"), QUEUE, columns)


def _stewards() -> None:
    op.create_table(
        "CraftSteward",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("userId", sa.UUID(), nullable=False),
        sa.Column("craftId", sa.UUID(), nullable=False),
        sa.Column("adoptedAt", STAMP, nullable=False),
        sa.Column("droppedAt", STAMP, nullable=True),
        sa.Column(
            "seenTaskKeys",
            postgresql.ARRAY(sa.Text()),
            server_default=sa.text("ARRAY[]::text[]"),
            nullable=False,
        ),
        sa.Column("seenAt", STAMP, nullable=True),
        sa.Column("createdAt", STAMP, server_default=sa.text("now()"), nullable=False),
        sa.Column("updatedAt", STAMP, server_default=sa.text("now()"), nullable=False),
        _check(STEWARD, "dropped", '"droppedAt" IS NULL OR "droppedAt" >= "adoptedAt"'),
        _fk(STEWARD, "userId", "User", "CASCADE"),
        _fk(STEWARD, "craftId", "Craft", "CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f(f"{STEWARD}_pkey")),
    )
    op.create_index(
        "CraftSteward_userId_craftId_live_key",
        STEWARD,
        ["userId", "craftId"],
        unique=True,
        postgresql_where=sa.text('"droppedAt" IS NULL'),
    )
    for columns in (["craftId", "droppedAt"], ["userId", "droppedAt"]):
        op.create_index(op.f(f"{STEWARD}_{'_'.join(columns)}_idx"), STEWARD, columns)


def _overrides() -> None:
    op.create_table(
        "TrustTierOverride",
        sa.Column("userId", sa.UUID(), nullable=False),
        sa.Column("tier", sa.String(length=16), nullable=False),
        sa.Column("note", sa.String(length=500), nullable=True),
        sa.Column("setById", sa.UUID(), nullable=True),
        sa.Column("setAt", STAMP, nullable=False),
        sa.Column("createdAt", STAMP, server_default=sa.text("now()"), nullable=False),
        sa.Column("updatedAt", STAMP, server_default=sa.text("now()"), nullable=False),
        _check(OVERRIDE, "tier", _listed("tier", TIERS)),
        _fk(OVERRIDE, "userId", "User", "CASCADE"),
        _fk(OVERRIDE, "setById", "User", "SET NULL"),
        sa.PrimaryKeyConstraint("userId", name=op.f(f"{OVERRIDE}_pkey")),
    )
    op.create_index(op.f(f"{OVERRIDE}_setById_idx"), OVERRIDE, ["setById"])


def _queue_rules() -> tuple[sa.Constraint, ...]:
    return (
        _check(QUEUE, "kind", _listed("kind", KINDS)),
        _check(QUEUE, "origin", _listed("origin", ORIGINS)),
        _check(QUEUE, "state", _listed("state", STATES)),
        _check(QUEUE, "outcome", f'"outcome" IS NULL OR {_listed("outcome", OUTCOMES)}'),
        _check(QUEUE, "done", '("state" = \'DONE\') = ("outcome" IS NOT NULL)'),
        _check(QUEUE, "proposal", "jsonb_typeof(\"proposal\") = 'object'"),
        _check(QUEUE, "counts", '"attempts" >= 0 AND "modelCalls" >= 0'),
        _fk(QUEUE, "proposerId", "User", "CASCADE"),
        _fk(QUEUE, "claimId", "Claim", "SET NULL"),
        sa.PrimaryKeyConstraint("id", name=op.f(f"{QUEUE}_pkey")),
    )


def _listed(column: str, values: tuple[str, ...]) -> str:
    named = ", ".join(f"'{value}'" for value in values)
    return f'"{column}" IN ({named})'


def _check(table: str, name: str, condition: str) -> sa.CheckConstraint:
    return sa.CheckConstraint(condition, name=op.f(f"{table}_{name}_check"))


def _fk(table: str, column: str, target: str, ondelete: str) -> sa.ForeignKeyConstraint:
    return sa.ForeignKeyConstraint(
        [column], [f"{target}.id"], name=op.f(f"{table}_{column}_fkey"), ondelete=ondelete
    )
