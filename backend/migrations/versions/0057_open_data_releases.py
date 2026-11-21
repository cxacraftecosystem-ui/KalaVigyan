from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0057_open_data_releases"
down_revision: str | Sequence[str] | None = "0056_datasets_and_materials"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLE = "OpenDataRelease"
STAMP = sa.DateTime(timezone=True)
DEPOSIT_TARGETS = ("SANDBOX", "ZENODO")
RELEASE_STATES = ("DRAFT", "PUBLISHED")
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
        "OpenDataRelease",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("target", sa.String(length=16), nullable=False),
        sa.Column("version", sa.String(length=20), nullable=False),
        sa.Column("releasedOn", sa.Date(), nullable=False),
        sa.Column("state", sa.String(length=16), server_default="DRAFT", nullable=False),
        sa.Column("doi", sa.String(length=255), nullable=False),
        sa.Column("conceptDoi", sa.String(length=255), nullable=False),
        sa.Column("recordId", sa.Integer(), nullable=False),
        sa.Column("conceptRecordId", sa.Integer(), nullable=False),
        sa.Column("recordUrl", sa.String(length=255), nullable=True),
        sa.Column("files", postgresql.JSONB(), server_default=sa.text("'[]'::jsonb"), nullable=False),
        sa.Column("counts", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("changes", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("rowDigests", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("totalBytes", sa.BigInteger(), server_default=sa.text("0"), nullable=False),
        sa.Column("manifestSha256", sa.String(length=64), nullable=False),
        sa.Column("publishedAt", STAMP, nullable=True),
        sa.Column("createdAt", STAMP, server_default=sa.text("now()"), nullable=False),
        sa.Column("updatedAt", STAMP, server_default=sa.text("now()"), nullable=False),
        *_checks(),
        sa.PrimaryKeyConstraint("id", name=op.f(f"{TABLE}_pkey")),
        sa.UniqueConstraint("target", "version", name=op.f(f"{TABLE}_target_version_key")),
    )
    op.create_index(op.f(f"{TABLE}_target_state_releasedOn_idx"), TABLE, ["target", "state", "releasedOn"])
    op.execute(f'ALTER TABLE "{TABLE}" ENABLE ROW LEVEL SECURITY')
    op.execute(REVOKE_PUBLIC_ROLES.replace("{table}", TABLE))


def downgrade() -> None:
    op.drop_table(TABLE)


def _checks() -> list[sa.CheckConstraint]:
    rules = {
        "target": f'"target" IN ({_listed(DEPOSIT_TARGETS)})',
        "state": f'"state" IN ({_listed(RELEASE_STATES)})',
        "manifestSha256": "\"manifestSha256\" ~ '^[0-9a-f]{64}$'",
        "totalBytes": '"totalBytes" >= 0',
        "published": '("state" = \'PUBLISHED\') = ("publishedAt" IS NOT NULL)',
    }
    return [sa.CheckConstraint(rule, name=op.f(f"{TABLE}_{name}_check")) for name, rule in rules.items()]


def _listed(values: Sequence[str]) -> str:
    return ", ".join(f"'{value}'" for value in values)
