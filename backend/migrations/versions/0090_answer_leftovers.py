from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0090_answer_leftovers"
down_revision: str | Sequence[str] | None = "0089_piece_embedding_stamps"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TERM_TEXT_CHARS = 120
STAGE_REVIEWS = "StageReview"
STATUS_CHARS = 16
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
STOPPED_BEFORE = """
UPDATE "Answer" SET "stoppedAt" = "updatedAt"
WHERE "payload" IS NULL
  AND "latencyMs" IS NULL
  AND "stoppedAt" IS NULL
  AND "createdAt" < now() - interval '1 hour'
"""


def upgrade() -> None:
    op.add_column("Answer", sa.Column("stoppedAt", sa.DateTime(timezone=True), nullable=True))
    op.add_column("Term", sa.Column("sentenceName", sa.String(TERM_TEXT_CHARS), nullable=True))
    op.add_column(
        "CraftGiRecord",
        sa.Column(
            "imitationClaimIds",
            postgresql.ARRAY(postgresql.UUID(as_uuid=True)),
            nullable=False,
            server_default=sa.text("ARRAY[]::uuid[]"),
        ),
    )
    op.execute(STOPPED_BEFORE)
    _stage_reviews()


def _stage_reviews() -> None:
    op.create_table(
        "StageReview",
        sa.Column("conceptId", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("status", sa.String(length=STATUS_CHARS), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("reviewerId", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("processStageId", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("createdAt", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "\"status\" IN ('PLACED', 'REJECTED')", name=op.f(f"{STAGE_REVIEWS}_status_check")
        ),
        sa.ForeignKeyConstraint(
            ["conceptId"], ["Concept.id"], name=op.f(f"{STAGE_REVIEWS}_conceptId_fkey"), ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["reviewerId"], ["User.id"], name=op.f(f"{STAGE_REVIEWS}_reviewerId_fkey"), ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["processStageId"],
            ["ProcessStage.id"],
            name=op.f(f"{STAGE_REVIEWS}_processStageId_fkey"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("conceptId", name=op.f(f"{STAGE_REVIEWS}_pkey")),
    )
    op.execute(f'ALTER TABLE "{STAGE_REVIEWS}" ENABLE ROW LEVEL SECURITY')
    op.execute(REVOKE_PUBLIC_ROLES.format(table=STAGE_REVIEWS))


def downgrade() -> None:
    op.drop_table("StageReview")
    op.drop_column("CraftGiRecord", "imitationClaimIds")
    op.drop_column("Term", "sentenceName")
    op.drop_column("Answer", "stoppedAt")
