from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0126_long_sessions"
down_revision: str | Sequence[str] | None = "0125_section_proposals"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLE = "SiteSession"
STAMP = sa.DateTime(timezone=True)
REVOKE_PUBLIC_ROLES = """
DO $do$
DECLARE grantee text;
BEGIN
    FOREACH grantee IN ARRAY ARRAY['anon', 'authenticated'] LOOP
        IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = grantee) THEN
            EXECUTE format('REVOKE ALL ON "SiteSession" FROM %I', grantee);
        END IF;
    END LOOP;
END
$do$
"""


def upgrade() -> None:
    op.create_table(
        TABLE,
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("userId", sa.UUID(), nullable=False),
        sa.Column("createdAt", STAMP, server_default=sa.text("now()"), nullable=False),
        sa.Column("renewedAt", STAMP, server_default=sa.text("now()"), nullable=False),
        sa.Column("endedAt", STAMP, nullable=True),
        sa.ForeignKeyConstraint(
            ["userId"], ["User.id"], name=op.f(f"{TABLE}_userId_fkey"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f(f"{TABLE}_pkey")),
    )
    op.create_index(op.f(f"{TABLE}_userId_idx"), TABLE, ["userId"])
    op.execute(f'ALTER TABLE "{TABLE}" ENABLE ROW LEVEL SECURITY')
    op.execute(REVOKE_PUBLIC_ROLES)


def downgrade() -> None:
    op.drop_table(TABLE)
