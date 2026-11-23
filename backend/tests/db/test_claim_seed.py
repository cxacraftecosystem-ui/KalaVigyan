from collections import Counter
from typing import Any

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_engine
from app.data.craft_master_loader import seed_plan
from app.models import (
    Claim,
    ClaimSource,
    Concept,
    ConceptEdge,
    Process,
    ProcessStage,
    ReviewEvent,
    Source,
    enums as e,
)
from app.services.claim_seed import claim_seed_plan, load_seed_claims, seed_claims, seed_id
from app.services.craft_seed import seed_crafts

KNOWLEDGE_TABLES = (
    "ReviewEvent",
    "ClaimSource",
    "ProcessStage",
    "Process",
    "ConceptEdge",
    "Claim",
    "Concept",
    "Source",
)
CRAFT_TABLES = ("CraftAlias", "CraftSpelling", "Craft", "CraftCode", "CraftSubCategory", "CraftCategory")

MODELS = {
    "sources": Source,
    "concepts": Concept,
    "edges": ConceptEdge,
    "processes": Process,
    "stages": ProcessStage,
    "claims": Claim,
    "claimSources": ClaimSource,
    "reviewEvents": ReviewEvent,
}


@pytest.fixture(scope="module")
def data() -> dict[str, Any]:
    return load_seed_claims()


def test_plan_counts_match_the_file(data: dict[str, Any]) -> None:
    plan = claim_seed_plan(data)
    assert len(plan["sources"]) == len(data["sources"]) == 122
    assert len(plan["concepts"]) == len(data["concepts"]) == 582
    assert len(plan["edges"]) == len(data["edges"]) == 767
    assert len(plan["claims"]) == len(data["claims"]) == 1914
    assert len(plan["reviewEvents"]) == len(plan["claims"])
    assert len(plan["claimSources"]) == sum(len(row["sources"]) for row in data["claims"])


def test_plan_ids_are_deterministic_and_unique(data: dict[str, Any]) -> None:
    first = claim_seed_plan(data)
    second = claim_seed_plan(data)
    for key, rows in first.items():
        ids = [row["id"] for row in rows]
        assert ids == [row["id"] for row in second[key]]
        assert len(set(ids)) == len(ids), key
    assert first["claims"][0]["id"] == seed_id("claim", data["claims"][0]["id"])


def test_plan_references_resolve(data: dict[str, Any]) -> None:
    plan = claim_seed_plan(data)
    concepts = {row["id"] for row in plan["concepts"]}
    edges = {row["id"] for row in plan["edges"]}
    sources = {row["id"] for row in plan["sources"]}
    claims = {row["id"] for row in plan["claims"]}
    for edge in plan["edges"]:
        assert edge["srcId"] in concepts and edge["dstId"] in concepts
        assert edge["claimId"] is None or edge["claimId"] in claims
    for claim in plan["claims"]:
        assert claim["subjectId"] in (edges if claim["subjectType"] == "EDGE" else concepts)
    for cite in plan["claimSources"]:
        assert cite["sourceId"] in sources and cite["claimId"] in claims
    stage_keys = Counter((row["craftSlug"], row["ordinal"]) for row in plan["stages"])
    assert max(stage_keys.values()) == 1


def test_plan_values_fit_the_schema(data: dict[str, Any]) -> None:
    plan = claim_seed_plan(data)
    assert {row["kind"] for row in plan["sources"]} <= set(e.SOURCE_KINDS)
    assert {row["reliability"] for row in plan["sources"]} <= set(e.RELIABILITIES)
    assert {row["storage"] for row in plan["sources"]} <= set(e.SOURCE_STORAGES)
    assert all(row["evidenceKind"] for row in plan["sources"])
    assert {row["type"] for row in plan["concepts"]} <= set(e.CONCEPT_TYPES)
    assert {row["relation"] for row in plan["edges"]} <= set(e.CONCEPT_RELATIONS)
    assert all(row["sourceRelation"] for row in plan["edges"])
    assert {row["evidenceLevel"] for row in plan["claims"]} <= set(e.EVIDENCE_LEVELS)
    assert {row["status"] for row in plan["claims"]} <= set(e.CLAIM_STATUSES)
    assert {row["quoteCheck"] for row in plan["claimSources"]} <= set(e.QUOTE_CHECKS)
    assert {row["relation"] for row in plan["claimSources"]} <= set(e.SOURCE_RELATIONS)
    assert {row["stageType"] for row in plan["stages"]} <= set(e.STAGE_TYPES)
    events = plan["reviewEvents"]
    assert {(row["actorKind"], row["systemActor"]) for row in events} == {("SYSTEM", "import")}
    assert [row["claimId"] for row in events] == [row["id"] for row in plan["claims"]]


async def _counts(session: AsyncSession) -> dict[str, int]:
    return {
        key: (await session.execute(select(func.count()).select_from(model))).scalar_one()
        for key, model in MODELS.items()
    }


async def _count_where(session: AsyncSession, model: Any, condition: Any) -> int:
    return (await session.execute(select(func.count()).select_from(model).where(condition))).scalar_one()


async def _with_only_the_seeded_crafts(session: AsyncSession) -> None:
    quoted = ", ".join(f'"{name}"' for name in (*KNOWLEDGE_TABLES, *CRAFT_TABLES))
    await session.execute(text(f"TRUNCATE {quoted} CASCADE"))
    await seed_crafts(session, seed_plan())


async def _totals_after_seeding_twice(session: AsyncSession, data: dict[str, Any]) -> dict[str, int]:
    first = await seed_claims(session, data)
    assert first["unresolvedSlugs"] == []
    plan_total = first["total"]
    inserted = first["inserted"]
    for key in ("sources", "concepts", "edges", "claims", "claimSources", "reviewEvents", "stages"):
        assert inserted[key] == plan_total[key], key
    after_first = await _counts(session)
    assert after_first == inserted

    second = await seed_claims(session, data)
    assert set(second["inserted"].values()) == {0}
    assert await _counts(session) == after_first
    return plan_total


async def _review_event_actors(session: AsyncSession) -> list[Any]:
    actors = (ReviewEvent.actorKind, ReviewEvent.systemActor)
    return list((await session.execute(select(*actors, func.count()).group_by(*actors))).all())


@pytest.mark.db
async def test_seed_claims_is_idempotent_on_the_seed_id(data: dict[str, Any]) -> None:
    async with get_engine().connect() as connection:
        transaction = await connection.begin()
        try:
            session = AsyncSession(bind=connection, expire_on_commit=False, autoflush=False)
            await _with_only_the_seeded_crafts(session)
            plan_total = await _totals_after_seeding_twice(session, data)
            assert await _count_where(session, Source, Source.evidenceKind.is_(None)) == 0
            assert await _review_event_actors(session) == [("SYSTEM", "import", plan_total["claims"])]
            linked = await _count_where(session, ConceptEdge, ConceptEdge.claimId.is_not(None))
            assert linked == sum(1 for row in claim_seed_plan(data)["edges"] if row["claimId"])
            crafted = await _count_where(session, Concept, Concept.craftId.is_not(None))
            assert crafted == sum(1 for row in data["concepts"] if row["craftSlug"])
            await session.close()
        finally:
            await transaction.rollback()
