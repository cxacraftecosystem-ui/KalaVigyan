from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0099_craft_group_names"
down_revision: str | Sequence[str] | None = "0098_term_zoom_levels"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

NAMES = "CraftGroupName"
PROPOSALS = "StructureProposal"
STAMP = sa.DateTime(timezone=True)
CODE_CHARS = 16
NAME_CHARS = 300
LOCATOR_CHARS = 300
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
    "ALTERNATIVE",
)
KINDS = (*KINDS_BEFORE, "GROUP_NAME")
GROUP_KINDS = ("COMMUNITY", "PERSON")
ORIGINS = ("DOSSIER", "PROPOSAL")
REVOKE_PUBLIC_ROLES = """
DO $do$
DECLARE grantee text;
BEGIN
    FOREACH grantee IN ARRAY ARRAY['anon', 'authenticated'] LOOP
        IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = grantee) THEN
            EXECUTE format('REVOKE ALL ON "CraftGroupName" FROM %I', grantee);
        END IF;
    END LOOP;
END
$do$
"""


def upgrade() -> None:
    _check_kinds(KINDS)
    op.create_table(
        "CraftGroupName",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("craftId", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(length=NAME_CHARS), nullable=False),
        sa.Column("nameKey", sa.String(length=NAME_CHARS), nullable=False),
        sa.Column("kind", sa.String(length=CODE_CHARS), nullable=False),
        sa.Column("origin", sa.String(length=CODE_CHARS), nullable=False),
        sa.Column("sourceTitle", sa.Text(), nullable=False),
        sa.Column("sourceUrl", sa.Text(), nullable=False),
        sa.Column("quote", sa.Text(), nullable=False),
        sa.Column("locator", sa.String(length=LOCATOR_CHARS), nullable=True),
        sa.Column("proposalId", sa.UUID(), nullable=True),
        sa.Column("createdAt", STAMP, server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(_listed("kind", GROUP_KINDS), name=op.f(f"{NAMES}_kind_check")),
        sa.CheckConstraint(_listed("origin", ORIGINS), name=op.f(f"{NAMES}_origin_check")),
        sa.ForeignKeyConstraint(
            ["craftId"], ["Craft.id"], name=op.f(f"{NAMES}_craftId_fkey"), ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["proposalId"], [f"{PROPOSALS}.id"], name=op.f(f"{NAMES}_proposalId_fkey"), ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f(f"{NAMES}_pkey")),
        sa.UniqueConstraint("craftId", "nameKey", name=op.f(f"{NAMES}_craftId_nameKey_key")),
    )
    op.create_index(op.f(f"{NAMES}_proposalId_idx"), NAMES, ["proposalId"])
    op.execute(f'ALTER TABLE "{NAMES}" ENABLE ROW LEVEL SECURITY')
    op.execute(REVOKE_PUBLIC_ROLES)


def downgrade() -> None:
    op.drop_table(NAMES)
    op.execute(f'DELETE FROM "{PROPOSALS}" WHERE "kind" = \'GROUP_NAME\'')
    _check_kinds(KINDS_BEFORE)


def _check_kinds(kinds: Sequence[str]) -> None:
    name = op.f(f"{PROPOSALS}_kind_check")
    op.drop_constraint(name, PROPOSALS, type_="check")
    op.create_check_constraint(name, PROPOSALS, _listed("kind", kinds))


def _listed(column: str, values: Sequence[str]) -> str:
    named = ", ".join(f"'{value}'" for value in values)
    return f'"{column}" IN ({named})'
