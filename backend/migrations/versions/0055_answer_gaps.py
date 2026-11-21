from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql

revision: str = "0055_answer_gaps"
down_revision: str | Sequence[str] | None = "0053_shared_allowances"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

GAPS = "AnswerGap"
VERDICTS = "AnswerVerdict"
STAMP = sa.DateTime(timezone=True)
TEXTS = postgresql.ARRAY(sa.Text())
NO_TEXTS = sa.text("ARRAY[]::text[]")
ANSWER_VERDICTS = ("ANSWERED", "THIN", "UNANSWERED")
GAP_LACKS = ("NO_CITED_EVIDENCE", "MISSING_FIELD", "FEW_SENTENCES", "LOW_RETRIEVAL", "FAILED_QUOTE")
GAP_STATES = ("OPEN", "ANSWERED", "LAPSED")
GAP_PRIORITIES = ("HIGH", "MEDIUM", "LOW")
DISCIPLINES = (
    "OVERVIEW",
    "PROCESS",
    "CHEMISTRY",
    "PHYSICS",
    "MATERIALS",
    "GEOGRAPHY",
    "GEOLOGY",
    "CLIMATE",
    "ECOLOGY",
    "BOTANY",
    "HISTORY",
    "ECONOMICS",
    "DESIGN",
    "HEALTH",
    "SOCIETY",
    "POLICY",
)
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
    _create_gaps()
    _create_verdicts()
    for table in (GAPS, VERDICTS):
        op.execute(f'ALTER TABLE "{table}" ENABLE ROW LEVEL SECURITY')
        op.execute(REVOKE_PUBLIC_ROLES.replace("{table}", table))


def downgrade() -> None:
    op.drop_table(VERDICTS)
    op.drop_table(GAPS)


def _create_gaps() -> None:
    op.create_table(
        "AnswerGap",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("craftId", sa.UUID(), nullable=False),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("language", sa.String(length=16), server_default="en", nullable=False),
        sa.Column("fields", TEXTS, server_default=NO_TEXTS, nullable=False),
        sa.Column("lacks", TEXTS, server_default=NO_TEXTS, nullable=False),
        sa.Column("askers", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("firstAskedAt", STAMP, nullable=False),
        sa.Column("lastAskedAt", STAMP, nullable=False),
        sa.Column("priority", sa.String(length=16), server_default="LOW", nullable=False),
        sa.Column("state", sa.String(length=16), server_default="OPEN", nullable=False),
        sa.Column("closedAt", STAMP, nullable=True),
        sa.Column("embedding", Vector(1536), nullable=True),
        sa.Column("embeddingModel", sa.String(length=120), nullable=True),
        sa.Column("createdAt", STAMP, server_default=sa.text("now()"), nullable=False),
        sa.Column("updatedAt", STAMP, server_default=sa.text("now()"), nullable=False),
        *_checks(GAPS, _gap_checks()),
        sa.ForeignKeyConstraint(
            ["craftId"], ["Craft.id"], name=op.f(f"{GAPS}_craftId_fkey"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f(f"{GAPS}_pkey")),
    )
    op.create_index(op.f(f"{GAPS}_craftId_state_idx"), GAPS, ["craftId", "state"])


def _create_verdicts() -> None:
    op.create_table(
        "AnswerVerdict",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("answerId", sa.UUID(), nullable=False),
        sa.Column("craftId", sa.UUID(), nullable=True),
        sa.Column("verdict", sa.String(length=16), nullable=False),
        sa.Column("fields", TEXTS, server_default=NO_TEXTS, nullable=False),
        sa.Column("lacking", TEXTS, server_default=NO_TEXTS, nullable=False),
        sa.Column("lacks", TEXTS, server_default=NO_TEXTS, nullable=False),
        sa.Column("sentences", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("gapId", sa.UUID(), nullable=True),
        sa.Column("embedding", Vector(1536), nullable=True),
        sa.Column("embeddingModel", sa.String(length=120), nullable=True),
        sa.Column("createdAt", STAMP, server_default=sa.text("now()"), nullable=False),
        *_checks(VERDICTS, _verdict_checks()),
        sa.ForeignKeyConstraint(
            ["answerId"], ["Answer.id"], name=op.f(f"{VERDICTS}_answerId_fkey"), ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["craftId"], ["Craft.id"], name=op.f(f"{VERDICTS}_craftId_fkey"), ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["gapId"], ["AnswerGap.id"], name=op.f(f"{VERDICTS}_gapId_fkey"), ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f(f"{VERDICTS}_pkey")),
        sa.UniqueConstraint("answerId", name=op.f(f"{VERDICTS}_answerId_key")),
    )
    op.create_index(
        op.f(f"{VERDICTS}_craftId_verdict_createdAt_idx"), VERDICTS, ["craftId", "verdict", "createdAt"]
    )
    op.create_index(op.f(f"{VERDICTS}_gapId_idx"), VERDICTS, ["gapId"])


def _gap_checks() -> dict[str, str]:
    return {
        "state": f'"state" IN ({_listed(GAP_STATES)})',
        "priority": f'"priority" IN ({_listed(GAP_PRIORITIES)})',
        "fields": f'"fields" <@ ARRAY[{_listed(DISCIPLINES)}]::text[]',
        "lacks": f'"lacks" <@ ARRAY[{_listed(GAP_LACKS)}]::text[]',
        "askers": '"askers" >= 0',
        "closed": '("state" = \'OPEN\') = ("closedAt" IS NULL)',
    }


def _verdict_checks() -> dict[str, str]:
    return {
        "verdict": f'"verdict" IN ({_listed(ANSWER_VERDICTS)})',
        "fields": f'"fields" <@ ARRAY[{_listed(DISCIPLINES)}]::text[]',
        "lacking": f'"lacking" <@ ARRAY[{_listed(DISCIPLINES)}]::text[]',
        "lacks": f'"lacks" <@ ARRAY[{_listed(GAP_LACKS)}]::text[]',
        "sentences": '"sentences" >= 0',
        "judged": '("verdict" = \'ANSWERED\') = (cardinality("lacks") = 0)',
    }


def _checks(table: str, checks: dict[str, str]) -> list[sa.CheckConstraint]:
    return [sa.CheckConstraint(rule, name=op.f(f"{table}_{name}_check")) for name, rule in checks.items()]


def _listed(values: Sequence[str]) -> str:
    return ", ".join(f"'{value}'" for value in values)
