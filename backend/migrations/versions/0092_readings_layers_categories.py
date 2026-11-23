from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0092_readings_layers_categories"
down_revision: str | Sequence[str] | None = "0090_answer_leftovers"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

READINGS = "ConditionReading"
PROPOSALS = "StructureProposal"
LAYERS = "MapLayerProposal"
STAMP = sa.DateTime(timezone=True)
NOTE_CHARS = 500
CODE_CHARS = 16
KINDS_BEFORE = (
    "STAGE_AFTER",
    "STAGE_WHY",
    "NATIVE_NAME",
    "REACTION",
    "BOTANICAL_NAME",
    "GLOSSARY_TERM",
    "CONFLICT",
    "OPEN_QUESTION",
    "GI_RECORD",
)
KINDS = (*KINDS_BEFORE, "ALTERNATIVE")
LAYER_STATUSES = ("PENDING", "APPROVED", "REJECTED")
REVOKE_PUBLIC_ROLES = """
DO $do$
DECLARE grantee text;
BEGIN
    FOREACH grantee IN ARRAY ARRAY['anon', 'authenticated'] LOOP
        IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = grantee) THEN
            EXECUTE format('REVOKE ALL ON "MapLayerProposal" FROM %I', grantee);
        END IF;
    END LOOP;
END
$do$
"""


def upgrade() -> None:
    _review_readings()
    _category_subjects()
    _check_kinds(KINDS)
    _layer_proposals()


def downgrade() -> None:
    op.drop_table(LAYERS)
    op.execute(f'DELETE FROM "{PROPOSALS}" WHERE "kind" = \'ALTERNATIVE\' OR "craftId" IS NULL')
    _check_kinds(KINDS_BEFORE)
    op.drop_constraint(op.f(f"{PROPOSALS}_subject_check"), PROPOSALS, type_="check")
    op.drop_index(op.f(f"{PROPOSALS}_categoryId_idx"), table_name=PROPOSALS)
    op.drop_column(PROPOSALS, "categoryId")
    op.alter_column(PROPOSALS, "craftId", existing_type=sa.UUID(), nullable=False)
    op.drop_index(op.f(f"{READINGS}_reviewedById_idx"), table_name=READINGS)
    for name in ("review_status", "reviewed"):
        op.drop_constraint(op.f(f"{READINGS}_{name}_check"), READINGS, type_="check")
    for column in ("reviewNote", "reviewedAt", "reviewedById", "reviewStatus"):
        op.drop_column(READINGS, column)


def _review_readings() -> None:
    op.add_column("ConditionReading", sa.Column("reviewStatus", sa.String(length=CODE_CHARS), nullable=True))
    op.add_column("ConditionReading", sa.Column("reviewedById", sa.UUID(), nullable=True))
    op.add_column("ConditionReading", sa.Column("reviewedAt", STAMP, nullable=True))
    op.add_column("ConditionReading", sa.Column("reviewNote", sa.String(length=NOTE_CHARS), nullable=True))
    op.create_foreign_key(
        op.f(f"{READINGS}_reviewedById_fkey"), READINGS, "User", ["reviewedById"], ["id"], ondelete="SET NULL"
    )
    op.create_check_constraint(
        op.f(f"{READINGS}_review_status_check"),
        READINGS,
        "\"reviewStatus\" IS NULL OR \"reviewStatus\" IN ('APPROVED', 'REJECTED')",
    )
    op.create_check_constraint(
        op.f(f"{READINGS}_reviewed_check"), READINGS, '"reviewStatus" IS NULL OR "reviewedAt" IS NOT NULL'
    )
    op.create_index(op.f(f"{READINGS}_reviewedById_idx"), READINGS, ["reviewedById"])


def _category_subjects() -> None:
    op.alter_column(PROPOSALS, "craftId", existing_type=sa.UUID(), nullable=True)
    op.add_column("StructureProposal", sa.Column("categoryId", sa.UUID(), nullable=True))
    op.create_foreign_key(
        op.f(f"{PROPOSALS}_categoryId_fkey"),
        PROPOSALS,
        "CraftCategory",
        ["categoryId"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index(op.f(f"{PROPOSALS}_categoryId_idx"), PROPOSALS, ["categoryId"])
    op.create_check_constraint(
        op.f(f"{PROPOSALS}_subject_check"), PROPOSALS, 'num_nonnulls("craftId", "categoryId") = 1'
    )


def _check_kinds(kinds: Sequence[str]) -> None:
    name = op.f(f"{PROPOSALS}_kind_check")
    op.drop_constraint(name, PROPOSALS, type_="check")
    op.create_check_constraint(name, PROPOSALS, _listed("kind", kinds))


def _layer_proposals() -> None:
    op.create_table(
        "MapLayerProposal",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("datasetId", sa.UUID(), nullable=False),
        sa.Column("proposerId", sa.UUID(), nullable=True),
        sa.Column("plan", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("layer", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("featureCount", sa.Integer(), nullable=False),
        sa.Column("byteSize", sa.Integer(), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=CODE_CHARS), server_default="PENDING", nullable=False),
        sa.Column("reviewedById", sa.UUID(), nullable=True),
        sa.Column("reviewedAt", STAMP, nullable=True),
        sa.Column("reviewNote", sa.String(length=NOTE_CHARS), nullable=True),
        sa.Column("createdAt", STAMP, server_default=sa.text("now()"), nullable=False),
        sa.Column("updatedAt", STAMP, server_default=sa.text("now()"), nullable=False),
        *_layer_rules(),
    )
    op.create_index(op.f(f"{LAYERS}_status_createdAt_idx"), LAYERS, ["status", "createdAt"])
    for column in ("proposerId", "reviewedById"):
        op.create_index(op.f(f"{LAYERS}_{column}_idx"), LAYERS, [column])
    op.execute(f'ALTER TABLE "{LAYERS}" ENABLE ROW LEVEL SECURITY')
    op.execute(REVOKE_PUBLIC_ROLES)


def _layer_rules() -> tuple[sa.Constraint, ...]:
    return (
        _layer_check("sha256", "\"sha256\" ~ '^[0-9a-f]{64}$'"),
        _layer_check("status", _listed("status", LAYER_STATUSES)),
        _layer_check("plan", "jsonb_typeof(\"plan\") = 'object'"),
        _layer_check("layer", "jsonb_typeof(\"layer\") = 'object'"),
        _layer_check("size", '"featureCount" >= 1 AND "byteSize" >= 1'),
        _layer_check("reviewed", '"status" = \'PENDING\' OR "reviewedAt" IS NOT NULL'),
        _layer_fk("datasetId", "EnvDataset", "CASCADE"),
        _layer_fk("proposerId", "User", "SET NULL"),
        _layer_fk("reviewedById", "User", "SET NULL"),
        sa.PrimaryKeyConstraint("id", name=op.f(f"{LAYERS}_pkey")),
        sa.UniqueConstraint("datasetId", name=op.f(f"{LAYERS}_datasetId_key")),
    )


def _listed(column: str, values: Sequence[str]) -> str:
    named = ", ".join(f"'{value}'" for value in values)
    return f'"{column}" IN ({named})'


def _layer_check(name: str, condition: str) -> sa.CheckConstraint:
    return sa.CheckConstraint(condition, name=op.f(f"{LAYERS}_{name}_check"))


def _layer_fk(column: str, target: str, ondelete: str) -> sa.ForeignKeyConstraint:
    return sa.ForeignKeyConstraint(
        [column], [f"{target}.id"], name=op.f(f"{LAYERS}_{column}_fkey"), ondelete=ondelete
    )
