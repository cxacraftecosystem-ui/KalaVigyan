import uuid
from dataclasses import dataclass
from functools import cache
from typing import Any

from app.models import (
    ClaimSource,
    Compound,
    ConditionReading,
    Material,
    Process,
    ProcessCondition,
    ProcessStage,
    Reaction,
    ReactionCitation,
    Source,
    StageMaterial,
)
from app.research.citations import Citation, SourceRef
from app.research.crafts import CraftRef
from app.science.reactions import SpeciesProposal, check_reaction
from app.science.records import (
    ConditionRecord,
    KnownClaim,
    MaterialRecord,
    ProcessRecord,
    ProcessRecords,
    ReactionRecord,
    ReadingRecord,
    SpeciesRecord,
    StageRecord,
)
from app.services.claim_seed import (
    claim_row,
    claim_source_rows,
    load_seed_claims,
    seed_id,
    source_row,
)
from app.services.knowledge_view import citation, source_ref

GOLDEN = "science.process.golden.json"
CRAFT = CraftRef(slug="Kutch-Ajrakh", name="Kutch Ajrakh", path="/crafts/Kutch-Ajrakh")
PROCESS_ID = seed_id("process", "Kutch-Ajrakh")
KUT, PA, RED = (
    "ie:ajrakh.process_stage.kut",
    "ie:ajrakh.process_stage.pa",
    "ie:ajrakh.process_stage.red-dyeing",
)
STAGES = (
    (KUT, 5, "Kut (iron-black printing)", "PRINT"),
    (PA, 6, "Pa (alum mordant printing for red)", "MORDANT"),
    (RED, 11, "Red dyeing (rang) with madder or alizarin", "DYE"),
)
STAGE_CLAIMS = {
    KUT: "seed-f1dacf07b4072a459cb5",
    PA: "seed-d9873cde3faa1e45c9c4",
    RED: "seed-b14a93745f3a652197c0",
}
LEFT_OUT_OF_THE_EXCERPT = (
    "seed-116b395b80705f3ff151",
    "seed-9c37c7c9b43a354a51a1",
    "seed-03864cb3c264079f0e1b",
)
IRON_ACETATE = uuid.UUID("8bb3d4e7-5fc1-5685-9b72-8279a0449481")
ALIZARIN = uuid.UUID("611c6249-947c-52e8-a8ae-f916a0be4ab2")


@dataclass(frozen=True)
class MaterialSpec:
    id: str
    stage: str
    name: str
    kind: str
    claim: str


@dataclass(frozen=True)
class ReactionSpec:
    id: str
    stage: str
    kind: str
    label: str
    species: tuple[tuple[str, str | None, str, uuid.UUID | None], ...]
    citations: tuple[tuple[str, int], ...]


@dataclass(frozen=True)
class ConditionSpec:
    stage: str
    label: str
    readings: tuple[tuple[str, int, str, float | None, float | None, str], ...]


MATERIALS = (
    MaterialSpec(
        "6a3e5cb8-ef2e-501f-a7f8-d7d0772d56e4",
        KUT,
        "Kut (iron-water black paste)",
        "MORDANT",
        "seed-ca39189df4e04dcb5a7a",
    ),
    MaterialSpec(
        "e2c65ac5-52a9-5625-9ed7-ce0d1c1cb19c", PA, "Alum (fatakdi)", "MORDANT", "seed-3b6ee85c9270e4102746"
    ),
    MaterialSpec(
        "a96fc53e-88ae-5f99-acd3-09346d9a67ea",
        RED,
        "Indian madder (majith/majeeta, Rubia cordifolia)",
        "DYE",
        "seed-bd5ef6022d643b22c6dd",
    ),
)
REACTIONS = (
    ReactionSpec(
        "d9643f49-fefc-5e3a-ad08-a5ae499a4161",
        KUT,
        "REDOX",
        "Scrap iron dissolving into iron acetate",
        (
            ("REACTANT", "Fe", "Iron", None),
            ("REACTANT", "CH3COOH", "Acetic acid", None),
            ("PRODUCT", "Fe(CH3COO)2", "Iron(II) acetate", IRON_ACETATE),
            ("PRODUCT", "H2", "Hydrogen", None),
        ),
        (("seed-e1a28b32e2c7416ebed3", 0), ("seed-ca39189df4e04dcb5a7a", 0)),
    ),
    ReactionSpec(
        "26229ecd-184c-5adf-86d0-b45c56394f27",
        RED,
        "COMPLEXATION",
        "Alizarin binding to the alum mordant",
        (
            ("REACTANT", "Al^3+", "Aluminium from the alum mordant", None),
            ("REACTANT", "C14H8O4", "Alizarin", ALIZARIN),
            ("PRODUCT", None, "Aluminium-alizarin lake", None),
        ),
        (("seed-b14a93745f3a652197c0", 0), ("seed-bd5ef6022d643b22c6dd", 0)),
    ),
)
CONDITIONS = (
    ConditionSpec(
        KUT,
        "Fermenting the iron paste",
        (
            ("seed-ca39189df4e04dcb5a7a", 0, "ten to fifteen days", 10, 15, "day"),
            ("seed-d124d09b6ccdc13459f6", 0, "two weeks", 2, 2, "week"),
        ),
    ),
    ConditionSpec(
        RED, "Red dye bath", (("seed-b14a93745f3a652197c0", 1, "up to four hours", None, 4, "hour"),)
    ),
)
COMPOUNDS = ((IRON_ACETATE, "Iron(II) acetate", "Fe(CH3COO)2"), (ALIZARIN, "Alizarin", "C14H8O4"))


def key(name: str) -> uuid.UUID:
    return uuid.uuid5(uuid.NAMESPACE_URL, f"test-process/{name}")


def stage_id(stage: str) -> uuid.UUID:
    return seed_id("stage", stage)


def claim_id(claim: str) -> uuid.UUID:
    return seed_id("claim", claim)


def citation_id(claim: str, index: int) -> uuid.UUID:
    return seed_id("claim-source", f"{claim}:{index}")


def checked(spec: ReactionSpec) -> Any:
    return check_reaction([SpeciesProposal(role, formula, name) for role, formula, name, _ in spec.species])


@cache
def seed_rows() -> dict[str, Any]:
    data = load_seed_claims()
    return {
        "claims": {row["id"]: row for row in data["claims"]},
        "sources": {row["id"]: source_row(row) for row in data["sources"]},
    }


def known_claim(claim: str) -> KnownClaim:
    row = seed_rows()["claims"][claim]
    stored = claim_row(row)
    cites = [ClaimSource(**cite) for cite in claim_source_rows(row)]
    cites.sort(key=lambda c: (c.quote is None, str(c.id)))
    return KnownClaim(
        id=stored["id"],
        text=stored["text"],
        level=stored["evidenceLevel"],
        citations=tuple(Citation.model_validate(citation(c, stored["evidenceLevel"])) for c in cites),
    )


def known_source(source_key: str) -> SourceRef:
    return SourceRef.model_validate(source_ref(Source(**seed_rows()["sources"][source_key])))


def golden_records() -> ProcessRecords:
    claims = {STAGE_CLAIMS[s] for s, *_ in STAGES} | {m.claim for m in MATERIALS}
    claims |= {c for r in REACTIONS for c, _ in r.citations} | {r[0] for c in CONDITIONS for r in c.readings}
    known = {claim_id(c): known_claim(c) for c in claims}
    sources = {str(seed_id("source", k)): known_source(k) for k in seed_rows()["sources"]}
    return ProcessRecords(
        craft=CRAFT,
        processes=(ProcessRecord(PROCESS_ID, "Seed process", "seed_claims"),),
        stages=tuple(
            StageRecord(stage_id(s), PROCESS_ID, ordinal, name, kind, (claim_id(STAGE_CLAIMS[s]),))
            for s, ordinal, name, kind in STAGES
        ),
        materials=tuple(_material_record(m) for m in MATERIALS),
        reactions=tuple(_reaction_record(r) for r in REACTIONS),
        conditions=tuple(_condition_record(c) for c in CONDITIONS),
        claims=known,
        sources=sources,
    )


def _material_record(spec: MaterialSpec) -> MaterialRecord:
    return MaterialRecord(
        uuid.UUID(spec.id),
        stage_id(spec.stage),
        spec.name,
        spec.kind,
        spec.kind,
        None,
        None,
        (claim_id(spec.claim),),
    )


def _reaction_record(spec: ReactionSpec) -> ReactionRecord:
    result = checked(spec)
    return ReactionRecord(
        id=uuid.UUID(spec.id),
        stage_id=stage_id(spec.stage),
        ordinal=1,
        kind=spec.kind,
        label=spec.label,
        species=tuple(
            SpeciesRecord(role, formula, name, compound) for role, formula, name, compound in spec.species
        ),
        balanced=result.balanced,
        coefficients=result.coefficients,
        checker_version=result.checker_version,
        delta_h=None,
        citations=tuple((claim_id(c), str(citation_id(c, i))) for c, i in spec.citations),
    )


def _condition_record(spec: ConditionSpec) -> ConditionRecord:
    return ConditionRecord(
        owner_id=stage_id(spec.stage),
        key="duration",
        label=spec.label,
        quantity="DURATION",
        readings=tuple(
            ReadingRecord(claim_id(c), str(citation_id(c, i)), stated, low, high, unit)
            for c, i, stated, low, high, unit in spec.readings
        ),
    )


def golden_rows(craft_id: uuid.UUID) -> list[Any]:
    rows: list[Any] = [Process(id=PROCESS_ID, craftId=craft_id, name="Seed process", variant="seed_claims")]
    rows += [
        ProcessStage(
            id=stage_id(s),
            processId=PROCESS_ID,
            ordinal=o,
            conceptId=seed_id("concept", s),
            name=n,
            stageType=t,
        )
        for s, o, n, t in STAGES
    ]
    rows += [Compound(id=i, name=n, formula=f) for i, n, f in COMPOUNDS]
    for spec in MATERIALS:
        rows.append(Material(id=key(spec.id), name=spec.name, nameNorm=f"test {spec.id}", kind=spec.kind))
        rows.append(
            StageMaterial(
                id=uuid.UUID(spec.id),
                stageId=stage_id(spec.stage),
                materialId=key(spec.id),
                role=spec.kind,
                claimId=claim_id(spec.claim),
            )
        )
    for spec in REACTIONS:
        rows += _reaction_rows(spec)
    for spec in CONDITIONS:
        rows += _condition_rows(spec)
    return rows


def _reaction_rows(spec: ReactionSpec) -> list[Any]:
    result = checked(spec)
    species = [
        {"role": r, "formula": f, "name": n, "compoundId": str(c) if c else None}
        for r, f, n, c in spec.species
    ]
    reaction = Reaction(
        id=uuid.UUID(spec.id),
        stageId=stage_id(spec.stage),
        ordinal=1,
        kind=spec.kind,
        label=spec.label,
        species=species,
        coefficients=list(result.coefficients) if result.coefficients else None,
        balanced=result.balanced,
        checkerVersion=result.checker_version,
    )
    links = [
        ReactionCitation(
            id=key(f"{spec.id}:{c}:{i}"), reactionId=uuid.UUID(spec.id), claimSourceId=citation_id(c, i)
        )
        for c, i in spec.citations
    ]
    return [reaction, *links]


def _condition_rows(spec: ConditionSpec) -> list[Any]:
    condition = ProcessCondition(
        id=key(f"condition:{spec.stage}"),
        stageId=stage_id(spec.stage),
        key="duration",
        label=spec.label,
        quantity="DURATION",
    )
    readings = [
        ConditionReading(
            id=key(f"reading:{c}:{i}"),
            conditionId=condition.id,
            claimSourceId=citation_id(c, i),
            stated=stated,
            statedMin=low,
            statedMax=high,
            statedUnit=unit,
        )
        for c, i, stated, low, high, unit in spec.readings
    ]
    return [condition, *readings]
