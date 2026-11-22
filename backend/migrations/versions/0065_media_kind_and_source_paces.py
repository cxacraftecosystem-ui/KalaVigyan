from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0065_media_kind_and_source_paces"
down_revision: str | Sequence[str] | None = "0062_open_data_scope"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PACE = "SourcePace"
LEASE = "SourceLease"
TABLES = (PACE, LEASE)
STAMP = sa.DateTime(timezone=True)
SERVICE_CHARS = 40
LANE_CHARS = 20
ENUM_ADDITIONS: tuple[tuple[str, tuple[str, ...]], ...] = (("SourceKind", ("MEDIA",)),)
COMMONS_FILES = (
    "UPDATE \"Source\" SET kind = 'MEDIA' WHERE kind = 'OTHER' "
    "AND url LIKE 'https://commons.wikimedia.org/wiki/File:%' "
    "AND url NOT ILIKE '%.pdf' AND url NOT ILIKE '%.djvu'"
)
MEDIA_BACK = "UPDATE \"Source\" SET kind = 'OTHER' WHERE kind = 'MEDIA'"
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
    with op.get_context().autocommit_block():
        for enum_name, values in ENUM_ADDITIONS:
            for value in values:
                op.execute(f"ALTER TYPE \"{enum_name}\" ADD VALUE IF NOT EXISTS '{value}'")
    op.execute(COMMONS_FILES)
    _paces()
    _leases()
    for table in TABLES:
        op.execute(f'ALTER TABLE "{table}" ENABLE ROW LEVEL SECURITY')
        op.execute(REVOKE_PUBLIC_ROLES.replace("{table}", table))


def downgrade() -> None:
    for table in reversed(TABLES):
        op.drop_table(table)
    op.execute(MEDIA_BACK)


def _paces() -> None:
    op.create_table(
        "SourcePace",
        sa.Column("service", sa.String(length=SERVICE_CHARS), nullable=False),
        sa.Column("lane", sa.String(length=LANE_CHARS), nullable=False),
        sa.Column("freeAt", STAMP, nullable=False),
        sa.Column("heldUntil", STAMP, nullable=False),
        sa.CheckConstraint("\"service\" <> ''", name=op.f(f"{PACE}_service_check")),
        sa.CheckConstraint("\"lane\" <> ''", name=op.f(f"{PACE}_lane_check")),
        sa.PrimaryKeyConstraint("service", "lane", name=op.f(f"{PACE}_pkey")),
    )


def _leases() -> None:
    op.create_table(
        "SourceLease",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("service", sa.String(length=SERVICE_CHARS), nullable=False),
        sa.Column("expiresAt", STAMP, nullable=False),
        sa.CheckConstraint("\"service\" <> ''", name=op.f(f"{LEASE}_service_check")),
        sa.PrimaryKeyConstraint("id", name=op.f(f"{LEASE}_pkey")),
    )
    op.create_index("SourceLease_service_expiresAt_idx", LEASE, ["service", "expiresAt"])
