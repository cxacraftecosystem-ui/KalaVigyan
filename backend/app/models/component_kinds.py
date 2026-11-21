from app.models.enums import BLOCK_KINDS

__all__ = [
    "AUTHORED_ART_KINDS",
    "AUTHORED_SCRIPT_KINDS",
    "COMPONENT_KINDS",
    "DOCUMENT_KINDS",
    "GENERAL_KINDS",
    "PAGE_TOOL_KINDS",
    "PIECE_KINDS",
]

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
GENERAL_KINDS = ("drawing", "chart", "fact_table", "timeline", "map_layer")
PAGE_TOOL_KINDS = (
    "ask_next",
    "audio_player",
    "citation_tool",
    "concept_atlas",
    "credits",
    "explainer",
    "film",
    "generator",
    "language_switch",
    "process_replay",
    "quiz",
    "reading_level",
    "related_crafts",
    "source_list",
)
AUTHORED_ART_KINDS = ("ai_illustration", "ai_video", "comic", "picture_plate", "specimen_plate")
AUTHORED_SCRIPT_KINDS = ("model_explainer", "timeline_map")
PIECE_KINDS = (*BLOCK_KINDS, *COMPONENT_KINDS)
DOCUMENT_KINDS = ("answer_block", "why_here")
