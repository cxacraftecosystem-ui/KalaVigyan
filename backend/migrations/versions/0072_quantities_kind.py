from collections.abc import Sequence

from alembic import op

revision: str = "0072_quantities_kind"
down_revision: str | Sequence[str] | None = "0080_stream_stamps_differs_on"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

KIND_CHECKS = ("KnowledgePiece", "ComponentProposal")
ADDED_KINDS = ("quantities",)
BLOCK_KINDS_BEFORE = (
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
BLOCK_KINDS = (*BLOCK_KINDS_BEFORE[:-1], *ADDED_KINDS, BLOCK_KINDS_BEFORE[-1])
COMPONENT_KINDS = (
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
    "drawing",
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


def upgrade() -> None:
    for table in KIND_CHECKS:
        _check_kinds(table, (*BLOCK_KINDS, *COMPONENT_KINDS))


def downgrade() -> None:
    added = ", ".join(f"'{kind}'" for kind in ADDED_KINDS)
    for table in KIND_CHECKS:
        op.execute(f'DELETE FROM "{table}" WHERE "kind" IN ({added})')
        _check_kinds(table, (*BLOCK_KINDS_BEFORE, *COMPONENT_KINDS))


def _check_kinds(table: str, kinds: Sequence[str]) -> None:
    name = op.f(f"{table}_kind_check")
    op.drop_constraint(name, table, type_="check")
    listed = ", ".join(f"'{kind}'" for kind in kinds)
    op.create_check_constraint(name, table, f'"kind" IN ({listed})')
