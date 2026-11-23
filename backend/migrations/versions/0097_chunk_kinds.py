from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0097_chunk_kinds"
down_revision: str | Sequence[str] | None = "0093_staged_reviews_refreshes"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLE = "Chunk"
KIND_CHARS = 16
CHUNK_KINDS = ("PASSAGE", "WINDOW")
WINDOW = "WINDOW"
WINDOW_ACL = "SIGNED_IN"
KIND_CHECK = f"{TABLE}_kind_check"
MARK_TRIGGER = "Chunk_kind_window_mark"
MARK_FUNCTION = f"""
CREATE OR REPLACE FUNCTION kv_mark_window_chunk() RETURNS trigger
LANGUAGE plpgsql AS $fn$
BEGIN
    IF NEW."acl" = '{WINDOW_ACL}' THEN
        NEW."kind" := '{WINDOW}';
    END IF;
    RETURN NEW;
END
$fn$
"""
CREATE_TRIGGER = f"""
CREATE TRIGGER "{MARK_TRIGGER}"
BEFORE INSERT ON "{TABLE}"
FOR EACH ROW EXECUTE FUNCTION kv_mark_window_chunk()
"""
MARK_WINDOWS = f"""UPDATE "{TABLE}" SET "kind" = '{WINDOW}' WHERE "acl" = '{WINDOW_ACL}'"""


def upgrade() -> None:
    op.add_column(
        "Chunk",
        sa.Column("kind", sa.String(length=KIND_CHARS), nullable=False, server_default=CHUNK_KINDS[0]),
    )
    listed = ", ".join(f"'{kind}'" for kind in CHUNK_KINDS)
    op.create_check_constraint(op.f(KIND_CHECK), TABLE, f'"kind" IN ({listed})')
    op.execute(MARK_WINDOWS)
    op.execute(MARK_FUNCTION)
    op.execute(CREATE_TRIGGER)


def downgrade() -> None:
    op.execute(f'DROP TRIGGER IF EXISTS "{MARK_TRIGGER}" ON "{TABLE}"')
    op.execute("DROP FUNCTION IF EXISTS kv_mark_window_chunk()")
    op.drop_constraint(op.f(KIND_CHECK), TABLE, type_="check")
    op.drop_column("Chunk", "kind")
