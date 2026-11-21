from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0059_page_translations"
down_revision: str | Sequence[str] | None = "0058_stored_documents"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TRANSLATION = "PageTranslation"
TEXT_UNIT = "PageTextUnit"
READER = "TranslationReader"
TABLES = (TRANSLATION, TEXT_UNIT, READER)
STAMP = sa.DateTime(timezone=True)
STATUSES = ("APPROVED", "IN_REVIEW", "DRAFT", "REJECTED", "SUPERSEDED")
ORIGINS = ("RESEARCH", "CONTRIBUTION", "AGENT")
HASH_RULE = "\"sourceHash\" ~ '^[0-9a-f]{64}$'"
NOT_ENGLISH = "\"language\" <> 'en'"
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
    _translations()
    _text_units()
    _readers()
    for table in TABLES:
        op.execute(f'ALTER TABLE "{table}" ENABLE ROW LEVEL SECURITY')
        op.execute(REVOKE_PUBLIC_ROLES.replace("{table}", table))


def downgrade() -> None:
    for table in reversed(TABLES):
        op.drop_table(table)


def _translations() -> None:
    op.create_table(
        "PageTranslation",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("batchId", sa.UUID(), nullable=False),
        sa.Column("subjectKind", sa.String(length=20), nullable=False),
        sa.Column("subjectSlug", sa.String(length=200), nullable=False),
        sa.Column("language", sa.String(length=16), nullable=False),
        sa.Column("unitKey", sa.String(length=200), nullable=False),
        sa.Column("sourceHash", sa.String(length=64), nullable=False),
        sa.Column("english", sa.Text(), nullable=False),
        sa.Column("texts", postgresql.JSONB(), server_default=sa.text("'[]'::jsonb"), nullable=False),
        sa.Column("checks", postgresql.JSONB(), server_default=sa.text("'[]'::jsonb"), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("placedBy", sa.String(length=16), nullable=True),
        sa.Column("origin", sa.String(length=16), nullable=False),
        sa.Column("proposerId", sa.UUID(), nullable=True),
        sa.Column("taskKey", sa.String(length=240), nullable=True),
        sa.Column("note", sa.String(length=500), nullable=True),
        sa.Column("reviewedById", sa.UUID(), nullable=True),
        sa.Column("reviewedAt", STAMP, nullable=True),
        sa.Column("reviewNote", sa.String(length=500), nullable=True),
        sa.Column("createdAt", STAMP, server_default=sa.text("now()"), nullable=False),
        *_translation_rules(),
    )
    _translation_indexes()


def _translation_rules() -> list[sa.Constraint]:
    rules = {
        "status": f'"status" IN ({_listed(STATUSES)})',
        "origin": f'"origin" IN ({_listed(ORIGINS)})',
        "sourceHash": HASH_RULE,
        "language": NOT_ENGLISH,
    }
    return [
        *_checks(TRANSLATION, rules),
        sa.ForeignKeyConstraint(
            ["proposerId"], ["User.id"], name=op.f(f"{TRANSLATION}_proposerId_fkey"), ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["reviewedById"], ["User.id"], name=op.f(f"{TRANSLATION}_reviewedById_fkey"), ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f(f"{TRANSLATION}_pkey")),
    ]


def _translation_indexes() -> None:
    op.create_index(
        op.f(f"{TRANSLATION}_subjectKind_subjectSlug_language_status_idx"),
        TRANSLATION,
        ["subjectKind", "subjectSlug", "language", "status"],
    )
    op.create_index(
        op.f(f"{TRANSLATION}_language_status_createdAt_idx"), TRANSLATION, ["language", "status", "createdAt"]
    )
    op.create_index(op.f(f"{TRANSLATION}_proposerId_idx"), TRANSLATION, ["proposerId"])


def _text_units() -> None:
    op.create_table(
        "PageTextUnit",
        sa.Column("subjectKind", sa.String(length=20), nullable=False),
        sa.Column("subjectSlug", sa.String(length=200), nullable=False),
        sa.Column("unitKey", sa.String(length=200), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("sourceHash", sa.String(length=64), nullable=False),
        sa.Column("chapter", sa.String(length=80), nullable=False),
        sa.Column("tag", sa.String(length=16), nullable=False),
        sa.Column("leaves", postgresql.JSONB(), server_default=sa.text("'[]'::jsonb"), nullable=False),
        sa.Column("documentTag", sa.String(length=160), nullable=False),
        sa.Column("refreshedAt", STAMP, server_default=sa.text("now()"), nullable=False),
        *_checks(TEXT_UNIT, {"sourceHash": HASH_RULE, "position": '"position" >= 0'}),
        sa.PrimaryKeyConstraint("subjectKind", "subjectSlug", "unitKey", name=op.f(f"{TEXT_UNIT}_pkey")),
    )
    op.create_index(
        op.f(f"{TEXT_UNIT}_subjectKind_subjectSlug_sourceHash_idx"),
        TEXT_UNIT,
        ["subjectKind", "subjectSlug", "sourceHash"],
    )


def _readers() -> None:
    op.create_table(
        "TranslationReader",
        sa.Column("userId", sa.UUID(), nullable=False),
        sa.Column("language", sa.String(length=16), nullable=False),
        sa.Column("createdAt", STAMP, server_default=sa.text("now()"), nullable=False),
        *_checks(READER, {"language": NOT_ENGLISH}),
        sa.ForeignKeyConstraint(
            ["userId"], ["User.id"], name=op.f(f"{READER}_userId_fkey"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("userId", "language", name=op.f(f"{READER}_pkey")),
    )


def _checks(table: str, rules: dict[str, str]) -> list[sa.CheckConstraint]:
    return [sa.CheckConstraint(rule, name=op.f(f"{table}_{name}_check")) for name, rule in rules.items()]


def _listed(values: Sequence[str]) -> str:
    return ", ".join(f"'{value}'" for value in values)
