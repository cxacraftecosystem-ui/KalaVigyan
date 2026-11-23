from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0077_state_and_reach_districts"
down_revision: str | Sequence[str] | None = "0078_media_page_key"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

STATE_VALUES = "StateEnvValue"
REACH_DISTRICTS = "RiverReachDistrict"
RUN_PERIOD_REPAIR = """
UPDATE "EnvDataset" AS d SET "period" = loaded.period
FROM (
    SELECT v."datasetId" AS dataset_id, max(v."depthOrPeriod") AS period
    FROM "DistrictEnvValue" AS v
    WHERE v."stat" = 'TREND_PER_DECADE'
    GROUP BY v."datasetId"
) AS loaded
WHERE loaded.dataset_id = d."id"
  AND d."code" IN ('CHIRPS_3_0', 'GHCN_CAMS_T2M')
  AND d."period" LIKE 'set per run%'
"""

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
    _create_state_values()
    _lock_down(STATE_VALUES)
    _create_reach_districts()
    _lock_down(REACH_DISTRICTS)
    op.execute(RUN_PERIOD_REPAIR)


def downgrade() -> None:
    op.drop_table("RiverReachDistrict")
    op.drop_table("StateEnvValue")


def _lock_down(table: str) -> None:
    op.execute(f'ALTER TABLE "{table}" ENABLE ROW LEVEL SECURITY')
    op.execute(REVOKE_PUBLIC_ROLES.replace("{table}", table))


def _create_state_values() -> None:
    op.create_table(
        "StateEnvValue",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("stateLgd", sa.Integer(), nullable=False),
        sa.Column("datasetId", sa.UUID(), nullable=False),
        sa.Column("variable", sa.String(length=120), nullable=False),
        sa.Column("depthOrPeriod", sa.String(length=80), nullable=False),
        sa.Column("stat", sa.String(length=40), nullable=False),
        sa.Column("unit", sa.String(length=40), nullable=True),
        sa.Column("valueText", sa.Text(), nullable=True),
        sa.Column("districts", sa.Integer(), nullable=False),
        sa.Column("weightedSum", sa.Float(), nullable=False),
        sa.Column("area", sa.Float(), nullable=False),
        sa.Column("total", sa.Float(), nullable=False),
        sa.Column("low", sa.Float(), nullable=False),
        sa.Column("high", sa.Float(), nullable=False),
        sa.Column("resolutions", postgresql.ARRAY(sa.Text()), nullable=False),
        sa.Column("methods", postgresql.ARRAY(sa.Text()), nullable=False),
        sa.Column("datasetDistricts", sa.Integer(), nullable=False),
        sa.Column("datasetArea", sa.Float(), nullable=False),
        sa.Column("createdAt", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            '"districts" >= 1 AND "datasetDistricts" >= "districts"',
            name=op.f("StateEnvValue_districts_check"),
        ),
        sa.ForeignKeyConstraint(
            ["stateLgd"], ["AdminState.lgd"], name=op.f("StateEnvValue_stateLgd_fkey"), ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["datasetId"], ["EnvDataset.id"], name=op.f("StateEnvValue_datasetId_fkey"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("StateEnvValue_pkey")),
    )
    op.create_index(op.f("StateEnvValue_stateLgd_idx"), "StateEnvValue", ["stateLgd"], unique=False)
    op.create_index(op.f("StateEnvValue_datasetId_idx"), "StateEnvValue", ["datasetId"], unique=False)


def _create_reach_districts() -> None:
    op.create_table(
        "RiverReachDistrict",
        sa.Column("hyrivId", sa.Integer(), autoincrement=False, nullable=False),
        sa.Column("districtLgd", sa.Integer(), autoincrement=False, nullable=False),
        sa.Column("entry", sa.Float(), nullable=False),
        sa.CheckConstraint('"entry" >= 0 AND "entry" <= 1', name=op.f("RiverReachDistrict_entry_check")),
        sa.ForeignKeyConstraint(
            ["hyrivId"],
            ["RiverReach.hyrivId"],
            name=op.f("RiverReachDistrict_hyrivId_fkey"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["districtLgd"],
            ["AdminDistrict.lgd"],
            name=op.f("RiverReachDistrict_districtLgd_fkey"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("hyrivId", "districtLgd", name=op.f("RiverReachDistrict_pkey")),
    )
    op.create_index(
        op.f("RiverReachDistrict_districtLgd_idx"), "RiverReachDistrict", ["districtLgd"], unique=False
    )
