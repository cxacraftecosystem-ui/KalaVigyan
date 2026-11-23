from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0079_shared_export_files"
down_revision: str | Sequence[str] | None = "0072_quantities_kind"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

FILES = "SharedExportFile"
OBJECT_KEY_CHARS = 1024
SHARE_TOKEN_CHARS = 64
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
    op.create_table(
        "SharedExportFile",
        sa.Column("key", sa.String(length=OBJECT_KEY_CHARS), nullable=False),
        sa.Column("shareToken", sa.String(length=SHARE_TOKEN_CHARS), nullable=False),
        sa.Column("createdAt", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("key", name=op.f(f"{FILES}_pkey")),
    )
    op.create_index(op.f(f"{FILES}_shareToken_idx"), FILES, ["shareToken"], unique=False)
    op.execute(f'ALTER TABLE "{FILES}" ENABLE ROW LEVEL SECURITY')
    op.execute(REVOKE_PUBLIC_ROLES.format(table=FILES))


def downgrade() -> None:
    op.drop_index(op.f(f"{FILES}_shareToken_idx"), table_name=FILES)
    op.drop_table("SharedExportFile")
