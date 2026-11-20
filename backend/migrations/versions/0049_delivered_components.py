from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0049_delivered_components"
down_revision: str | Sequence[str] | None = "0050_image_screens"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PIECES = "KnowledgePiece"
PROPOSALS = "ComponentProposal"
PREVIEWS = "PagePreview"
STAMP = sa.DateTime(timezone=True)
KIND_CHECKS = (PIECES, PROPOSALS)
GENERAL_KINDS = ("general_drawing", "general_chart", "general_table", "general_timeline", "general_map_layer")
PIECE_KINDS_BEFORE = (
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
PIECE_KINDS = (*PIECE_KINDS_BEFORE, *GENERAL_KINDS)
PREVIEW_SUBJECT_KINDS = ("craft", "family", "category")
DELIVERED_SPEC = (
    '("spec" IS NULL AND "units" IS NULL) OR '
    "(jsonb_typeof(\"spec\") = 'object' AND jsonb_typeof(\"units\") = 'object')"
)
REVOKE_PUBLIC_ROLES = """
DO $do$
DECLARE grantee text;
BEGIN
    FOREACH grantee IN ARRAY ARRAY['anon', 'authenticated'] LOOP
        IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = grantee) THEN
            EXECUTE format('REVOKE ALL ON "PagePreview" FROM %I', grantee);
        END IF;
    END LOOP;
END
$do$
"""


def upgrade() -> None:
    for table in KIND_CHECKS:
        _check_kinds(table, PIECE_KINDS)
    op.add_column(
        "ComponentProposal", sa.Column("spec", postgresql.JSONB(astext_type=sa.Text()), nullable=True)
    )
    op.add_column(
        "ComponentProposal", sa.Column("units", postgresql.JSONB(astext_type=sa.Text()), nullable=True)
    )
    op.add_column(
        "ComponentProposal",
        sa.Column(
            "claimIds", postgresql.ARRAY(sa.UUID()), server_default=sa.text("ARRAY[]::uuid[]"), nullable=False
        ),
    )
    op.create_check_constraint(op.f(f"{PROPOSALS}_delivered_check"), PROPOSALS, DELIVERED_SPEC)
    _create_previews()


def downgrade() -> None:
    op.drop_table(PREVIEWS)
    op.drop_constraint(op.f(f"{PROPOSALS}_delivered_check"), PROPOSALS, type_="check")
    for column in ("claimIds", "units", "spec"):
        op.drop_column(PROPOSALS, column)
    for table in KIND_CHECKS:
        op.execute(f'DELETE FROM "{table}" WHERE "kind" IN ({_listed(GENERAL_KINDS)})')
        _check_kinds(table, PIECE_KINDS_BEFORE)


def _create_previews() -> None:
    op.create_table(
        "PagePreview",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("userId", sa.UUID(), nullable=False),
        sa.Column("subjectKind", sa.String(length=20), nullable=False),
        sa.Column("subjectSlug", sa.String(length=200), nullable=False),
        sa.Column("document", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("expiresAt", STAMP, nullable=False),
        sa.Column("createdAt", STAMP, server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            f'"subjectKind" IN ({_listed(PREVIEW_SUBJECT_KINDS)})', name=op.f(f"{PREVIEWS}_subjectKind_check")
        ),
        sa.CheckConstraint('"expiresAt" > "createdAt"', name=op.f(f"{PREVIEWS}_expires_check")),
        sa.CheckConstraint("jsonb_typeof(\"document\") = 'object'", name=op.f(f"{PREVIEWS}_document_check")),
        sa.ForeignKeyConstraint(
            ["userId"], ["User.id"], name=op.f(f"{PREVIEWS}_userId_fkey"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f(f"{PREVIEWS}_pkey")),
    )
    op.create_index(op.f(f"{PREVIEWS}_userId_expiresAt_idx"), PREVIEWS, ["userId", "expiresAt"])
    op.execute(f'ALTER TABLE "{PREVIEWS}" ENABLE ROW LEVEL SECURITY')
    op.execute(REVOKE_PUBLIC_ROLES)


def _check_kinds(table: str, kinds: Sequence[str]) -> None:
    name = op.f(f"{table}_kind_check")
    op.drop_constraint(name, table, type_="check")
    op.create_check_constraint(name, table, f'"kind" IN ({_listed(kinds)})')


def _listed(values: Sequence[str]) -> str:
    return ", ".join(f"'{value}'" for value in values)
