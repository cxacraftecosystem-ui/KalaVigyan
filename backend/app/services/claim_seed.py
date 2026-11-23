import json
import uuid
from datetime import UTC, datetime
from itertools import batched
from pathlib import Path
from typing import Any

from sqlalchemy import bindparam, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.data.craft_master_loader import ID_NAMESPACE, SEED_CLAIMS_FILE
from app.models import (
    Claim,
    ClaimSource,
    Concept,
    ConceptEdge,
    Craft,
    CraftSubCategory,
    Process,
    ProcessStage,
    ReviewEvent,
    Source,
)
from app.models.knowledge import QUOTE_MAX_CHARS
from app.research.vocabulary import CONCEPT_TYPE_DISCIPLINES
from app.services.craft_seed import ids_by_slug

BATCH = 500
SYSTEM_ACTOR = "import"
IMPORT_ORIGIN = "IMPORT"
SEED_PROCESS_NAME = "Seed process"
SEED_PROCESS_VARIANT = "seed_claims"
IMPORT_NOTE = "seed import"


def seed_id(kind: str, key: str) -> uuid.UUID:
    return uuid.uuid5(ID_NAMESPACE, f"seed-claims:{kind}:{key}")


def load_seed_claims(path: Path | None = None) -> dict[str, Any]:
    return json.loads((path or SEED_CLAIMS_FILE).read_text(encoding="utf-8"))


def _date(value: Any) -> datetime | None:
    if not value:
        return None
    parsed = datetime.fromisoformat(str(value))
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def _clip(value: Any, limit: int) -> str | None:
    return None if value is None else str(value)[:limit]


def source_row(row: dict[str, Any]) -> dict[str, Any]:
    external = {"seedId": row["id"]}
    if row.get("importRef"):
        external["importRef"] = row["importRef"]
    return {
        "id": seed_id("source", row["id"]),
        "kind": row["kind"],
        "title": row["title"],
        "authors": list(row.get("authors") or []),
        "year": row.get("year"),
        "doi": _clip(row.get("doi"), 255),
        "url": row.get("url"),
        "publisher": _clip(row.get("publisher"), 300),
        "licence": _clip(row.get("licence"), 200),
        "reliability": row.get("reliability") or "C",
        "storage": row.get("storage") or "LINK_ONLY",
        "retrievedAt": _date(row.get("retrievedAt")),
        "origin": row.get("origin") or "IMPORT",
        "sensitivity": row.get("sensitivity") or "OPEN",
        "attribution": row.get("attribution"),
        "evidenceKind": _clip(row.get("evidenceKind"), 80),
        "notes": row.get("notes"),
        "externalIds": external,
    }


def concept_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": seed_id("concept", row["key"]),
        "craftSlug": row.get("craftSlug"),
        "subCategorySlug": row.get("subCategorySlug"),
        "type": row["type"],
        "name": str(row["name"])[:300],
        "description": row.get("description"),
        "originRef": row["key"],
        "sensitivity": row.get("sensitivity") or "OPEN",
    }


def edge_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": seed_id("edge", row["key"]),
        "srcId": seed_id("concept", row["src"]),
        "dstId": seed_id("concept", row["dst"]),
        "relation": row["relation"],
        "sourceRelation": _clip(row.get("sourceRelation"), 80),
    }


def claim_row(row: dict[str, Any]) -> dict[str, Any]:
    kind = "edge" if row["subjectType"] == "EDGE" else "concept"
    return {
        "id": seed_id("claim", row["id"]),
        "subjectType": row["subjectType"],
        "subjectId": seed_id(kind, row["subjectKey"]),
        "predicate": str(row["predicate"])[:120],
        "text": row["text"],
        "textLang": row.get("textLang") or "en",
        "evidenceLevel": row["evidenceLevel"],
        "levelReason": row.get("levelReason"),
        "origin": row.get("origin") or "IMPORT",
        "status": row.get("status") or "PROPOSED",
        "createdByKind": row.get("createdByKind") or "SYSTEM",
        "sensitivity": row.get("sensitivity") or "OPEN",
    }


def seed_field(row: dict[str, Any], concept_types: dict[str, str]) -> str | None:
    if row["subjectType"] != "CONCEPT":
        return None
    return CONCEPT_TYPE_DISCIPLINES.get(concept_types.get(row["subjectKey"], ""))


def claim_source_rows(row: dict[str, Any]) -> list[dict[str, Any]]:
    claim_id = seed_id("claim", row["id"])
    return [
        {
            "id": seed_id("claim-source", f"{row['id']}:{index}"),
            "claimId": claim_id,
            "sourceId": seed_id("source", cite["sourceId"]),
            "locator": _clip(cite.get("locator"), 300),
            "quote": _clip(cite.get("quote"), QUOTE_MAX_CHARS),
            "quoteCheck": cite.get("quoteCheck") or "NA",
            "relation": cite.get("relation") or "DIRECT",
        }
        for index, cite in enumerate(row.get("sources") or [])
    ]


def review_event_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": seed_id("review-event", row["id"]),
        "claimId": seed_id("claim", row["id"]),
        "actorId": None,
        "actorKind": "SYSTEM",
        "systemActor": row.get("systemActor") or SYSTEM_ACTOR,
        "fromStatus": None,
        "toStatus": row.get("status") or "PROPOSED",
        "fromLevel": None,
        "toLevel": row["evidenceLevel"],
        "note": f"{IMPORT_NOTE} {row['id']}",
    }


def stage_rows(concepts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for concept in concepts:
        stage = concept.get("stage")
        if not stage or not concept.get("craftSlug") or stage.get("ordinal") is None:
            continue
        rows.append(
            {
                "id": seed_id("stage", concept["key"]),
                "craftSlug": concept["craftSlug"],
                "ordinal": int(stage["ordinal"]),
                "conceptId": seed_id("concept", concept["key"]),
                "name": str(stage.get("title") or concept["name"])[:300],
                "stageType": stage.get("stageType") or "OTHER",
            }
        )
    return rows


def claim_seed_plan(data: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    claims = data.get("claims") or []
    edge_claim: dict[uuid.UUID, uuid.UUID] = {}
    for row in claims:
        if row["subjectType"] == "EDGE":
            edge_claim.setdefault(seed_id("edge", row["subjectKey"]), seed_id("claim", row["id"]))
    edges = [edge_row(row) for row in data.get("edges") or []]
    concept_types = {row["key"]: row["type"] for row in data.get("concepts") or []}
    for edge in edges:
        edge["claimId"] = edge_claim.get(edge["id"])
    return {
        "sources": [source_row(row) for row in data.get("sources") or []],
        "concepts": [concept_row(row) for row in data.get("concepts") or []],
        "edges": edges,
        "stages": stage_rows(data.get("concepts") or []),
        "claims": [claim_row(row) | {"field": seed_field(row, concept_types)} for row in claims],
        "claimSources": [cite for row in claims for cite in claim_source_rows(row)],
        "reviewEvents": [review_event_row(row) for row in claims],
    }


async def _insert_new(session: AsyncSession, model: Any, rows: list[dict[str, Any]]) -> int:
    inserted = 0
    for chunk in batched(rows, BATCH, strict=False):
        result = await session.execute(
            insert(model).values(list(chunk)).on_conflict_do_nothing().returning(model.id)
        )
        inserted += len(result.scalars().all())
    return inserted


async def _restamped_authors(session: AsyncSession, sources: list[dict[str, Any]]) -> None:
    table = Source.__table__
    authors = bindparam("seedAuthors", type_=table.c.authors.type)
    rows = [{"sourceId": row["id"], "seedAuthors": row["authors"]} for row in sources]
    if rows:
        await session.execute(
            update(table)
            .where(
                table.c.id == bindparam("sourceId"),
                table.c.origin == IMPORT_ORIGIN,
                table.c.authors.is_distinct_from(authors),
            )
            .values(authors=authors),
            rows,
        )


async def _seed_processes(
    session: AsyncSession, stages: list[dict[str, Any]], craft_ids: dict[str, uuid.UUID]
) -> tuple[int, int]:
    process_rows = []
    process_for: dict[str, uuid.UUID] = {}
    for slug in sorted({row["craftSlug"] for row in stages if row["craftSlug"] in craft_ids}):
        process_id = seed_id("process", slug)
        process_for[slug] = process_id
        process_rows.append(
            {
                "id": process_id,
                "craftId": craft_ids[slug],
                "name": SEED_PROCESS_NAME,
                "variant": SEED_PROCESS_VARIANT,
            }
        )
    stage_values = [
        {
            "id": row["id"],
            "processId": process_for[row["craftSlug"]],
            "ordinal": row["ordinal"],
            "conceptId": row["conceptId"],
            "name": row["name"],
            "stageType": row["stageType"],
        }
        for row in stages
        if row["craftSlug"] in process_for
    ]
    return (
        await _insert_new(session, Process, process_rows),
        await _insert_new(session, ProcessStage, stage_values),
    )


def _concept_values(
    concepts: list[dict[str, Any]], craft_ids: dict[str, uuid.UUID], sub_ids: dict[str, uuid.UUID]
) -> list[dict[str, Any]]:
    values = []
    for row in concepts:
        craft_slug = row["craftSlug"]
        sub_slug = row["subCategorySlug"]
        kept = {k: v for k, v in row.items() if k not in ("craftSlug", "subCategorySlug")}
        kept["craftId"] = craft_ids.get(craft_slug) if craft_slug else None
        kept["subCategoryId"] = sub_ids.get(sub_slug) if sub_slug else None
        values.append(kept)
    return values


def _unresolved_slugs(
    concepts: list[dict[str, Any]], craft_ids: dict[str, uuid.UUID], sub_ids: dict[str, uuid.UUID]
) -> list[str]:
    crafts = {row["craftSlug"] for row in concepts if row["craftSlug"] and row["craftSlug"] not in craft_ids}
    subs = {
        row["subCategorySlug"]
        for row in concepts
        if row["subCategorySlug"] and row["subCategorySlug"] not in sub_ids
    }
    return sorted(crafts | subs)


async def _linked_edge_claims(session: AsyncSession, edges: list[dict[str, Any]]) -> None:
    links = [{"edgeId": row["id"], "linkClaimId": row["claimId"]} for row in edges if row["claimId"]]
    if links:
        table = ConceptEdge.__table__
        await session.execute(
            update(table)
            .where(table.c.id == bindparam("edgeId"), table.c.claimId.is_(None))
            .values(claimId=bindparam("linkClaimId")),
            links,
        )


async def seed_claims(session: AsyncSession, data: dict[str, Any] | None = None) -> dict[str, Any]:
    plan = claim_seed_plan(data if data is not None else load_seed_claims())
    craft_ids = await ids_by_slug(session, Craft)
    sub_ids = await ids_by_slug(session, CraftSubCategory)
    concept_values = _concept_values(plan["concepts"], craft_ids, sub_ids)
    await _restamped_authors(session, plan["sources"])
    inserted = {
        "sources": await _insert_new(session, Source, plan["sources"]),
        "concepts": await _insert_new(session, Concept, concept_values),
        "edges": await _insert_new(
            session, ConceptEdge, [{k: v for k, v in row.items() if k != "claimId"} for row in plan["edges"]]
        ),
    }
    inserted["processes"], inserted["stages"] = await _seed_processes(session, plan["stages"], craft_ids)
    inserted["claims"] = await _insert_new(session, Claim, plan["claims"])
    inserted["claimSources"] = await _insert_new(session, ClaimSource, plan["claimSources"])
    inserted["reviewEvents"] = await _insert_new(session, ReviewEvent, plan["reviewEvents"])
    await _linked_edge_claims(session, plan["edges"])
    await session.flush()
    return {
        "total": {key: len(rows) for key, rows in plan.items()},
        "inserted": inserted,
        "unresolvedSlugs": _unresolved_slugs(plan["concepts"], craft_ids, sub_ids),
    }
