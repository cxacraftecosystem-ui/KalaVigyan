from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0091_craft_page_archive_dropped"
down_revision: str | Sequence[str] | None = "0086_mcp_call_name_required"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

ARCHIVE = "CraftPageArchive"
VARIANTS = "\"variant\" IN ('OPEN', 'RESEARCHER')"
REVOKE_PUBLIC_ROLES = f"""
DO $do$
DECLARE grantee text;
BEGIN
    FOREACH grantee IN ARRAY ARRAY['anon', 'authenticated'] LOOP
        IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = grantee) THEN
            EXECUTE format('REVOKE ALL ON "{ARCHIVE}" FROM %I', grantee);
        END IF;
    END LOOP;
END
$do$
"""


def upgrade() -> None:
    op.drop_table("CraftPageArchive")


def downgrade() -> None:
    op.create_table(
        "CraftPageArchive",
        sa.Column("craftId", sa.UUID(), nullable=False),
        sa.Column("curationVersion", sa.Integer(), nullable=False),
        sa.Column("variant", sa.Text(), nullable=False),
        sa.Column("body", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("etag", sa.Text(), nullable=False),
        sa.Column("frozenAt", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["craftId"], ["Craft.id"], name=op.f("CraftPageArchive_craftId_fkey"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("craftId", "curationVersion", "variant", name=op.f("CraftPageArchive_pkey")),
        sa.CheckConstraint(VARIANTS, name=op.f("CraftPageArchive_variant_check")),
    )
    op.execute(f'ALTER TABLE "{ARCHIVE}" ENABLE ROW LEVEL SECURITY')
    op.execute(REVOKE_PUBLIC_ROLES)
