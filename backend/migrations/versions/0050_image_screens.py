from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0050_image_screens"
down_revision: str | Sequence[str] | None = "0047_structure_proposals"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

STAMP = sa.DateTime(timezone=True)
CONTRIBUTION = "ImageContribution"
LINK = "UploadLink"
NEW_TABLES = ("PictureDeclaration", "ImageFingerprint", "ImageScreen")
ONE_TARGET = 'num_nonnulls("stageId", "materialId", "slot") <= 1'

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
    _declarations()
    _fingerprints()
    _screens()
    _contribution_targets()
    _link_targets()
    for table in NEW_TABLES:
        op.execute(f'ALTER TABLE "{table}" ENABLE ROW LEVEL SECURITY')
        op.execute(REVOKE_PUBLIC_ROLES.format(table=table))


def downgrade() -> None:
    for column in ("taskKey", "slot", "materialId"):
        op.drop_column(LINK, column)
    op.drop_constraint(op.f(f"{CONTRIBUTION}_one_target_check"), CONTRIBUTION, type_="check")
    for column in ("declarationId", "taskKey", "slot", "materialId"):
        op.drop_column(CONTRIBUTION, column)
    for table in reversed(NEW_TABLES):
        op.drop_table(table)


def _declarations() -> None:
    table = "PictureDeclaration"
    op.create_table(
        "PictureDeclaration",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("contributorId", sa.UUID(), nullable=True),
        sa.Column("craftId", sa.UUID(), nullable=False),
        sa.Column("channel", sa.String(length=8), nullable=False),
        sa.Column("origin", sa.String(length=16), nullable=False),
        sa.Column("generator", sa.String(length=120), nullable=True),
        sa.Column("termsVersion", sa.String(length=40), nullable=False),
        sa.Column("rightsConfirmedAt", STAMP, nullable=False),
        sa.Column("confirmation", sa.String(length=500), nullable=True),
        sa.Column("pictures", sa.Integer(), nullable=False),
        sa.Column("createdAt", STAMP, server_default=sa.text("now()"), nullable=False),
        _check(table, "channel", "\"channel\" IN ('WEB', 'LINK', 'SLOT', 'MCP')"),
        _check(table, "pictures", '"pictures" >= 1'),
        _check(table, "confirmed", '"channel" <> \'MCP\' OR "confirmation" IS NOT NULL'),
        _fk(table, "contributorId", "User", "SET NULL"),
        _fk(table, "craftId", "Craft", "CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f(f"{table}_pkey")),
    )
    for column in ("contributorId", "craftId"):
        op.create_index(op.f(f"{table}_{column}_idx"), table, [column])


def _fingerprints() -> None:
    table = "ImageFingerprint"
    op.create_table(
        "ImageFingerprint",
        sa.Column("assetId", sa.UUID(), nullable=False),
        sa.Column("fingerprint", sa.BigInteger(), nullable=False),
        sa.Column("createdAt", STAMP, server_default=sa.text("now()"), nullable=False),
        _fk(table, "assetId", "MediaAsset", "CASCADE"),
        sa.PrimaryKeyConstraint("assetId", name=op.f(f"{table}_pkey")),
    )


def _screens() -> None:
    table = "ImageScreen"
    op.create_table(
        "ImageScreen",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("contributionId", sa.UUID(), nullable=False),
        sa.Column("receivedMime", sa.String(length=64), nullable=False),
        sa.Column("receivedBytes", sa.Integer(), nullable=False),
        sa.Column("fingerprint", sa.BigInteger(), nullable=True),
        sa.Column("nearestAssetId", sa.UUID(), nullable=True),
        sa.Column("nearestDistance", sa.SmallInteger(), nullable=True),
        sa.Column("verdict", sa.String(length=16), nullable=False),
        sa.Column(
            "flags",
            postgresql.ARRAY(sa.String(length=32)),
            server_default=sa.text("ARRAY[]::varchar[]"),
            nullable=False,
        ),
        sa.Column(
            "reasons", postgresql.ARRAY(sa.Text()), server_default=sa.text("ARRAY[]::text[]"), nullable=False
        ),
        sa.Column("provider", sa.String(length=64), nullable=True),
        sa.Column("model", sa.String(length=120), nullable=True),
        sa.Column("usageEventId", sa.UUID(), nullable=True),
        sa.Column("inputTokens", sa.Integer(), nullable=True),
        sa.Column("outputTokens", sa.Integer(), nullable=True),
        sa.Column("costUsd", sa.Numeric(precision=12, scale=6), server_default=sa.text("0"), nullable=False),
        sa.Column("createdAt", STAMP, server_default=sa.text("now()"), nullable=False),
        *_screen_rules(table),
    )
    for column in ("nearestAssetId", "usageEventId"):
        op.create_index(op.f(f"{table}_{column}_idx"), table, [column])


def _screen_rules(table: str) -> tuple[sa.Constraint, ...]:
    return (
        _check(table, "verdict", "\"verdict\" IN ('CLEAR', 'FLAGGED', 'UNSCREENED')"),
        _check(table, "cost", '"costUsd" >= 0'),
        _check(table, "reasoned", '"verdict" = \'CLEAR\' OR cardinality("reasons") > 0'),
        sa.UniqueConstraint("contributionId", name=op.f(f"{table}_contributionId_key")),
        _fk(table, "contributionId", "ImageContribution", "CASCADE"),
        _fk(table, "nearestAssetId", "MediaAsset", "SET NULL"),
        _fk(table, "usageEventId", "UsageEvent", "SET NULL"),
        sa.PrimaryKeyConstraint("id", name=op.f(f"{table}_pkey")),
    )


def _contribution_targets() -> None:
    op.add_column("ImageContribution", sa.Column("materialId", sa.UUID(), nullable=True))
    op.add_column("ImageContribution", sa.Column("slot", sa.String(length=16), nullable=True))
    op.add_column("ImageContribution", sa.Column("taskKey", sa.String(length=240), nullable=True))
    op.add_column("ImageContribution", sa.Column("declarationId", sa.UUID(), nullable=True))
    _foreign(CONTRIBUTION, "materialId", "Material")
    _foreign(CONTRIBUTION, "declarationId", "PictureDeclaration")
    op.create_check_constraint(op.f(f"{CONTRIBUTION}_one_target_check"), CONTRIBUTION, ONE_TARGET)
    for column in ("declarationId", "taskKey"):
        op.create_index(op.f(f"{CONTRIBUTION}_{column}_idx"), CONTRIBUTION, [column])


def _link_targets() -> None:
    op.add_column("UploadLink", sa.Column("materialId", sa.UUID(), nullable=True))
    op.add_column("UploadLink", sa.Column("slot", sa.String(length=16), nullable=True))
    op.add_column("UploadLink", sa.Column("taskKey", sa.String(length=240), nullable=True))
    _foreign(LINK, "materialId", "Material")


def _foreign(table: str, column: str, target: str) -> None:
    op.create_foreign_key(
        op.f(f"{table}_{column}_fkey"), table, target, [column], ["id"], ondelete="SET NULL"
    )


def _check(table: str, name: str, condition: str) -> sa.CheckConstraint:
    return sa.CheckConstraint(condition, name=op.f(f"{table}_{name}_check"))


def _fk(table: str, column: str, target: str, ondelete: str) -> sa.ForeignKeyConstraint:
    return sa.ForeignKeyConstraint(
        [column], [f"{target}.id"], name=op.f(f"{table}_{column}_fkey"), ondelete=ondelete
    )
