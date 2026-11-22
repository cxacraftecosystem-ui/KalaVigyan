from __future__ import annotations

import json
import uuid
from collections.abc import Mapping
from dataclasses import dataclass, field
from itertools import batched
from pathlib import Path
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import InvalidInput
from app.data.craft_master_loader import DATA_DIR
from app.data.craft_text import fold
from app.models import (
    Compound,
    ConditionReading,
    Material,
    ProcessCondition,
    ProcessStage,
    Reaction,
    ReactionCitation,
    StageMaterial,
)
from app.science.reactions import SpeciesProposal, check_reaction
from app.science.units import Bounds, normalised_bounds
from app.services.claim_seed import load_seed_claims, seed_claims, seed_id, stage_rows

__all__ = [
    "SCIENCE_SEED_FILE",
    "SciencePlan",
    "constants_data",
    "load_science_seed",
    "science_seed_plan",
    "seed_science",
]

SCIENCE_SEED_FILE = DATA_DIR / "science_seed.json"
BATCH = 500
SEED_ORDER = (
    ("compounds", Compound),
    ("materials", Material),
    ("stageMaterials", StageMaterial),
    ("reactions", Reaction),
    ("reactionCitations", ReactionCitation),
    ("conditions", ProcessCondition),
    ("readings", ConditionReading),
)
STAGE_BOUND = ("stageMaterials", "reactions", "conditions")
KEPT_WHEN_UNSEEDED = {"compounds": ("pubchemCid",)}


@dataclass(frozen=True)
class _SeedClaims:
    claims: Mapping[str, dict[str, Any]]
    concepts: Mapping[str, dict[str, Any]]
    stages: Mapping[str, uuid.UUID]
    edge_claims: Mapping[str, str]
    uses: tuple[dict[str, Any], ...]

    @classmethod
    def of(cls, data: dict[str, Any]) -> _SeedClaims:
        concepts = {concept["key"]: concept for concept in data.get("concepts") or []}
        seeded = {row["id"] for row in stage_rows(list(concepts.values()))}
        stages = {key: seed_id("stage", key) for key in concepts if seed_id("stage", key) in seeded}
        edge_claims: dict[str, str] = {}
        for claim in data.get("claims") or []:
            if claim["subjectType"] == "EDGE":
                edge_claims.setdefault(claim["subjectKey"], claim["id"])
        uses = tuple(
            edge
            for edge in data.get("edges") or []
            if edge["relation"] == "USES"
            and edge["src"] in stages
            and concepts.get(edge["dst"], {}).get("type") == "MATERIAL"
        )
        return cls(
            claims={claim["id"]: claim for claim in data.get("claims") or []},
            concepts=concepts,
            stages=stages,
            edge_claims=edge_claims,
            uses=uses,
        )

    def stage(self, key: str) -> uuid.UUID:
        if key not in self.stages:
            raise InvalidInput(f"{key} is not a seeded process stage")
        return self.stages[key]

    def citation(self, claim_key: str, index: int) -> dict[str, Any]:
        claim = self.claims.get(claim_key)
        cites = (claim or {}).get("sources") or []
        if not 0 <= index < len(cites):
            raise InvalidInput(f"seed claim {claim_key} has no citation {index}")
        return cites[index]


@dataclass
class SciencePlan:
    rows: dict[str, list[dict[str, Any]]] = field(
        default_factory=lambda: {name: [] for name, _ in SEED_ORDER}
    )

    def totals(self) -> dict[str, int]:
        return {name: len(rows) for name, rows in self.rows.items()}


def load_science_seed(path: Path | None = None) -> dict[str, Any]:
    return json.loads((path or SCIENCE_SEED_FILE).read_text(encoding="utf-8"))


def constants_data(science: dict[str, Any]) -> dict[str, Any]:
    constants = science["constants"]
    return {
        "sources": constants["sources"],
        "concepts": constants["concepts"],
        "edges": [],
        "claims": [{k: v for k, v in claim.items() if k != "constant"} for claim in constants["claims"]],
    }


def science_seed_plan(science: dict[str, Any], claims_data: dict[str, Any]) -> SciencePlan:
    seed = _SeedClaims.of(claims_data)
    plan = SciencePlan()
    compounds = {row["key"]: seed_id("compound", row["key"]) for row in science["compounds"]}
    plan.rows["compounds"] = [
        {
            "id": compounds[row["key"]],
            "name": row["name"],
            "formula": row["formula"],
            "pubchemCid": row.get("pubchemCid"),
        }
        for row in science["compounds"]
    ]
    _plan_materials(plan, seed, science["materials"], compounds)
    for reaction in science["reactions"]:
        _plan_reaction(plan, seed, reaction, compounds)
    for condition in science["conditions"]:
        _plan_condition(plan, seed, condition)
    return plan


async def seed_science(
    session: AsyncSession, science: dict[str, Any] | None = None, claims_data: dict[str, Any] | None = None
) -> dict[str, Any]:
    science = science if science is not None else load_science_seed()
    plan = science_seed_plan(science, claims_data if claims_data is not None else load_seed_claims())
    constants = await seed_claims(session, constants_data(science))
    present = set((await session.scalars(select(ProcessStage.id))).all())
    skipped = _drop_missing_stages(plan, present)
    written = {
        name: await _upsert(session, model, plan.rows[name], KEPT_WHEN_UNSEEDED.get(name, ()))
        for name, model in SEED_ORDER
    }
    await session.flush()
    return {"constants": constants, "total": plan.totals(), "written": written, "skippedRows": skipped}


def _plan_materials(
    plan: SciencePlan, seed: _SeedClaims, kinds: Mapping[str, Any], compounds: Mapping[str, uuid.UUID]
) -> None:
    for edge in seed.uses:
        key = edge["dst"]
        if key not in kinds:
            raise InvalidInput(f"material {key} has no kind and role in the science seed")
        known = kinds[key]
        material_id = seed_id("material", key)
        if material_id not in {row["id"] for row in plan.rows["materials"]}:
            plan.rows["materials"].append(_material_row(seed.concepts[key], known, compounds))
        claim_key = seed.edge_claims.get(edge["key"])
        plan.rows["stageMaterials"].append(
            {
                "id": seed_id("stage-material", edge["key"]),
                "stageId": seed.stage(edge["src"]),
                "materialId": material_id,
                "role": known["role"],
                "quantityText": None,
                "claimId": seed_id("claim", claim_key) if claim_key else None,
            }
        )


def _material_row(
    concept: dict[str, Any], known: Mapping[str, Any], compounds: Mapping[str, uuid.UUID]
) -> dict[str, Any]:
    compound = known.get("compound")
    if compound is not None and compound not in compounds:
        raise InvalidInput(f"material {concept['key']} names unknown compound {compound}")
    name = str(concept["name"])[:300]
    return {
        "id": seed_id("material", concept["key"]),
        "name": name,
        "nameNorm": fold(name)[:300],
        "kind": known["kind"],
        "conceptId": seed_id("concept", concept["key"]),
        "compoundId": compounds[compound] if compound else None,
    }


def _plan_reaction(
    plan: SciencePlan, seed: _SeedClaims, reaction: dict[str, Any], compounds: Mapping[str, uuid.UUID]
) -> None:
    proposals = [SpeciesProposal(s["role"], s["formula"], s["name"]) for s in reaction["species"]]
    checked = check_reaction(proposals)
    reaction_id = seed_id("reaction", f"{reaction['stage']}:{reaction['key']}")
    plan.rows["reactions"].append(
        {
            "id": reaction_id,
            "stageId": seed.stage(reaction["stage"]),
            "ordinal": reaction["ordinal"],
            "kind": reaction["kind"],
            "label": reaction["label"],
            "species": [_species_json(s, compounds) for s in reaction["species"]],
            "equationInput": checked.equation_input,
            "equationBalanced": checked.equation_balanced,
            "coefficients": list(checked.coefficients) if checked.coefficients else None,
            "balanced": checked.balanced,
            "checkerVersion": checked.checker_version,
        }
    )
    for claim_key, index in reaction["citations"]:
        seed.citation(claim_key, index)
        plan.rows["reactionCitations"].append(
            {
                "id": seed_id("reaction-citation", f"{reaction_id}:{claim_key}:{index}"),
                "reactionId": reaction_id,
                "claimSourceId": seed_id("claim-source", f"{claim_key}:{index}"),
            }
        )


def _species_json(species: Mapping[str, Any], compounds: Mapping[str, uuid.UUID]) -> dict[str, Any]:
    compound = species.get("compound")
    if compound is not None and compound not in compounds:
        raise InvalidInput(f"species {species.get('name')} names unknown compound {compound}")
    return {
        "role": species["role"],
        "formula": species["formula"],
        "name": species["name"],
        "compoundId": str(compounds[compound]) if compound else None,
    }


def _plan_condition(plan: SciencePlan, seed: _SeedClaims, condition: dict[str, Any]) -> None:
    owner = f"{condition['stage']}:{condition['key']}"
    condition_id = seed_id("condition", owner)
    plan.rows["conditions"].append(
        {
            "id": condition_id,
            "stageId": seed.stage(condition["stage"]),
            "reactionId": None,
            "key": condition["key"],
            "label": condition["label"],
            "quantity": condition["quantity"],
        }
    )
    for reading in condition["readings"]:
        _check_reading(seed, condition["quantity"], reading)
        plan.rows["readings"].append(
            {
                "id": seed_id("reading", f"{owner}:{reading['claim']}:{reading['citation']}"),
                "conditionId": condition_id,
                "claimSourceId": seed_id("claim-source", f"{reading['claim']}:{reading['citation']}"),
                "stated": reading["stated"],
                "statedMin": reading["min"],
                "statedMax": reading["max"],
                "statedUnit": reading["unit"],
            }
        )


def _check_reading(seed: _SeedClaims, quantity: str, reading: Mapping[str, Any]) -> None:
    cite = seed.citation(reading["claim"], reading["citation"])
    normalised_bounds(quantity, Bounds(reading["min"], reading["max"]), reading["unit"])
    stated = fold(reading["stated"])
    said = (fold(seed.claims[reading["claim"]]["text"]), fold(cite.get("quote")))
    if not stated or not any(stated in text for text in said):
        raise InvalidInput(f"{reading['stated']!r} is not said by seed claim {reading['claim']}")


def _drop_missing_stages(plan: SciencePlan, present: set[uuid.UUID]) -> int:
    before = sum(len(rows) for rows in plan.rows.values())
    for name in STAGE_BOUND:
        plan.rows[name] = [row for row in plan.rows[name] if row["stageId"] in present]
    reactions = {row["id"] for row in plan.rows["reactions"]}
    conditions = {row["id"] for row in plan.rows["conditions"]}
    plan.rows["reactionCitations"] = [
        r for r in plan.rows["reactionCitations"] if r["reactionId"] in reactions
    ]
    plan.rows["readings"] = [r for r in plan.rows["readings"] if r["conditionId"] in conditions]
    return before - sum(len(rows) for rows in plan.rows.values())


async def _upsert(
    session: AsyncSession, model: Any, rows: list[dict[str, Any]], kept: tuple[str, ...] = ()
) -> int:
    for chunk in batched(rows, BATCH, strict=False):
        statement = insert(model).values(list(chunk))
        changed = {
            key: func.coalesce(statement.excluded[key], getattr(model, key))
            if key in kept
            else statement.excluded[key]
            for key in chunk[0]
            if key != "id"
        }
        await session.execute(statement.on_conflict_do_update(index_elements=["id"], set_=changed))
    return len(rows)
