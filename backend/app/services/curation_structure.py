from __future__ import annotations

import uuid
from collections.abc import Sequence
from typing import Any

from app.curation.dossier import Dossier
from app.curation.entities import Place, Reaction as DossierReaction, Species
from app.curation.vocabulary import INDIA
from app.data.craft_text import fold
from app.data.district_register import DistrictCodes
from app.science.reactions import SpeciesProposal, check_reaction

from .curation_keys import (
    CRAFT_LOCATION_ROLES,
    CURATED_PROCESS_NAME,
    CURATED_PROCESS_VARIANT,
    HYPOTHESIS_LEVEL,
    QUOTED_LEVEL,
    TOOL_MATERIAL_KIND,
    TOOL_ROLE,
    curated_id,
)
from .curation_rows import ConceptPlan, CraftTarget, claim_source_id

__all__ = [
    "NAME_NORM_CHARS",
    "REACTION_LABEL_MAX_CHARS",
    "location_rows",
    "material_rows",
    "place_codes",
    "process_row",
    "reaction_citation_rows",
    "reaction_label",
    "reaction_rows",
    "species_label",
    "stage_material_rows",
    "stage_ordinals",
    "stage_rows",
]

NAME_NORM_CHARS = 300
REACTION_LABEL_MAX_CHARS = 200
SPECIES_JOIN = " + "
REACTION_ARROW = " → "


def place_codes(place: Place, codes: DistrictCodes) -> tuple[int | None, int | None]:
    if place.country != INDIA or place.state is None:
        return None, None
    district = codes.district_lgd(place.state, place.district) if place.district else None
    return codes.state_lgd(place.state), district


def location_rows(dossier: Dossier, craft: CraftTarget, codes: DistrictCodes) -> list[dict[str, Any]]:
    claims = {claim.id: claim for claim in dossier.claims}
    rows = []
    for place in dossier.places:
        state_lgd, district_lgd = place_codes(place, codes)
        precision = _precision(place, state_lgd, district_lgd)
        if place.role not in CRAFT_LOCATION_ROLES or precision is None:
            continue
        stating = [claims[claim_id] for claim_id in place.claim_ids]
        guessed = all(claim.hypothesis for claim in stating)
        rows.append(
            {
                "id": curated_id(dossier.craft_slug, "location", place.id),
                "craftId": craft.id,
                "precision": precision,
                "stateLgd": state_lgd,
                "districtLgd": district_lgd if precision == "DISTRICT" else None,
                "placeLabel": place.name,
                "sourceId": curated_id(dossier.craft_slug, stating[0].quotes[0].source_id),
                "evidenceLevel": HYPOTHESIS_LEVEL if guessed else QUOTED_LEVEL,
                "role": place.role,
            }
        )
    return rows


def _precision(place: Place, state_lgd: int | None, district_lgd: int | None) -> str | None:
    if state_lgd is None:
        return None
    if district_lgd is not None:
        return "DISTRICT"
    return "STATE" if place.kind == "STATE" else None


def process_row(dossier: Dossier, craft: CraftTarget) -> dict[str, Any] | None:
    if not dossier.stages:
        return None
    return {
        "id": curated_id(dossier.craft_slug, "process"),
        "craftId": craft.id,
        "name": CURATED_PROCESS_NAME,
        "variant": CURATED_PROCESS_VARIANT,
        "archivedAt": None,
    }


def stage_ordinals(dossier: Dossier) -> dict[str, int]:
    ordinals = {stage.id: stage.order for stage in dossier.stages if stage.order is not None}
    following = max(ordinals.values(), default=0)
    for stage in dossier.stages:
        if stage.order is None:
            following += 1
            ordinals[stage.id] = following
    return ordinals


def stage_rows(dossier: Dossier, concepts: ConceptPlan) -> list[dict[str, Any]]:
    slug = dossier.craft_slug
    ordinals = stage_ordinals(dossier)
    return [
        {
            "id": curated_id(slug, "stage", stage.id),
            "processId": curated_id(slug, "process"),
            "ordinal": ordinals[stage.id],
            "ordered": stage.order is not None,
            "conceptId": concepts.ids[stage.id],
            "name": stage.name,
            "stageType": stage.stage_type,
            "durationText": stage.duration.text if stage.duration else None,
        }
        for stage in dossier.stages
    ]


def material_rows(dossier: Dossier, concepts: ConceptPlan) -> list[dict[str, Any]]:
    slug = dossier.craft_slug
    rows = [
        _material(curated_id(slug, "material", item.id), item.name, item.kind, concepts.ids[item.id])
        for item in dossier.materials
    ]
    rows += [
        _material(curated_id(slug, "tool", item.id), item.name, TOOL_MATERIAL_KIND, concepts.ids[item.id])
        for item in dossier.tools
    ]
    return rows


def _material(material_id: uuid.UUID, name: str, kind: str, concept_id: uuid.UUID) -> dict[str, Any]:
    return {
        "id": material_id,
        "name": name,
        "nameNorm": fold(name)[:NAME_NORM_CHARS],
        "kind": kind,
        "conceptId": concept_id,
        "compoundId": None,
    }


def stage_material_rows(dossier: Dossier) -> list[dict[str, Any]]:
    slug = dossier.craft_slug
    roles = {item.id: item.role for item in dossier.materials}
    rows: dict[uuid.UUID, dict[str, Any]] = {}
    for stage in dossier.stages:
        uses = [
            ("stage-material", "material", use.material_id, roles[use.material_id], use.claim_id)
            for use in stage.materials
        ]
        uses += [("stage-tool", "tool", use.tool_id, TOOL_ROLE, use.claim_id) for use in stage.tools]
        for prefix, kind, item_id, role, claim_id in uses:
            row_id = curated_id(slug, prefix, stage.id, item_id)
            rows.setdefault(
                row_id,
                {
                    "id": row_id,
                    "stageId": curated_id(slug, "stage", stage.id),
                    "materialId": curated_id(slug, kind, item_id),
                    "role": role,
                    "quantityText": None,
                    "claimId": curated_id(slug, claim_id),
                },
            )
    return list(rows.values())


def reaction_label(reaction: DossierReaction) -> str:
    return species_label(
        reaction.kind, [item.name for item in reaction.reactants], [item.name for item in reaction.products]
    )


def species_label(kind: str, reactants: Sequence[str], products: Sequence[str]) -> str:
    made = SPECIES_JOIN.join(products)
    for label in (f"{SPECIES_JOIN.join(reactants)}{REACTION_ARROW}{made}", made):
        if len(label) <= REACTION_LABEL_MAX_CHARS:
            return label
    return f"{kind.replace('_', ' ').capitalize()} reaction"


def reaction_rows(dossier: Dossier) -> list[dict[str, Any]]:
    slug = dossier.craft_slug
    seen: dict[str, int] = {}
    rows = []
    for reaction in dossier.reactions:
        if reaction.stage_id is None:
            continue
        ordinal = seen.get(reaction.stage_id, 0)
        seen[reaction.stage_id] = ordinal + 1
        species = [*_species("REACTANT", reaction.reactants), *_species("PRODUCT", reaction.products)]
        checked = check_reaction([SpeciesProposal(s["role"], s["formula"], s["name"]) for s in species])
        rows.append(
            {
                "id": curated_id(slug, "reaction", reaction.id),
                "stageId": curated_id(slug, "stage", reaction.stage_id),
                "ordinal": ordinal,
                "kind": reaction.kind,
                "label": reaction_label(reaction),
                "species": species,
                "equationInput": checked.equation_input,
                "equationBalanced": checked.equation_balanced,
                "coefficients": list(checked.coefficients) if checked.coefficients else None,
                "balanced": checked.balanced,
                "checkerVersion": checked.checker_version,
            }
        )
    return rows


def _species(role: str, species: list[Species]) -> list[dict[str, Any]]:
    return [
        {"role": role, "formula": item.formula, "name": item.name, "compoundId": None} for item in species
    ]


def reaction_citation_rows(dossier: Dossier) -> list[dict[str, Any]]:
    slug = dossier.craft_slug
    claims = {claim.id: claim for claim in dossier.claims}
    rows: dict[uuid.UUID, dict[str, Any]] = {}
    for reaction in dossier.reactions:
        if reaction.stage_id is None:
            continue
        reaction_id = curated_id(slug, "reaction", reaction.id)
        for claim_id in reaction.claim_ids:
            for quote in claims[claim_id].quotes:
                cited = claim_source_id(slug, claim_id, quote.source_id, quote.quote)
                row_id = curated_id(slug, "reaction-citation", reaction.id, str(cited))
                rows.setdefault(row_id, {"id": row_id, "reactionId": reaction_id, "claimSourceId": cited})
    return list(rows.values())
