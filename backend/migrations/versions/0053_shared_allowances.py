from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0053_shared_allowances"
down_revision: str | Sequence[str] | None = "0054_field_photo_reviews"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLE = "AllowanceBucket"
HOLDER_CHARS = 80
KIND_CHARS = 40
LAST_TAKEN = '"lastTaken" >= 0 AND "lastTaken" <= "used"'

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
        "AllowanceBucket",
        sa.Column("holder", sa.String(length=HOLDER_CHARS), nullable=False),
        sa.Column("kind", sa.String(length=KIND_CHARS), nullable=False),
        sa.Column("hourStart", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used", sa.Integer(), nullable=False),
        sa.Column("lastTaken", sa.Integer(), nullable=False),
        sa.CheckConstraint('"used" >= 0', name=op.f(f"{TABLE}_used_check")),
        sa.CheckConstraint(LAST_TAKEN, name=op.f(f"{TABLE}_last_taken_check")),
        sa.PrimaryKeyConstraint("holder", "kind", "hourStart", name=op.f(f"{TABLE}_pkey")),
    )
    op.create_index(op.f(f"{TABLE}_hourStart_idx"), TABLE, ["hourStart"])
    op.execute(f'ALTER TABLE "{TABLE}" ENABLE ROW LEVEL SECURITY')
    op.execute(REVOKE_PUBLIC_ROLES.format(table=TABLE))


def downgrade() -> None:
    op.drop_index(op.f(f"{TABLE}_hourStart_idx"), table_name=TABLE)
    op.drop_table(TABLE)
