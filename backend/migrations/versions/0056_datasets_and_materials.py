from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0056_datasets_and_materials"
down_revision: str | Sequence[str] | None = "0055_answer_gaps"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

STAMP = sa.DateTime(timezone=True)
KIND_CHECKS = ("KnowledgePiece", "ComponentProposal")
DECLARED_SPEC = {"KnowledgePiece": "\"payload\" ? 'delivered'", "ComponentProposal": "\"spec\" ? 'head'"}
RENAMED_KINDS = (
    ("general_drawing", "drawing"),
    ("general_chart", "chart"),
    ("general_table", "fact_table"),
    ("general_timeline", "timeline"),
    ("general_map_layer", "map_layer"),
)
BLOCK_KINDS = (
    "prose",
    "process_ladder",
    "region_story",
    "map_layer",
    "reaction_player",
    "material_card",
    "molecule_3d",
    "images",
    "simulation",
    "what_if",
    "timeline_map",
    "zoom_story",
    "expert_view",
    "seasons",
    "supply_map",
    "compare",
    "in_practice",
    "quiz",
    "open_questions",
    "artisan_voice",
    "designs",
    "concept_graph",
    "measure",
    "market_gi",
    "climate_risk",
    "indigo_vat",
    "mordant_bath",
    "lost_wax",
    "firing",
    "component",
)
COMPONENT_KINDS_BEFORE = (
    "ai_illustration",
    "ai_video",
    "ask_next",
    "audio_player",
    "chart",
    "choice_toggle",
    "citation_tool",
    "comic",
    "concept_atlas",
    "credits",
    "diagram",
    "dip_player",
    "equation_card",
    "experiment_lab",
    "explainer",
    "fact_table",
    "film",
    "generator",
    "label_card",
    "language_switch",
    "map_sequence",
    "material_cards",
    "model_explainer",
    "picture_plate",
    "process_replay",
    "reading_level",
    "related_crafts",
    "source_disagreements",
    "source_list",
    "specimen_plate",
    "stage_player",
    "stat_tiles",
    "structure_diagram",
    "swatch_cards",
    "swatch_pair",
    "timeline",
    "voice",
)
PIECE_KINDS_BEFORE = (*BLOCK_KINDS, *COMPONENT_KINDS_BEFORE, *(old for old, _ in RENAMED_KINDS))
PIECE_KINDS = (*BLOCK_KINDS, *sorted((*COMPONENT_KINDS_BEFORE, "drawing")))
ORIGINS = ("SITE", "CONTRIBUTED")
SHA256 = "~ '^[0-9a-f]{64}$'"
NEW_TABLES = ("DatasetTable", "DatasetUpload")
DOCUMENT_KINDS = """
UPDATE "MonographDocument" AS d
SET "document" = jsonb_set(
    d."document",
    '{{content,components}}',
    (
        SELECT jsonb_agg(
            CASE WHEN c ->> 'kind' = '{old}' THEN jsonb_set(c, '{{kind}}', '"{new}"') ELSE c END
            ORDER BY n
        )
        FROM jsonb_array_elements(d."document" -> 'content' -> 'components') WITH ORDINALITY AS t(c, n)
    )
)
WHERE jsonb_typeof(d."document" -> 'content' -> 'components') = 'array'
AND d."document" -> 'content' -> 'components' @> '[{{"kind": "{old}"}}]'
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
    for table in KIND_CHECKS:
        _drop_kind_check(table)
        for old, new in RENAMED_KINDS:
            op.execute(f'UPDATE "{table}" SET "kind" = \'{new}\' WHERE "kind" = \'{old}\'')
        _add_kind_check(table, PIECE_KINDS)
    for old, new in RENAMED_KINDS:
        op.execute(DOCUMENT_KINDS.format(old=old, new=new))
    _dataset_columns()
    _dataset_tables()
    _dataset_uploads()
    for table in NEW_TABLES:
        op.execute(f'ALTER TABLE "{table}" ENABLE ROW LEVEL SECURITY')
        op.execute(REVOKE_PUBLIC_ROLES.format(table=table))


def downgrade() -> None:
    for table in reversed(NEW_TABLES):
        op.drop_table(table)
    op.drop_index(op.f("EnvDataset_proposedById_idx"), table_name="EnvDataset")
    op.drop_constraint(op.f("EnvDataset_proposedById_fkey"), "EnvDataset", type_="foreignkey")
    op.drop_constraint(op.f("EnvDataset_origin_check"), "EnvDataset", type_="check")
    for column in ("proposedById", "origin", "landingUrl", "doi", "version"):
        op.drop_column("EnvDataset", column)
    for table in KIND_CHECKS:
        _drop_kind_check(table)
        for old, new in RENAMED_KINDS:
            declared = DECLARED_SPEC[table]
            op.execute(f'UPDATE "{table}" SET "kind" = \'{old}\' WHERE "kind" = \'{new}\' AND {declared}')
        op.execute(f'DELETE FROM "{table}" WHERE "kind" = \'drawing\'')
        _add_kind_check(table, PIECE_KINDS_BEFORE)
    op.execute(DOCUMENT_KINDS.format(old="drawing", new="general_drawing"))


def _drop_kind_check(table: str) -> None:
    op.drop_constraint(op.f(f"{table}_kind_check"), table, type_="check")


def _add_kind_check(table: str, kinds: Sequence[str]) -> None:
    listed = ", ".join(f"'{kind}'" for kind in kinds)
    op.create_check_constraint(op.f(f"{table}_kind_check"), table, f'"kind" IN ({listed})')


def _dataset_columns() -> None:
    op.add_column("EnvDataset", sa.Column("version", sa.String(length=120), nullable=True))
    op.add_column("EnvDataset", sa.Column("doi", sa.String(length=200), nullable=True))
    op.add_column("EnvDataset", sa.Column("landingUrl", sa.Text(), nullable=True))
    op.add_column(
        "EnvDataset", sa.Column("origin", sa.String(length=20), server_default="SITE", nullable=False)
    )
    op.add_column("EnvDataset", sa.Column("proposedById", sa.UUID(), nullable=True))
    listed = ", ".join(f"'{origin}'" for origin in ORIGINS)
    op.create_check_constraint(op.f("EnvDataset_origin_check"), "EnvDataset", f'"origin" IN ({listed})')
    op.create_foreign_key(
        op.f("EnvDataset_proposedById_fkey"),
        "EnvDataset",
        "User",
        ["proposedById"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(op.f("EnvDataset_proposedById_idx"), "EnvDataset", ["proposedById"])


def _dataset_tables() -> None:
    table = "DatasetTable"
    op.create_table(
        "DatasetTable",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("datasetId", sa.UUID(), nullable=False),
        sa.Column("columns", postgresql.ARRAY(sa.Text()), nullable=False),
        sa.Column("rows", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("rowCount", sa.Integer(), nullable=False),
        sa.Column("byteSize", sa.Integer(), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("createdAt", STAMP, server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(f'"sha256" {SHA256}', name=op.f(f"{table}_sha256_check")),
        sa.CheckConstraint("jsonb_typeof(\"rows\") = 'array'", name=op.f(f"{table}_rows_check")),
        sa.CheckConstraint('"rowCount" >= 1 AND "byteSize" >= 1', name=op.f(f"{table}_size_check")),
        sa.ForeignKeyConstraint(
            ["datasetId"], ["EnvDataset.id"], name=op.f(f"{table}_datasetId_fkey"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f(f"{table}_pkey")),
        sa.UniqueConstraint("datasetId", name=op.f(f"{table}_datasetId_key")),
    )


def _dataset_uploads() -> None:
    table = "DatasetUpload"
    op.create_table(
        "DatasetUpload",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("userId", sa.UUID(), nullable=False),
        sa.Column("userTokenVersion", sa.Integer(), nullable=False),
        sa.Column("slotHash", sa.String(length=64), nullable=False),
        sa.Column("record", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("expiresAt", STAMP, nullable=False),
        sa.Column("usedAt", STAMP, nullable=True),
        sa.Column("datasetId", sa.UUID(), nullable=True),
        sa.Column("createdAt", STAMP, server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(f'"sha256" {SHA256}', name=op.f(f"{table}_sha256_check")),
        sa.CheckConstraint("jsonb_typeof(\"record\") = 'object'", name=op.f(f"{table}_record_check")),
        sa.CheckConstraint('"datasetId" IS NULL OR "usedAt" IS NOT NULL', name=op.f(f"{table}_used_check")),
        sa.ForeignKeyConstraint(
            ["userId"], ["User.id"], name=op.f(f"{table}_userId_fkey"), ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["datasetId"], ["EnvDataset.id"], name=op.f(f"{table}_datasetId_fkey"), ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f(f"{table}_pkey")),
        sa.UniqueConstraint("slotHash", name=op.f(f"{table}_slotHash_key")),
    )
    op.create_index(op.f(f"{table}_userId_expiresAt_idx"), table, ["userId", "expiresAt"])
    op.create_index(op.f(f"{table}_datasetId_idx"), table, ["datasetId"])
