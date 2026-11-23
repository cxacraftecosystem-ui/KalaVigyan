from __future__ import annotations

import uuid
from collections import defaultdict
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from app.core.errors import InvalidInput
from app.curation.check_file import CheckFile
from app.curation.checks import default_context
from app.curation.dossier import Dossier
from app.curation.files import CURATION_DIR, checked_dossier
from app.data.craft_master_loader import ACTIVE, seed_plan, seed_uuid
from app.data.district_register import load_district_codes
from app.data.portal_craft_register import load_portal_crafts
from app.models import Claim, ClaimSource, Craft, MediaRef as MediaRefRow, Source
from app.research.citations import SourceRef
from app.research.craft_page import CraftPage
from app.research.crafts import CraftRef
from app.science.records import (
    MaterialRecord,
    ProcessRecord,
    ProcessRecords,
    ReactionRecord,
    SpeciesRecord,
    StageRecord,
)

from .answer_events import cited_claims
from .craft_page import craft_page
from .craft_page_records import ClaimFacts, CraftPageRecords, page_craft
from .craft_page_register import register_context
from .curation_keys import CURATED_STATUS
from .curation_overview import indexed_overview, overview_pieces
from .curation_plan import CurationPlan, PlanParts, curation_plan
from .curation_rows import CraftTarget
from .knowledge_view import ClaimView, cited_view, craft_ref, source_ref
from .media_ref_store import stored_media_ref

__all__ = [
    "checked_records",
    "dossier_preview",
    "dossier_records",
    "master_craft",
    "plan_views",
    "portal_craft",
    "preview_page",
    "preview_records",
]

OPEN = "OPEN"


def master_craft(slug: str) -> tuple[Craft, tuple[str | None, str | None]]:
    plan = seed_plan()
    row = next((craft for craft in plan["crafts"] if craft["slug"] == slug), None)
    if row is None:
        return portal_craft(slug, plan)
    sub = next(item for item in plan["subCategories"] if item["id"] == row["subCategoryId"])
    category = next(item for item in plan["categories"] if item["id"] == sub["categoryId"])
    craft = Craft(
        id=uuid.UUID(row["id"]),
        slug=row["slug"],
        name=row["name"],
        localName=None,
        category=row["category"],
        giStatus=row["giStatus"],
        stateOfPractice=row["stateOfPractice"],
        stateOfOrigin=row["stateOfOrigin"],
        isCatchAll=row["isCatchAll"],
    )
    return craft, (category["name"], sub["name"])


def portal_craft(slug: str, plan: dict[str, Any]) -> tuple[Craft, tuple[str | None, str | None]]:
    found = next((c for c in load_portal_crafts() if c.slug == slug and c.status == ACTIVE), None)
    if found is None:
        raise InvalidInput(f"{slug} is not an active craft on the master list or the portal craft register")
    sub = next((item for item in plan["subCategories"] if item["slug"] == found.sub_category_slug), None)
    category = (
        None if sub is None else next(item for item in plan["categories"] if item["id"] == sub["categoryId"])
    )
    craft = Craft(
        id=uuid.UUID(seed_uuid("c", found.slug)),
        slug=found.slug,
        name=found.name,
        localName=None,
        category=None if category is None else category["name"],
        giStatus=found.gi_status,
        stateOfPractice=list(found.state_of_practice),
        stateOfOrigin=list(found.state_of_origin),
        isCatchAll=False,
    )
    return craft, (
        None if category is None else category["name"],
        None if sub is None else sub["name"],
    )


def dossier_preview(craft_slug: str, *, directory: Path = CURATION_DIR) -> CraftPage:
    return craft_page(dossier_records(craft_slug, directory=directory))


def dossier_records(craft_slug: str, *, directory: Path = CURATION_DIR) -> CraftPageRecords:
    result = checked_dossier(directory / f"{craft_slug}.json", default_context())
    if result.problems or result.dossier is None or result.check is None:
        lines = (
            "; ".join(problem.line(craft_slug) for problem in result.problems) or "the check file is missing"
        )
        raise InvalidInput(f"the dossier of {craft_slug} does not pass its checks: {lines}")
    return checked_records(result.dossier, result.check)


def preview_page(dossier: Dossier, check: CheckFile) -> CraftPage:
    return craft_page(checked_records(dossier, check))


def checked_records(dossier: Dossier, check: CheckFile) -> CraftPageRecords:
    craft, names = master_craft(dossier.craft_slug)
    target = CraftTarget(id=craft.id, slug=craft.slug, name=craft.name)
    plan = curation_plan(dossier, check, target, load_district_codes())
    return preview_records(plan, craft, names)


def preview_records(
    plan: CurationPlan, craft: Craft, names: tuple[str | None, str | None]
) -> CraftPageRecords:
    views, sources = plan_views(plan)
    cited = cited_claims(list(views.values()), sources)
    districts = sorted(
        {place.district_lgd for place in plan.index.places if place.location_id and place.district_lgd}
    )
    overview = overview_pieces(plan.dossier, cited, craft_id=plan.craft.id, districts=districts)
    refs = {str(key): SourceRef.model_validate(source_ref(row)) for key, row in sources.items()}
    records = CraftPageRecords(
        craft=page_craft(craft, names),
        curated=indexed_overview(plan.index, overview),
        views=tuple(views.values()),
        facts=_facts(plan),
        sources=refs,
        process=_process(plan, craft),
        pieces={piece.id: piece for piece in overview.pieces},
        media={row["id"]: stored_media_ref(MediaRefRow(**row)) for row in plan.part("media")},
    )
    return register_context(records, plan, {})


def plan_views(plan: PlanParts) -> tuple[dict[uuid.UUID, ClaimView], dict[uuid.UUID, Source]]:
    sources = {row["id"]: Source(**row) for row in plan.part("sources")}
    cites: dict[uuid.UUID, list[ClaimSource]] = defaultdict(list)
    for row in plan.part("claimSources"):
        if row["sourceId"] in sources:
            cites[row["claimId"]].append(ClaimSource(**row))
    concept_types = {row["id"]: row["type"] for row in plan.part("concepts")}
    views = {}
    for row in plan.part("claims"):
        if row["status"] == CURATED_STATUS and row["sensitivity"] == OPEN and cites[row["id"]]:
            placed = (row["subjectId"], concept_types[row["subjectId"]])
            views[row["id"]] = cited_view(Claim(**row), cites[row["id"]], placed)
    return views, sources


def _facts(plan: CurationPlan) -> dict[uuid.UUID, ClaimFacts]:
    concepts = {row["id"]: row for row in plan.part("concepts")}
    disciplines = {row["claimId"]: row["discipline"] for row in plan.part("curatedClaims")}
    return {
        row["id"]: ClaimFacts(
            origin=row["origin"],
            sources_differ=row["sourcesDiffer"],
            discipline=disciplines[row["id"]],
            concept_name=concepts[row["subjectId"]]["name"],
            concept_type=concepts[row["subjectId"]]["type"],
        )
        for row in plan.part("claims")
    }


def _concept_claims(plan: CurationPlan) -> dict[uuid.UUID, list[uuid.UUID]]:
    found: dict[uuid.UUID, list[uuid.UUID]] = defaultdict(list)
    for row in plan.part("claims"):
        found[row["subjectId"]].append(row["id"])
    return found


def _process(plan: CurationPlan, craft: Craft) -> ProcessRecords:
    by_concept = _concept_claims(plan)
    materials = {row["id"]: row for row in plan.part("materials")}
    quoted = {row["id"]: row["claimId"] for row in plan.part("claimSources")}
    citations: dict[uuid.UUID, list[tuple[uuid.UUID, str]]] = defaultdict(list)
    for row in plan.part("reactionCitations"):
        citations[row["reactionId"]].append((quoted[row["claimSourceId"]], str(row["claimSourceId"])))
    return ProcessRecords(
        craft=CraftRef.model_validate(craft_ref(craft)),
        processes=tuple(
            ProcessRecord(row["id"], row["name"], row["variant"]) for row in plan.part("processes")
        ),
        stages=tuple(_stage(row, by_concept) for row in plan.part("stages")),
        materials=tuple(
            _material(row, materials[row["materialId"]], by_concept) for row in plan.part("stageMaterials")
        ),
        reactions=tuple(_reaction(row, citations[row["id"]]) for row in plan.part("reactions")),
        conditions=(),
        claims={},
        sources={},
    )


def _stage(row: Mapping[str, Any], by_concept: Mapping[uuid.UUID, list[uuid.UUID]]) -> StageRecord:
    return StageRecord(
        row["id"],
        row["processId"],
        row["ordinal"],
        row["name"],
        row["stageType"],
        tuple(by_concept.get(row["conceptId"], [])),
        ordered=row["ordered"],
    )


def _material(
    use: Mapping[str, Any], material: Mapping[str, Any], by_concept: Mapping[uuid.UUID, list[uuid.UUID]]
) -> MaterialRecord:
    return MaterialRecord(
        id=use["id"],
        stage_id=use["stageId"],
        name=material["name"],
        kind=material["kind"],
        role=use["role"],
        quantity_text=None,
        compound=None,
        claim_ids=(use["claimId"], *by_concept.get(material["conceptId"], [])),
        material_id=material["id"],
        concept_id=material["conceptId"],
    )


def _reaction(row: Mapping[str, Any], citations: list[tuple[uuid.UUID, str]]) -> ReactionRecord:
    return ReactionRecord(
        id=row["id"],
        stage_id=row["stageId"],
        ordinal=row["ordinal"],
        kind=row["kind"],
        label=row["label"],
        species=tuple(SpeciesRecord(s["role"], s["formula"], s["name"], None) for s in row["species"]),
        balanced=row["balanced"],
        coefficients=tuple(row["coefficients"]) if row["coefficients"] else None,
        checker_version=row["checkerVersion"],
        delta_h=None,
        citations=tuple(citations),
    )
