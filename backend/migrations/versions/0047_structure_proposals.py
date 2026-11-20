from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0047_structure_proposals"
down_revision: str | Sequence[str] | None = "0046_contrast_preference"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLE = "StructureProposal"
STAMP = sa.DateTime(timezone=True)
KINDS = (
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
STATUSES = ("PENDING", "APPROVED", "REJECTED", "REFUSED")
ORIGINS = ("CONTRIBUTION", "AGENT")
REVOKE_PUBLIC_ROLES = """
DO $do$
DECLARE grantee text;
BEGIN
    FOREACH grantee IN ARRAY ARRAY['anon', 'authenticated'] LOOP
        IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = grantee) THEN
            EXECUTE format('REVOKE ALL ON "StructureProposal" FROM %I', grantee);
        END IF;
    END LOOP;
END
$do$
"""


def upgrade() -> None:
    op.create_table(
        "StructureProposal",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("proposerId", sa.UUID(), nullable=True),
        sa.Column("craftId", sa.UUID(), nullable=False),
        sa.Column("kind", sa.String(length=16), nullable=False),
        sa.Column("item", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("field", sa.String(length=16), nullable=True),
        sa.Column("statement", sa.Text(), nullable=True),
        sa.Column("sources", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("checks", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("taskKey", sa.String(length=240), nullable=True),
        sa.Column("note", sa.String(length=500), nullable=True),
        sa.Column("origin", sa.String(length=16), nullable=False),
        sa.Column("status", sa.String(length=16), server_default="PENDING", nullable=False),
        sa.Column("reviewedById", sa.UUID(), nullable=True),
        sa.Column("reviewedAt", STAMP, nullable=True),
        sa.Column("reviewNote", sa.String(length=500), nullable=True),
        sa.Column("claimId", sa.UUID(), nullable=True),
        sa.Column("createdAt", STAMP, server_default=sa.text("now()"), nullable=False),
        sa.Column("updatedAt", STAMP, server_default=sa.text("now()"), nullable=False),
        *_rules(),
    )
    op.create_index(op.f(f"{TABLE}_status_createdAt_idx"), TABLE, ["status", "createdAt"])
    for column in ("proposerId", "craftId", "reviewedById", "claimId"):
        op.create_index(op.f(f"{TABLE}_{column}_idx"), TABLE, [column])
    op.execute(f'ALTER TABLE "{TABLE}" ENABLE ROW LEVEL SECURITY')
    op.execute(REVOKE_PUBLIC_ROLES)


def downgrade() -> None:
    op.drop_table(TABLE)


def _listed(column: str, values: tuple[str, ...]) -> str:
    named = ", ".join(f"'{value}'" for value in values)
    return f'"{column}" IN ({named})'


def _check(name: str, condition: str) -> sa.CheckConstraint:
    return sa.CheckConstraint(condition, name=op.f(f"{TABLE}_{name}_check"))


def _fk(column: str, target: str, ondelete: str) -> sa.ForeignKeyConstraint:
    return sa.ForeignKeyConstraint(
        [column], [f"{target}.id"], name=op.f(f"{TABLE}_{column}_fkey"), ondelete=ondelete
    )


def _rules() -> tuple[sa.Constraint, ...]:
    return (
        _check("kind", _listed("kind", KINDS)),
        _check("status", _listed("status", STATUSES)),
        _check("origin", _listed("origin", ORIGINS)),
        _check("item", "jsonb_typeof(\"item\") = 'object'"),
        _check("sources", "jsonb_typeof(\"sources\") = 'array'"),
        _check("checks", "jsonb_typeof(\"checks\") = 'array'"),
        _check("reviewed", "\"status\" IN ('PENDING', 'REFUSED') OR \"reviewedAt\" IS NOT NULL"),
        _fk("proposerId", "User", "SET NULL"),
        _fk("craftId", "Craft", "CASCADE"),
        _fk("reviewedById", "User", "SET NULL"),
        _fk("claimId", "Claim", "SET NULL"),
        sa.PrimaryKeyConstraint("id", name=op.f(f"{TABLE}_pkey")),
    )
