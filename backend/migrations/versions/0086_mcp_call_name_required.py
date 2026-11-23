from collections.abc import Sequence

from alembic import op

revision: str = "0086_mcp_call_name_required"
down_revision: str | Sequence[str] | None = "0083_piece_districts_and_places"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

FILL_TRIGGER = "McpToolCall_clientName_fill"
FILL_FUNCTION = """
CREATE OR REPLACE FUNCTION kv_fill_mcp_client_name() RETURNS trigger
LANGUAGE plpgsql AS $fn$
BEGIN
    IF NEW."clientName" IS NULL THEN
        SELECT k."name" INTO NEW."clientName"
        FROM "OAuthGrant" AS g JOIN "OAuthClient" AS k ON k."id" = g."clientId"
        WHERE g."id" = NEW."grantId";
    END IF;
    RETURN NEW;
END
$fn$
"""
CREATE_TRIGGER = f"""
CREATE TRIGGER "{FILL_TRIGGER}"
BEFORE INSERT ON "McpToolCall"
FOR EACH ROW EXECUTE FUNCTION kv_fill_mcp_client_name()
"""


def upgrade() -> None:
    op.execute(f'DROP TRIGGER IF EXISTS "{FILL_TRIGGER}" ON "McpToolCall"')
    op.execute("DROP FUNCTION IF EXISTS kv_fill_mcp_client_name()")


def downgrade() -> None:
    op.execute(FILL_FUNCTION)
    op.execute(CREATE_TRIGGER)
