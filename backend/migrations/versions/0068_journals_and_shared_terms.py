from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0068_journals_and_shared_terms"
down_revision: str | Sequence[str] | None = "0065_media_kind_and_source_paces"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

CONTAINER_TITLE_CHARS = 300
JOURNAL_AS_PUBLISHER_ADAPTERS = ("europe_pmc", "semantic_scholar")
CONTAINER_TITLE_RULE = '"containerTitle" IS NULL OR "containerTitle" <> \'\''
SHARED = "SharedTermCraft"
IDS = postgresql.ARRAY(sa.UUID())
REVOKE_PUBLIC_ROLES = """
DO $do$
DECLARE grantee text;
BEGIN
    FOREACH grantee IN ARRAY ARRAY['anon', 'authenticated'] LOOP
        IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = grantee) THEN
            EXECUTE format('REVOKE ALL ON "SharedTermCraft" FROM %I', grantee);
        END IF;
    END LOOP;
END
$do$
"""


def _journals_backfill() -> str:
    prefixes = " OR ".join(
        f"\"externalIds\" ->> 'evidenceId' LIKE '{adapter}:%'" for adapter in JOURNAL_AS_PUBLISHER_ADAPTERS
    )
    return (
        'UPDATE "Source" SET "containerTitle" = "publisher" '
        f'WHERE "publisher" IS NOT NULL AND "publisher" <> \'\' AND ({prefixes})'
    )


def _source_journals() -> None:
    op.add_column(
        "Source", sa.Column("containerTitle", sa.String(length=CONTAINER_TITLE_CHARS), nullable=True)
    )
    op.create_check_constraint(op.f("Source_containerTitle_check"), "Source", CONTAINER_TITLE_RULE)
    op.execute(_journals_backfill())


def _shared_terms() -> None:
    op.create_table(
        "SharedTermCraft",
        sa.Column("termId", sa.UUID(), nullable=False),
        sa.Column("craftId", sa.UUID(), nullable=False),
        sa.Column("conceptIds", IDS, nullable=False),
        sa.Column("claimIds", IDS, nullable=False),
        sa.Column("refreshedAt", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint('cardinality("conceptIds") > 0', name=op.f(f"{SHARED}_concepts_check")),
        sa.CheckConstraint('cardinality("claimIds") > 0', name=op.f(f"{SHARED}_claims_check")),
        sa.ForeignKeyConstraint(
            ["termId"], ["Term.id"], name=op.f(f"{SHARED}_termId_fkey"), ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["craftId"], ["Craft.id"], name=op.f(f"{SHARED}_craftId_fkey"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("termId", "craftId", name=op.f(f"{SHARED}_pkey")),
    )
    op.create_index(op.f(f"{SHARED}_craftId_idx"), SHARED, ["craftId"])
    op.execute(f'ALTER TABLE "{SHARED}" ENABLE ROW LEVEL SECURITY')
    op.execute(REVOKE_PUBLIC_ROLES)


def upgrade() -> None:
    _source_journals()
    _shared_terms()


def downgrade() -> None:
    op.drop_table(SHARED)
    op.drop_constraint(op.f("Source_containerTitle_check"), "Source", type_="check")
    op.drop_column("Source", "containerTitle")
