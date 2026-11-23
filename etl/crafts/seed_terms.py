from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from typing import Any

__all__ = [
    "CONCEPT_TYPES",
    "HYPOTHESIS",
    "PROVISIONAL",
    "RELATIONS",
    "STAGE_TYPES",
    "ClaimSubject",
    "SeedClaim",
    "concept_type",
    "sha1_text",
    "stage_type",
]

PROVISIONAL = "PROVISIONAL"
HYPOTHESIS = "HYPOTHESIS"

CONCEPT_TYPES = {
    "tradition": "TRADITION",
    "material": "MATERIAL",
    "tool": "TOOL",
    "process_stage": "PROCESS_STAGE",
    "artisan_decision": "ARTISAN_DECISION",
    "design_principle": "DESIGN_PRINCIPLE",
    "outcome": "OUTCOME",
    "scientific_mechanism": "MECHANISM",
    "mechanism": "MECHANISM",
    "environmental_condition": "ENVIRONMENTAL_CONDITION",
    "environment": "ENVIRONMENTAL_CONDITION",
    "historical_context": "HISTORICAL_CONTEXT",
    "history": "HISTORICAL_CONTEXT",
    "comparison": "COMPARISON",
    "explanation": "EXPLANATION",
    "open_question": "OPEN_QUESTION",
    "action": "ARTISAN_ACTION",
    "sensory_cue": "SENSORY_CUE",
    "property": "PROPERTY",
    "change": "CHANGE",
    "concept": "CONCEPT",
}

RELATIONS = {
    "BELONGS_TO": "PART_OF",
    "PART_OF": "PART_OF",
    "USES": "USES",
    "PRECEDES": "PRECEDES",
    "PRODUCES": "PRODUCES",
    "AFFECTED_BY": "AFFECTED_BY",
    "SCIENTIFICALLY_EXPLAINED_BY": "SCIENTIFICALLY_EXPLAINED_BY",
}

STAGE_TYPES: tuple[tuple[str, str], ...] = (
    ("scour", "SCOUR"),
    ("saaj", "SCOUR"),
    ("desiz", "SCOUR"),
    ("mordant", "MORDANT"),
    ("harda", "MORDANT"),
    ("tannin", "MORDANT"),
    ("resist", "RESIST"),
    ("dabu", "RESIST"),
    ("mud", "RESIST"),
    ("indigo", "DYE"),
    ("dye", "DYE"),
    ("dyeing", "DYE"),
    ("boil", "DYE"),
    ("print", "PRINT"),
    ("wash", "WASH"),
    ("rins", "WASH"),
    ("dry", "DRY"),
    ("sun", "DRY"),
    ("bleach", "DRY"),
    ("fir", "FIRE"),
    ("kiln", "FIRE"),
    ("cast", "CAST"),
    ("carv", "CARVE"),
    ("shap", "SHAPE"),
    ("form", "SHAPE"),
    ("finish", "FINISH"),
    ("burnish", "FINISH"),
)


def sha1_text(*parts: str) -> str:
    return hashlib.sha1("␟".join(parts).encode("utf-8")).hexdigest()


def stage_type(*texts: str) -> str:
    blob = " ".join(texts).lower()
    for needle, kind in STAGE_TYPES:
        if re.search(r"(?<![a-z])" + re.escape(needle), blob):
            return kind
    return "OTHER"


def concept_type(kind: str) -> str:
    return CONCEPT_TYPES.get(kind, kind.upper())


@dataclass(frozen=True)
class ClaimSubject:
    kind: str
    key: str
    name: str
    predicate: str


@dataclass(frozen=True, kw_only=True)
class SeedClaim:
    craft_slug: str | None
    sub_slug: str
    subject: ClaimSubject
    text: str
    stage: dict[str, Any] | None
    level: str
    reason: str
    provenance_kind: str | None
    sources: list[dict[str, Any]]
    import_ref: dict[str, Any]
    related_keys: list[str] | None = None

    def row(self) -> dict[str, Any]:
        row: dict[str, Any] = {
            "id": "seed-" + sha1_text(self.subject.key, self.text)[:20],
            "craftSlug": self.craft_slug,
            "subCategorySlug": self.sub_slug,
            "subjectType": self.subject.kind,
            "subjectKey": self.subject.key,
            "subjectName": self.subject.name,
            "predicate": self.subject.predicate,
            "text": self.text,
            "textLang": "en",
            "stage": self.stage,
            "evidenceLevel": self.level,
            "levelReason": self.reason,
            "provenanceKind": self.provenance_kind,
            "origin": "IMPORT",
            "status": "PROPOSED",
            "createdByKind": "SYSTEM",
            "systemActor": "import",
            "sensitivity": "OPEN",
            "sources": self.sources,
        }
        if self.related_keys is not None:
            row["relatedKeys"] = self.related_keys
        row["importRef"] = self.import_ref
        return row
