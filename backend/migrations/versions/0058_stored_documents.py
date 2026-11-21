from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0058_stored_documents"
down_revision: str | Sequence[str] | None = "0057_open_data_releases"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLE = "StoredDocument"
STAMP = sa.DateTime(timezone=True)
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
        "StoredDocument",
        sa.Column("subjectKind", sa.String(length=20), nullable=False),
        sa.Column("subjectSlug", sa.String(length=200), nullable=False),
        sa.Column("language", sa.String(length=16), server_default="en", nullable=False),
        sa.Column("stamp", sa.String(length=64), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("contentHash", sa.String(length=64), nullable=False),
        sa.Column("document", sa.Text(), nullable=False),
        sa.Column("builtAt", STAMP, nullable=False),
        sa.Column("wantedAt", STAMP, nullable=True),
        sa.CheckConstraint('"version" >= 1', name=op.f(f"{TABLE}_version_check")),
        sa.PrimaryKeyConstraint("subjectKind", "subjectSlug", "language", name=op.f(f"{TABLE}_pkey")),
    )
    op.execute(f'ALTER TABLE "{TABLE}" ENABLE ROW LEVEL SECURITY')
    op.execute(REVOKE_PUBLIC_ROLES.replace("{table}", TABLE))


def downgrade() -> None:
    op.drop_table(TABLE)
