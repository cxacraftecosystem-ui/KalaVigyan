from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0074_mcp_activity"
down_revision: str | Sequence[str] | None = "0071_understand_and_answer_rows"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

CALLS = "McpToolCall"
DAYS = "McpToolCallDay"
CLIENT_NAME_CHARS = 120
TOOL_NAME_CHARS = 64
OUTCOME_CHARS = 16
REASON_CHARS = 300
OUTCOMES = "\"outcome\" IN ('OK', 'TOOL_ERROR', 'PROTOCOL_ERROR')"
REASON_ONLY_ON_FAILURE = '"outcome" <> \'OK\' OR "reason" IS NULL'
NAME_EACH_CALL = """
UPDATE "McpToolCall" AS c SET "clientName" = k."name"
FROM "OAuthGrant" AS g JOIN "OAuthClient" AS k ON k."id" = g."clientId"
WHERE g."id" = c."grantId"
"""
REVOKE_PUBLIC_ROLES = """
DO $do$
DECLARE grantee text;
BEGIN
    FOREACH grantee IN ARRAY ARRAY['anon', 'authenticated'] LOOP
        IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = grantee) THEN
            EXECUTE format('REVOKE ALL ON "{table}" FROM %I', grantee);
        END IF;
    END LOOP;
END
$do$
"""


def upgrade() -> None:
    op.add_column("McpToolCall", sa.Column("clientName", sa.String(length=CLIENT_NAME_CHARS), nullable=True))
    op.add_column("McpToolCall", sa.Column("reason", sa.String(length=REASON_CHARS), nullable=True))
    op.execute(NAME_EACH_CALL)
    op.alter_column(CALLS, "clientName", nullable=False)
    op.create_check_constraint(op.f(f"{CALLS}_reason_check"), CALLS, REASON_ONLY_ON_FAILURE)
    op.create_table(
        "McpToolCallDay",
        sa.Column("day", sa.Date(), nullable=False),
        sa.Column("clientName", sa.String(length=CLIENT_NAME_CHARS), nullable=False),
        sa.Column("tool", sa.String(length=TOOL_NAME_CHARS), nullable=False),
        sa.Column("outcome", sa.String(length=OUTCOME_CHARS), nullable=False),
        sa.Column("calls", sa.Integer(), nullable=False),
        sa.CheckConstraint(OUTCOMES, name=op.f(f"{DAYS}_outcome_check")),
        sa.CheckConstraint('"calls" >= 1', name=op.f(f"{DAYS}_calls_check")),
        sa.PrimaryKeyConstraint("day", "clientName", "tool", "outcome", name=op.f(f"{DAYS}_pkey")),
    )
    op.execute(f'ALTER TABLE "{DAYS}" ENABLE ROW LEVEL SECURITY')
    op.execute(REVOKE_PUBLIC_ROLES.format(table=DAYS))


def downgrade() -> None:
    op.drop_table("McpToolCallDay")
    op.drop_constraint(op.f(f"{CALLS}_reason_check"), CALLS, type_="check")
    op.drop_column("McpToolCall", "reason")
    op.drop_column("McpToolCall", "clientName")
