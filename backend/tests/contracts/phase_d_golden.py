import json
from functools import cache
from typing import Any, Literal

from pydantic import Field

from app.research.base import ContractModel
from app.research.citations import SourceRef
from app.research.crafts import CraftRef
from app.services.craft_page_records import CraftPageRecords
from app.services.curation_preview import master_craft, preview_records
from app.services.knowledge_view import ClaimView

from ..curation.import_support import plan_of
from .golden import golden_json
from .phase_b_golden import FixturePiece, FixtureSection

__all__ = [
    "CURATED_CRAFT",
    "PHASE_D",
    "PhaseDFixture",
    "curated_sources",
    "curated_views",
    "phase_d",
    "phase_d_blocks",
]

PHASE_D = "explainer.phase-d.golden.json"
CURATED_CRAFT = "Kutch-Ajrakh"


class PhaseDFixture(ContractModel):
    schema_version: Literal[1]
    crafts: list[CraftRef] = Field(min_length=2, max_length=2)
    sections: list[FixtureSection] = Field(min_length=1)
    pieces: list[FixturePiece]
    sources: list[SourceRef]


@cache
def _phase_d() -> str:
    return json.dumps(golden_json(PHASE_D))


def phase_d() -> dict[str, Any]:
    return json.loads(_phase_d())


def phase_d_blocks() -> dict[str, dict[str, Any]]:
    return {block["id"]: block for section in phase_d()["sections"] for block in section["blocks"]}


@cache
def _curated_records() -> CraftPageRecords:
    craft, names = master_craft(CURATED_CRAFT)
    return preview_records(plan_of(CURATED_CRAFT), craft, names)


def curated_views() -> dict[str, ClaimView]:
    return {str(view.id): view for view in _curated_records().views}


def curated_sources() -> dict[str, SourceRef]:
    return dict(_curated_records().sources)
