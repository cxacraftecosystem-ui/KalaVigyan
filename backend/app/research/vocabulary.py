from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Literal

from app.core.errors import InvalidInput
from app.models.component_kinds import PIECE_KINDS
from app.models.enums import (
    ANSWER_MODES,
    BLOCK_KINDS,
    CHUNK_ACLS,
    CONCEPT_TYPES,
    DISCIPLINES,
    ENV_STATS,
    EVIDENCE_LEVELS,
    EXPLAINER_DEPTHS,
    LIVE_TIERS,
    MATERIAL_KINDS,
    MATERIAL_ROLES,
    MEDIA_KINDS,
    PIECE_SUBJECT_KINDS,
    PLACE_ROLES,
    QUOTE_CHECKS,
    REACTION_KINDS,
    RELIABILITIES,
    SOURCE_KINDS,
    SOURCE_RELATIONS,
    STAGE_TYPES,
)

__all__ = [
    "ANSWER_LANGUAGES",
    "ANSWER_LANGUAGE_SPECS",
    "CANONICAL_LANGUAGE",
    "CONCEPT_TYPE_DISCIPLINES",
    "EVIDENCE_LABELS",
    "FACT_LEVELS",
    "HYPOTHESIS_LEVEL",
    "LABEL_LEVELS",
    "LEVEL_ORDER",
    "RETRIEVAL_TIERS",
    "RIGHT_TO_LEFT_SCRIPTS",
    "SHOWN_LEVELS",
    "STORED_TIERS",
    "AnswerLanguage",
    "AnswerLanguageSpec",
    "AnswerMode",
    "BlockKind",
    "ChunkAcl",
    "Depth",
    "Discipline",
    "EnvStat",
    "EvidenceLabel",
    "EvidenceLevel",
    "FacetType",
    "LiveTier",
    "MaterialKind",
    "MaterialRole",
    "MediaKind",
    "PieceKind",
    "PieceSubjectKind",
    "PlaceRole",
    "QuoteCheck",
    "ReactionKind",
    "RetrievalTier",
    "ShownLevel",
    "SourceRelation",
    "SourceType",
    "StageType",
    "TextDirection",
    "TrustTier",
    "answer_language_options",
    "language_option",
    "text_direction",
    "weakest_level",
]

CONCEPT_TYPE_DISCIPLINES: Mapping[str, str] = MappingProxyType(
    {
        "TRADITION": "OVERVIEW",
        "HISTORICAL_CONTEXT": "HISTORY",
        "DESIGN_PRINCIPLE": "DESIGN",
        "PROCESS_STAGE": "PROCESS",
        "ARTISAN_ACTION": "PROCESS",
        "ARTISAN_DECISION": "PROCESS",
        "SENSORY_CUE": "PROCESS",
        "MATERIAL": "MATERIALS",
        "TOOL": "MATERIALS",
        "PROPERTY": "MATERIALS",
        "MECHANISM": "CHEMISTRY",
        "EXPLANATION": "CHEMISTRY",
        "CHANGE": "CHEMISTRY",
        "ENVIRONMENTAL_CONDITION": "GEOGRAPHY",
    }
)

STORED_TIERS = ("T0", "T1", "T2")
RETRIEVAL_TIERS = (*STORED_TIERS, *LIVE_TIERS)
SHOWN_LEVELS = (*EVIDENCE_LEVELS, "UNAVAILABLE")
EVIDENCE_LABELS = ("QUOTED", "INFERRED")
HYPOTHESIS_LEVEL = "HYPOTHESIS"
LABEL_LEVELS = {"QUOTED": "PROVISIONAL", "INFERRED": HYPOTHESIS_LEVEL}
LEVEL_ORDER = {level: rank for rank, level in enumerate(EVIDENCE_LEVELS)}
FACT_LEVELS = tuple(level for level in EVIDENCE_LEVELS if level != HYPOTHESIS_LEVEL)


@dataclass(frozen=True)
class AnswerLanguageSpec:
    label: str
    autonym: str
    script: str


ANSWER_LANGUAGE_SPECS: Mapping[str, AnswerLanguageSpec] = MappingProxyType(
    {
        "en": AnswerLanguageSpec("English", "English", "Latn"),
        "hi": AnswerLanguageSpec("Hindi", "हिन्दी", "Deva"),
        "bn": AnswerLanguageSpec("Bengali", "বাংলা", "Beng"),
        "ta": AnswerLanguageSpec("Tamil", "தமிழ்", "Taml"),
        "te": AnswerLanguageSpec("Telugu", "తెలుగు", "Telu"),
        "mr": AnswerLanguageSpec("Marathi", "मराठी", "Deva"),
        "gu": AnswerLanguageSpec("Gujarati", "ગુજરાતી", "Gujr"),
        "kn": AnswerLanguageSpec("Kannada", "ಕನ್ನಡ", "Knda"),
        "ml": AnswerLanguageSpec("Malayalam", "മലയാളം", "Mlym"),
        "or": AnswerLanguageSpec("Odia", "ଓଡ଼ିଆ", "Orya"),
        "pa": AnswerLanguageSpec("Punjabi", "ਪੰਜਾਬੀ", "Guru"),
        "as": AnswerLanguageSpec("Assamese", "অসমীয়া", "Beng"),
        "ur": AnswerLanguageSpec("Urdu", "اردو", "Arab"),
    }
)
ANSWER_LANGUAGES = tuple(ANSWER_LANGUAGE_SPECS)
CANONICAL_LANGUAGE = "en"
RIGHT_TO_LEFT_SCRIPTS = frozenset({"Arab"})
TEXT_DIRECTIONS = ("ltr", "rtl")

AnswerLanguage = Literal[*ANSWER_LANGUAGES]
TextDirection = Literal[*TEXT_DIRECTIONS]
AnswerMode = Literal[*ANSWER_MODES]
ChunkAcl = Literal[*CHUNK_ACLS]
EvidenceLevel = Literal[*EVIDENCE_LEVELS]
ShownLevel = Literal[*SHOWN_LEVELS]
RetrievalTier = Literal[*RETRIEVAL_TIERS]
LiveTier = Literal[*LIVE_TIERS]
TrustTier = Literal[*RELIABILITIES]
SourceType = Literal[*SOURCE_KINDS]
FacetType = Literal[*CONCEPT_TYPES]
QuoteCheck = Literal[*QUOTE_CHECKS]
SourceRelation = Literal[*SOURCE_RELATIONS]
EvidenceLabel = Literal[*EVIDENCE_LABELS]
StageType = Literal[*STAGE_TYPES]
MaterialKind = Literal[*MATERIAL_KINDS]
MaterialRole = Literal[*MATERIAL_ROLES]
ReactionKind = Literal[*REACTION_KINDS]
EnvStat = Literal[*ENV_STATS]
MediaKind = Literal[*MEDIA_KINDS]
PlaceRole = Literal[*PLACE_ROLES]
PieceSubjectKind = Literal[*PIECE_SUBJECT_KINDS]
PieceKind = Literal[*PIECE_KINDS]
Depth = Literal[*EXPLAINER_DEPTHS]
BlockKind = Literal[*BLOCK_KINDS]
Discipline = Literal[*DISCIPLINES]


def weakest_level(levels: Iterable[str]) -> str:
    given = list(levels)
    if not given:
        raise InvalidInput("A level needs at least one input level")
    unknown = sorted({level for level in given if level not in LEVEL_ORDER})
    if unknown:
        raise InvalidInput(f"Unknown evidence levels: {', '.join(unknown)}")
    return max(given, key=LEVEL_ORDER.__getitem__)


def text_direction(language: str) -> TextDirection:
    spec = ANSWER_LANGUAGE_SPECS.get(language)
    if spec is None:
        raise InvalidInput(f"Unknown answer language {language!r}")
    return "rtl" if spec.script in RIGHT_TO_LEFT_SCRIPTS else "ltr"


def answer_language_options() -> list[dict[str, str]]:
    return [language_option(code) for code in ANSWER_LANGUAGES]


def language_option(language: str) -> dict[str, str]:
    spec = ANSWER_LANGUAGE_SPECS.get(language)
    if spec is None:
        raise InvalidInput(f"Unknown answer language {language!r}")
    return {
        "code": language,
        "label": spec.label,
        "autonym": spec.autonym,
        "script": spec.script,
        "direction": text_direction(language),
    }
