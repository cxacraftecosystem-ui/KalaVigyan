import uuid
from datetime import UTC, datetime
from typing import Any

from app.research.structure_proposals import StructureProposal
from app.services.curated_index import (
    CuratedPage,
    IndexAfter,
    IndexConflict,
    IndexMaterial,
    IndexNativeName,
    IndexStage,
)

SLUG = "Structure-Test-Craft"
PAGE_URL = "https://crafts.example.org/structure/dyeing"
PAGE_TEXT = (
    "Printers here call the cloth ajrak, from the word for blue. After the second wash in the river the "
    "cloth turns a deep red where the alum mordant was printed. Alum is potassium aluminium sulfate, "
    "KAl(SO4)2, and it binds the dye alizarin to the cotton. Indigo comes from Indigofera tinctoria, "
    "grown in the delta. The craft was registered on 2009-03-10 under application number 182."
)
NAME_QUOTE = "Printers here call the cloth ajrak, from the word for blue"
AFTER_QUOTE = "the cloth turns a deep red where the alum mordant was printed"
FORMULA_QUOTE = "Alum is potassium aluminium sulfate, KAl(SO4)2, and it binds the dye alizarin to the cotton"
BOTANY_QUOTE = "Indigo comes from Indigofera tinctoria, grown in the delta"
GI_QUOTE = "The craft was registered on 2009-03-10 under application number 182"


def key(name: str) -> uuid.UUID:
    return uuid.uuid5(uuid.NAMESPACE_URL, f"test-structure/{name}")


STAGE_ID, STAGE_CONCEPT = key("stage"), key("stage-concept")
OTHER_STAGE_ID, OTHER_CONCEPT = key("other-stage"), key("other-concept")
MATERIAL_ID, MATERIAL_CONCEPT = key("material"), key("material-concept")
HISTORY_CONCEPT = key("history-concept")
HELD_A, HELD_B, HELD_C = key("held-a"), key("held-b"), key("held-c")
OLD_AFTER = key("old-after")


def stage(stage_key: str, stage_id: uuid.UUID, concept: uuid.UUID, **changes: Any) -> IndexStage:
    base: dict[str, Any] = {
        "key": stage_key,
        "stage_id": stage_id,
        "concept_id": concept,
        "local_name": None,
        "order": None,
        "order_claim_id": None,
        "duration": None,
        "season": None,
        "claim_ids": [HELD_A],
    }
    return IndexStage(**(base | changes))


def indigo() -> IndexMaterial:
    return IndexMaterial(
        key="M01",
        material_id=MATERIAL_ID,
        concept_id=MATERIAL_CONCEPT,
        name="Indigo",
        kind="DYE",
        role="DYE",
        local_names=[],
        botanical_name=None,
        pubchem_cid=None,
        claim_ids=[HELD_A],
    )


def curated_page(**changes: Any) -> CuratedPage:
    base: dict[str, Any] = {
        "craft_slug": SLUG,
        "version": 2,
        "curated_at": datetime(2026, 11, 1, tzinfo=UTC),
        "coverage": "THIN",
        "searched": [],
        "process_id": None,
        "craft_concepts": {"HISTORY": HISTORY_CONCEPT},
        "overview": {},
        "conflicts": [IndexConflict(about="When the river dried", claim_ids=[HELD_B, HELD_C])],
        "open_questions": [],
        "places": [],
        "communities": [],
        "stages": [
            stage("P01", STAGE_ID, STAGE_CONCEPT),
            stage("P02", OTHER_STAGE_ID, OTHER_CONCEPT, after=IndexAfter(text="Pale", claim_id=OLD_AFTER)),
        ],
        "materials": [indigo()],
        "tools": [],
        "reactions": [],
        "glossary": [],
        "pictures": [],
        "environment": [],
        "native_names": [IndexNativeName(text="Ajrakh", language="hi", script="Deva", claim_id=HELD_A)],
        "claim_order": [HELD_A, HELD_B, HELD_C],
    }
    return CuratedPage(**(base | changes))


def source(quote: str, **changes: Any) -> dict[str, Any]:
    return {
        "url": PAGE_URL,
        "title": "Dyeing in the delta",
        "language": "en",
        "quotes": [{"text": quote, "locator": "para 1"}],
    } | changes


def proposal(item: dict[str, Any], quote: str = NAME_QUOTE, **changes: Any) -> StructureProposal:
    body: dict[str, Any] = {
        "subject": {"kind": "craft", "slug": SLUG},
        "item": item,
        "field": "HISTORY",
        "statement": "Printers in the delta call the cloth ajrak, after their word for blue.",
        "sources": [source(quote)],
    }
    return StructureProposal.model_validate(body | changes)
