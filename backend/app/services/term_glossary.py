from __future__ import annotations

import json
import uuid
from collections.abc import Iterable, Sequence
from itertools import batched
from typing import Any

from sqlalchemy import delete, func, select, tuple_
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import InvalidInput
from app.data.craft_master_loader import CRAFT_WIKIDATA_FILE, ID_NAMESPACE
from app.models import (
    Concept,
    Craft,
    CraftAlias,
    CuratedCraft,
    SharedTermCraft,
    Term,
    TermConcept,
    TermCraft,
    TermSummary,
)
from app.research.subject_keys import term_key
from app.research.term_marking import GlossaryEntry

from .claim_seed import load_seed_claims, seed_id
from .glossary_plan import (
    CraftNames,
    SeedConcept,
    TermSeed,
    compounds_of,
    concepts_of,
    glossary_plan,
    wikidata_links,
)
from .local_term_meanings import checked_meanings, dossier_quotes
from .science_seed import load_science_seed

__all__ = [
    "LATIN_SCRIPT",
    "glossary_entries",
    "glossary_seed",
    "removed_unplanned_links",
    "seed_terms",
    "term_id",
]

BATCH = 500
LATIN_SCRIPT = "Latn"
ACTIVE = "ACTIVE"
MERGED = "MERGED"
TERM_SEEDED_COLUMNS = ("label", "meaning", "localNames", "aliases", "wikidataId")


def term_id(key: str) -> uuid.UUID:
    return uuid.uuid5(ID_NAMESPACE, f"term:{key}")


def glossary_seed(crafts: Sequence[CraftNames], concepts: Sequence[SeedConcept]) -> list[TermSeed]:
    wikidata = wikidata_links(json.loads(CRAFT_WIKIDATA_FILE.read_text(encoding="utf-8")))
    meanings = checked_meanings(concepts, dossier_quotes)
    return glossary_plan(crafts, wikidata, concepts, compounds_of(load_science_seed()), meanings)


async def seed_terms(session: AsyncSession) -> dict[str, int]:
    craft_ids, crafts = await _craft_names(session)
    concepts = concepts_of(load_seed_claims())
    plan = glossary_seed(crafts, concepts)
    present = await _present_concepts(
        session, [seed_id("concept", k) for seed in plan for k in seed.concept_keys]
    )
    await _upsert_terms(session, plan)
    stored = await _stored_ids(session, [seed.key for seed in plan])
    craft_links = [
        {"termId": stored[seed.key], "craftId": craft_ids[slug]}
        for seed in plan
        for slug in seed.craft_slugs
        if slug in craft_ids
    ]
    concept_links = [
        {"termId": stored[seed.key], "conceptId": seed_id("concept", key)}
        for seed in plan
        for key in seed.concept_keys
        if seed_id("concept", key) in present
    ]
    linked = await _insert_links(session, TermCraft, craft_links)
    linked += await _insert_links(session, TermConcept, concept_links)
    seed_concepts = [seed_id("concept", concept.key) for concept in concepts]
    removed = await removed_unplanned_links(session, craft_links, concept_links, seed_concepts)
    await session.flush()
    return {
        "terms": len(plan),
        "craftLinks": len(craft_links),
        "conceptLinks": len(concept_links),
        "newLinks": linked,
        "removedLinks": len(removed),
        "removedTerms": await _removed_unlinked_terms(session, {term for term, _ in removed}),
    }


async def removed_unplanned_links(
    session: AsyncSession,
    craft_links: Sequence[dict[str, uuid.UUID]],
    concept_links: Sequence[dict[str, uuid.UUID]],
    seed_concepts: Sequence[uuid.UUID],
) -> list[tuple[uuid.UUID, uuid.UUID]]:
    crafts = select(TermCraft.termId, TermCraft.craftId).where(
        TermCraft.craftId.not_in(select(CuratedCraft.craftId))
    )
    planned = {(link["termId"], link["craftId"]) for link in craft_links}
    craft_pair = (TermCraft.termId, TermCraft.craftId)
    removed = await _removed_links(
        session, craft_pair, (await session.execute(crafts)).tuples().all(), planned
    )
    seeded: list[tuple[uuid.UUID, uuid.UUID]] = []
    for chunk in batched(seed_concepts, BATCH, strict=False):
        found = select(TermConcept.termId, TermConcept.conceptId).where(TermConcept.conceptId.in_(chunk))
        seeded.extend((await session.execute(found)).tuples().all())
    planned = {(link["termId"], link["conceptId"]) for link in concept_links}
    concept_pair = (TermConcept.termId, TermConcept.conceptId)
    return [*removed, *await _removed_links(session, concept_pair, seeded, planned)]


async def _removed_links(
    session: AsyncSession,
    pair: tuple[Any, Any],
    stored: Sequence[tuple[uuid.UUID, uuid.UUID]],
    planned: set[tuple[uuid.UUID, uuid.UUID]],
) -> list[tuple[uuid.UUID, uuid.UUID]]:
    stale = sorted(link for link in set(stored) if link not in planned)
    for chunk in batched(stale, BATCH, strict=False):
        await session.execute(delete(pair[0].class_).where(tuple_(*pair).in_(list(chunk))))
    return stale


async def _removed_unlinked_terms(session: AsyncSession, term_ids: set[uuid.UUID]) -> int:
    if not term_ids:
        return 0
    held = [select(model.termId) for model in (TermCraft, TermConcept, SharedTermCraft, TermSummary)]
    unlinked = delete(Term).where(Term.id.in_(sorted(term_ids)), *(Term.id.not_in(ids) for ids in held))
    return len((await session.execute(unlinked.returning(Term.id))).all())


async def _upsert_terms(session: AsyncSession, plan: Sequence[TermSeed]) -> None:
    for chunk in batched(plan, BATCH, strict=False):
        statement = insert(Term).values([_term_values(seed) for seed in chunk])
        changed = {column: statement.excluded[column] for column in TERM_SEEDED_COLUMNS}
        await session.execute(
            statement.on_conflict_do_update(
                index_elements=[Term.key], set_={**changed, "updatedAt": func.now()}
            )
        )


async def glossary_entries(session: AsyncSession, craft_ids: Sequence[uuid.UUID]) -> list[GlossaryEntry]:
    if not craft_ids:
        return []
    names = await session.scalars(select(Craft.name).where(Craft.id.in_(craft_ids)))
    own = {_key_of(name) for name in names}
    linked = select(TermCraft.termId).where(TermCraft.craftId.in_(craft_ids))
    rows = await session.scalars(select(Term).where(Term.id.in_(linked)).order_by(Term.key))
    return [
        GlossaryEntry(key=row.key, surfaces=(row.label, *row.aliases, *row.localNames))
        for row in rows
        if row.key not in own
    ]


async def _craft_names(session: AsyncSession) -> tuple[dict[str, uuid.UUID], list[CraftNames]]:
    crafts = (
        await session.execute(select(Craft.id, Craft.slug, Craft.name).where(Craft.status != MERGED))
    ).all()
    aliases: dict[uuid.UUID, list[Any]] = {}
    rows = await session.execute(
        select(CraftAlias.craftId, CraftAlias.alias, CraftAlias.script)
        .where(CraftAlias.status == ACTIVE)
        .order_by(CraftAlias.craftId, CraftAlias.alias)
    )
    for row in rows:
        aliases.setdefault(row.craftId, []).append(row)
    names = [
        CraftNames(
            slug=craft.slug,
            name=craft.name,
            aliases=tuple(a.alias for a in aliases.get(craft.id, []) if a.script in (None, LATIN_SCRIPT)),
            local_names=tuple(
                a.alias for a in aliases.get(craft.id, []) if a.script not in (None, LATIN_SCRIPT)
            ),
        )
        for craft in crafts
    ]
    return {craft.slug: craft.id for craft in crafts}, names


async def _present_concepts(session: AsyncSession, ids: Iterable[uuid.UUID]) -> set[uuid.UUID]:
    wanted = list(dict.fromkeys(ids))
    found: set[uuid.UUID] = set()
    for chunk in batched(wanted, BATCH, strict=False):
        found.update(await session.scalars(select(Concept.id).where(Concept.id.in_(chunk))))
    return found


async def _stored_ids(session: AsyncSession, keys: Sequence[str]) -> dict[str, uuid.UUID]:
    stored: dict[str, uuid.UUID] = {}
    for chunk in batched(keys, BATCH, strict=False):
        stored.update(
            (await session.execute(select(Term.key, Term.id).where(Term.key.in_(chunk)))).tuples().all()
        )
    return stored


async def _insert_links(session: AsyncSession, model: Any, rows: list[dict[str, uuid.UUID]]) -> int:
    inserted = 0
    for chunk in batched(rows, BATCH, strict=False):
        result = await session.execute(
            insert(model).values(list(chunk)).on_conflict_do_nothing().returning(model.termId)
        )
        inserted += len(result.scalars().all())
    return inserted


def _key_of(name: str) -> str | None:
    try:
        return term_key(name)
    except InvalidInput:
        return None


def _term_values(seed: TermSeed) -> dict[str, Any]:
    return {
        "id": term_id(seed.key),
        "key": seed.key,
        "label": seed.label,
        "meaning": seed.meaning,
        "localNames": seed.local_names,
        "aliases": seed.aliases,
        "wikidataId": seed.wikidata_id,
    }
