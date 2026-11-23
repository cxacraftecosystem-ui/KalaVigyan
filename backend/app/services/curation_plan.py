from __future__ import annotations

import uuid
from collections.abc import Mapping
from dataclasses import dataclass, replace
from typing import Any, Protocol

from app.curation.check_file import CheckFile
from app.curation.dossier import Dossier
from app.data.district_register import DistrictCodes

from .curated_index import CuratedPage
from .curation_page_index import curated_page_index
from .curation_records import (
    gi_row,
    media_claim_rows,
    media_rows,
    price_rows,
    term_concept_rows,
    term_craft_rows,
    term_rows,
    workforce_rows,
)
from .curation_rows import (
    ConceptPlan,
    CraftTarget,
    claim_rows,
    claim_source_rows,
    concept_plan,
    curated_claim_rows,
    source_rows,
)
from .curation_structure import (
    alternative_rows,
    location_rows,
    material_rows,
    process_row,
    reaction_citation_rows,
    reaction_rows,
    stage_material_rows,
    stage_rows,
)

__all__ = [
    "PLAN_PARTS",
    "SOURCE_REFERENCES",
    "CurationPlan",
    "PlanParts",
    "Rows",
    "aliased_sources",
    "curation_plan",
]

PLAN_PARTS = (
    "sources",
    "concepts",
    "claims",
    "curatedClaims",
    "claimSources",
    "locations",
    "processes",
    "stages",
    "materials",
    "stageMaterials",
    "reactions",
    "reactionCitations",
    "alternatives",
    "media",
    "mediaClaims",
    "terms",
    "termCrafts",
    "termConcepts",
    "giRecords",
    "prices",
    "workforce",
)
SOURCE_REFERENCES = (("claimSources", "sourceId"), ("locations", "sourceId"))

Rows = tuple[dict[str, Any], ...]


class PlanParts(Protocol):
    def part(self, name: str) -> Rows: ...


def aliased_sources(rows: Mapping[str, Rows], aliases: Mapping[uuid.UUID, uuid.UUID]) -> dict[str, Rows]:
    aliased = dict(rows)
    aliased["sources"] = tuple(row for row in rows["sources"] if row["id"] not in aliases)
    for part, column in SOURCE_REFERENCES:
        if part in aliased:
            aliased[part] = tuple(
                {**row, column: aliases.get(row[column], row[column])} for row in aliased[part]
            )
    return aliased


@dataclass(frozen=True)
class CurationPlan:
    craft: CraftTarget
    dossier: Dossier
    concepts: ConceptPlan
    rows: Mapping[str, Rows]
    index: CuratedPage

    def part(self, name: str) -> Rows:
        return self.rows[name]

    def claim_ids(self) -> list[uuid.UUID]:
        return [row["id"] for row in self.rows["claims"]]

    def with_sources(self, aliases: Mapping[uuid.UUID, uuid.UUID]) -> CurationPlan:
        if not aliases:
            return self
        return replace(self, rows=aliased_sources(self.rows, aliases))


def curation_plan(
    dossier: Dossier, check: CheckFile, craft: CraftTarget, codes: DistrictCodes
) -> CurationPlan:
    concepts = concept_plan(dossier, craft_id=craft.id, name=craft.name)
    locations = location_rows(dossier, craft, codes)
    process = process_row(dossier, craft)
    gi = gi_row(dossier, craft)
    found: dict[str, list[dict[str, Any]]] = {
        "sources": source_rows(dossier, check),
        "concepts": list(concepts.rows),
        "claims": claim_rows(dossier, check, concepts),
        "curatedClaims": curated_claim_rows(dossier, "craftId", craft.id),
        "claimSources": claim_source_rows(dossier, check),
        "locations": locations,
        "processes": [process] if process else [],
        "stages": stage_rows(dossier, concepts),
        "materials": material_rows(dossier, concepts),
        "stageMaterials": stage_material_rows(dossier),
        "reactions": reaction_rows(dossier),
        "reactionCitations": reaction_citation_rows(dossier),
        "alternatives": alternative_rows(dossier, concepts),
        "media": media_rows(dossier),
        "mediaClaims": media_claim_rows(dossier),
        "terms": term_rows(dossier),
        "termCrafts": term_craft_rows(dossier, craft),
        "termConcepts": term_concept_rows(dossier, concepts),
        "giRecords": [gi] if gi else [],
        "prices": price_rows(dossier, craft, codes),
        "workforce": workforce_rows(dossier, craft),
    }
    index = curated_page_index(dossier, concepts, codes, {row["id"] for row in locations})
    rows = {name: tuple(found[name]) for name in PLAN_PARTS}
    return CurationPlan(craft=craft, dossier=dossier, concepts=concepts, rows=rows, index=index)
