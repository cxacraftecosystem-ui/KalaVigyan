from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0054_field_photo_reviews"
down_revision: str | Sequence[str] | None = "0052_drafts_and_supplied_sources"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

STAMP = sa.DateTime(timezone=True)
NEW_TABLES = ("FieldPhotoReview", "FieldPhotoScreen")
SHA256 = "~ '^[0-9a-f]{64}$'"
DECISIONS = "('SHOW', 'HIDE', 'CROP')"
REASONS = "('IDENTITY_DOCUMENT', 'NOT_AGREED', 'PRIVATE_PLACE', 'POOR_QUALITY', 'NOT_THIS_CRAFT', 'OTHER')"
CROP_COLUMNS = '"cropLeft", "cropTop", "cropWidth", "cropHeight", "cropKey", "cropSha256", "cropMime"'

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
    _reviews()
    _screens()
    for table in NEW_TABLES:
        op.execute(f'ALTER TABLE "{table}" ENABLE ROW LEVEL SECURITY')
        op.execute(REVOKE_PUBLIC_ROLES.format(table=table))


def downgrade() -> None:
    for table in reversed(NEW_TABLES):
        op.drop_table(table)


def _reviews() -> None:
    table = "FieldPhotoReview"
    op.create_table(
        "FieldPhotoReview",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("imageId", sa.UUID(), nullable=True),
        sa.Column("imageSha256", sa.String(length=64), nullable=False),
        sa.Column("decision", sa.String(length=8), nullable=False),
        sa.Column("reason", sa.String(length=24), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column(
            "clearedFlags",
            postgresql.ARRAY(sa.String(length=32)),
            server_default=sa.text("ARRAY[]::varchar[]"),
            nullable=False,
        ),
        sa.Column("cropLeft", sa.Integer(), nullable=True),
        sa.Column("cropTop", sa.Integer(), nullable=True),
        sa.Column("cropWidth", sa.Integer(), nullable=True),
        sa.Column("cropHeight", sa.Integer(), nullable=True),
        sa.Column("cropKey", sa.Text(), nullable=True),
        sa.Column("cropSha256", sa.String(length=64), nullable=True),
        sa.Column("cropMime", sa.String(length=16), nullable=True),
        sa.Column("deciderId", sa.UUID(), nullable=True),
        sa.Column("deciderRole", sa.String(length=20), nullable=False),
        sa.Column("decidedAt", STAMP, server_default=sa.text("now()"), nullable=False),
        *_review_rules(table),
    )
    op.create_index(op.f(f"{table}_deciderId_idx"), table, ["deciderId"])


def _review_rules(table: str) -> tuple[sa.Constraint, ...]:
    return (
        _check(table, "decision", f'"decision" IN {DECISIONS}'),
        _check(table, "reason", f'"reason" IS NULL OR "reason" IN {REASONS}'),
        _check(table, "reasoned", '("decision" = \'HIDE\') = ("reason" IS NOT NULL)'),
        _check(table, "noted", '"reason" IS DISTINCT FROM \'OTHER\' OR "note" IS NOT NULL'),
        _check(table, "cropped", '("decision" = \'CROP\') = ("cropKey" IS NOT NULL)'),
        _check(table, "crop", f"num_nonnulls({CROP_COLUMNS}) IN (0, 7)"),
        _check(table, "imageSha256", f'"imageSha256" {SHA256}'),
        sa.UniqueConstraint("imageId", name=op.f(f"{table}_imageId_key")),
        _fk(table, "imageId", "FieldImage", "SET NULL"),
        _fk(table, "deciderId", "User", "SET NULL"),
        sa.PrimaryKeyConstraint("id", name=op.f(f"{table}_pkey")),
    )


def _screens() -> None:
    table = "FieldPhotoScreen"
    op.create_table(
        "FieldPhotoScreen",
        sa.Column("imageId", sa.UUID(), nullable=False),
        sa.Column("imageSha256", sa.String(length=64), nullable=False),
        sa.Column("fingerprint", sa.BigInteger(), nullable=True),
        sa.Column("nearestAssetId", sa.UUID(), nullable=True),
        sa.Column("nearestImageId", sa.UUID(), nullable=True),
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
        sa.Column("screenedAt", STAMP, server_default=sa.text("now()"), nullable=False),
        *_screen_rules(table),
    )
    for column in ("nearestAssetId", "nearestImageId", "usageEventId"):
        op.create_index(op.f(f"{table}_{column}_idx"), table, [column])


def _screen_rules(table: str) -> tuple[sa.Constraint, ...]:
    return (
        _check(table, "verdict", "\"verdict\" IN ('CLEAR', 'FLAGGED', 'UNSCREENED')"),
        _check(table, "cost", '"costUsd" >= 0'),
        _check(table, "reasoned", '"verdict" = \'CLEAR\' OR cardinality("reasons") > 0'),
        _check(table, "imageSha256", f'"imageSha256" {SHA256}'),
        _fk(table, "imageId", "FieldImage", "CASCADE"),
        _fk(table, "nearestAssetId", "MediaAsset", "SET NULL"),
        _fk(table, "nearestImageId", "FieldImage", "SET NULL"),
        _fk(table, "usageEventId", "UsageEvent", "SET NULL"),
        sa.PrimaryKeyConstraint("imageId", name=op.f(f"{table}_pkey")),
    )


def _check(table: str, name: str, condition: str) -> sa.CheckConstraint:
    return sa.CheckConstraint(condition, name=op.f(f"{table}_{name}_check"))


def _fk(table: str, column: str, target: str, ondelete: str) -> sa.ForeignKeyConstraint:
    return sa.ForeignKeyConstraint(
        [column], [f"{target}.id"], name=op.f(f"{table}_{column}_fkey"), ondelete=ondelete
    )
