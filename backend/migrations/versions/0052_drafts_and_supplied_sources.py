from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0052_drafts_and_supplied_sources"
down_revision: str | Sequence[str] | None = "0049_delivered_components"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

DRAFTS = "PageDraft"
SUPPLIED = "SuppliedSource"
STAMP = sa.DateTime(timezone=True)
JSONB = postgresql.JSONB(astext_type=sa.Text())
UUIDS = postgresql.ARRAY(sa.UUID())
SUBJECT_KINDS = ("craft", "family", "category")
DRAFT_STATES = ("OPEN", "SUBMITTED")
SUPPLIED_STATES = ("READY", "AWAITING_FILE")
ACCESS_KINDS = ("SUBSCRIPTION", "INSTITUTION", "OWN_COPY", "ARCHIVE", "BLOCKED_SITE")
UPLOADS = ("pdf", "text")
GRADES = ("A", "B", "C", "D")
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
    _create_drafts()
    _create_supplied()
    for table in (DRAFTS, SUPPLIED):
        op.execute(f'ALTER TABLE "{table}" ENABLE ROW LEVEL SECURITY')
        op.execute(REVOKE_PUBLIC_ROLES.replace("{table}", table))


def downgrade() -> None:
    op.drop_table(SUPPLIED)
    op.drop_table(DRAFTS)


def _create_drafts() -> None:
    op.create_table(
        "PageDraft",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("userId", sa.UUID(), nullable=False),
        sa.Column("subjectKind", sa.String(length=20), nullable=False),
        sa.Column("subjectSlug", sa.String(length=200), nullable=False),
        sa.Column("state", sa.String(length=20), server_default=sa.text("'OPEN'"), nullable=False),
        sa.Column(
            "parts",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("bytes", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("version", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.Column("previewUrl", sa.Text(), nullable=True),
        sa.Column("previewExpiresAt", STAMP, nullable=True),
        sa.Column("report", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("result", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("submittedAt", STAMP, nullable=True),
        sa.Column("expiresAt", STAMP, nullable=False),
        sa.Column("createdAt", STAMP, server_default=sa.text("now()"), nullable=False),
        sa.Column("updatedAt", STAMP, server_default=sa.text("now()"), nullable=False),
        *_checks(DRAFTS, _draft_checks()),
        *_keys(DRAFTS),
    )
    op.create_index(
        "PageDraft_userId_subject_open_key",
        DRAFTS,
        ["userId", "subjectKind", "subjectSlug"],
        unique=True,
        postgresql_where=sa.text("\"state\" = 'OPEN'"),
    )
    op.create_index(op.f(f"{DRAFTS}_userId_expiresAt_idx"), DRAFTS, ["userId", "expiresAt"])


def _create_supplied() -> None:
    op.create_table(
        "SuppliedSource",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("userId", sa.UUID(), nullable=False),
        sa.Column("userTokenVersion", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("state", sa.String(length=20), nullable=False),
        sa.Column("citeUrl", sa.String(length=2048), nullable=False),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column("doi", sa.String(length=255), nullable=True),
        sa.Column("isbn", sa.String(length=13), nullable=True),
        sa.Column("identity", JSONB, nullable=False),
        sa.Column("confirmation", JSONB, nullable=True),
        sa.Column("accessKind", sa.String(length=20), nullable=False),
        sa.Column("accessedOn", sa.Date(), nullable=False),
        sa.Column("accessNote", sa.String(length=300), nullable=True),
        sa.Column("licence", sa.String(length=200), nullable=True),
        sa.Column("grade", sa.String(length=1), nullable=False),
        sa.Column("gradeReason", sa.String(length=400), nullable=False),
        sa.Column("passages", JSONB, server_default=sa.text("'[]'::jsonb"), nullable=False),
        sa.Column("text", sa.Text(), nullable=True),
        sa.Column("textSha256", sa.String(length=64), nullable=True),
        sa.Column("fileSha256", sa.String(length=64), nullable=True),
        sa.Column("characters", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("upload", sa.String(length=10), nullable=True),
        sa.Column("slotHash", sa.String(length=64), nullable=True),
        sa.Column("slotExpiresAt", STAMP, nullable=True),
        sa.Column("sourceIds", UUIDS, server_default=sa.text("ARRAY[]::uuid[]"), nullable=False),
        sa.Column("createdAt", STAMP, server_default=sa.text("now()"), nullable=False),
        sa.Column("updatedAt", STAMP, server_default=sa.text("now()"), nullable=False),
        *_checks(SUPPLIED, _supplied_checks()),
        *_keys(SUPPLIED),
        sa.UniqueConstraint("slotHash", name=op.f(f"{SUPPLIED}_slotHash_key")),
    )
    op.create_index(op.f(f"{SUPPLIED}_userId_citeUrl_idx"), SUPPLIED, ["userId", "citeUrl"])
    op.create_index(op.f(f"{SUPPLIED}_userId_createdAt_idx"), SUPPLIED, ["userId", "createdAt"])


def _keys(table: str) -> list[sa.Constraint]:
    owner = sa.ForeignKeyConstraint(
        ["userId"], ["User.id"], name=op.f(f"{table}_userId_fkey"), ondelete="CASCADE"
    )
    return [owner, sa.PrimaryKeyConstraint("id", name=op.f(f"{table}_pkey"))]


def _draft_checks() -> dict[str, str]:
    return {
        "subjectKind": f'"subjectKind" IN ({_listed(SUBJECT_KINDS)})',
        "state": f'"state" IN ({_listed(DRAFT_STATES)})',
        "parts": "jsonb_typeof(\"parts\") = 'object'",
        "counts": '"bytes" >= 0 AND "version" >= 1',
        "submitted": '("state" = \'SUBMITTED\') = ("submittedAt" IS NOT NULL AND "result" IS NOT NULL)',
    }


def _supplied_checks() -> dict[str, str]:
    return {
        "state": f'"state" IN ({_listed(SUPPLIED_STATES)})',
        "accessKind": f'"accessKind" IN ({_listed(ACCESS_KINDS)})',
        "grade": f'"grade" IN ({_listed(GRADES)})',
        "upload": f'"upload" IS NULL OR "upload" IN ({_listed(UPLOADS)})',
        "ready": '("state" = \'READY\') = ("text" IS NOT NULL AND "textSha256" IS NOT NULL)',
        "slot": '("slotHash" IS NULL) = ("slotExpiresAt" IS NULL)',
        "passages": "jsonb_typeof(\"passages\") = 'array'",
        "characters": '"characters" >= 0',
    }


def _checks(table: str, checks: dict[str, str]) -> list[sa.CheckConstraint]:
    return [sa.CheckConstraint(rule, name=op.f(f"{table}_{name}_check")) for name, rule in checks.items()]


def _listed(values: Sequence[str]) -> str:
    return ", ".join(f"'{value}'" for value in values)
