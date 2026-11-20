from __future__ import annotations

import uuid
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, replace
from typing import Any

from sqlalchemy import Select, func, literal, select, union_all
from sqlalchemy.ext.asyncio import AsyncSession

from app.data.craft_text import core_key
from app.models import Claim, Concept, Craft, CuratedCraft, KnowledgePiece
from app.research.craft_finding import PLACE_SCORE, CraftSignals, query_words, ranked_crafts
from app.research.knowledge_api import FoundCraft, FoundCrafts
from app.research.retrieval import SHOWN_CLAIM_STATUSES, VISIBLE_SENSITIVITY

from .coverage_reads import found_coverage
from .craft_index import CraftIndex
from .craft_matching import lexical_match, ranked_candidates
from .craft_resolver import CraftIndexStore

__all__ = ["CANDIDATES_EACH", "find_crafts"]

CANDIDATES_EACH = 30
TEXT_SEARCH = "english"


@dataclass(frozen=True)
class _Held:
    words: frozenset[str]
    hits: int


async def find_crafts(session: AsyncSession, store: CraftIndexStore, query: str, *, site: str) -> FoundCrafts:
    index = await store.get(session)
    words = query_words(query)
    named = _named(index, query)
    held = await _held(session, words)
    ids = [*named, *(craft_id for craft_id in held if craft_id not in named)]
    signals = await _standing(
        session, [_signals(index, craft_id, named, held) for craft_id in ids if craft_id in index.refs]
    )
    ranked = ranked_crafts(signals, words)
    fields = await found_coverage(session, [scored.signals.craft.slug for scored in ranked])
    return FoundCrafts(
        query=query,
        crafts=[
            FoundCraft(
                craft=scored.signals.craft,
                score=scored.score,
                page_url=f"{site}{scored.signals.craft.path}",
                fields=fields.get(scored.signals.craft.slug),
            )
            for scored in ranked
        ],
    )


def _named(index: CraftIndex, query: str) -> dict[uuid.UUID, tuple[float, frozenset[str]]]:
    match = lexical_match(index, query)
    found: dict[uuid.UUID, tuple[float, frozenset[str]]] = {}
    for candidate in ranked_candidates(index, match)[:CANDIDATES_EACH]:
        target = index.slugs[candidate.craft.slug].craft_id
        found[target] = (candidate.score, _tokens(reason.matched for reason in candidate.reasons))
    places = frozenset(match.hints)
    for craft_id, keys in index.craft_places.items():
        if craft_id not in found and keys & places:
            found[craft_id] = (PLACE_SCORE, _tokens(keys & places))
    return found


async def _held(session: AsyncSession, words: Sequence[str]) -> dict[uuid.UUID, _Held]:
    if not words:
        return {}
    either = func.to_tsquery(TEXT_SEARCH, " | ".join(words))
    hits = union_all(*_knowledge(either)).subquery("hits")
    columns = [func.bool_or(hits.c.tsv.op("@@")(func.to_tsquery(TEXT_SEARCH, word))) for word in words]
    rows = await session.execute(
        select(hits.c.craft_id, func.count(), *columns)
        .group_by(hits.c.craft_id)
        .order_by(func.count().desc(), hits.c.craft_id)
        .limit(CANDIDATES_EACH)
    )
    return {row[0]: _Held(words=_found(words, row[2:]), hits=int(row[1])) for row in rows.all()}


def _found(words: Sequence[str], flags: Sequence[Any]) -> frozenset[str]:
    return frozenset(word for word, held in zip(words, flags, strict=True) if held)


def _knowledge(query: Any) -> tuple[Select[Any], ...]:
    claims = (
        select(Concept.craftId.label("craft_id"), Claim.tsv.label("tsv"))
        .join(Concept, Concept.id == Claim.subjectId)
        .where(
            Claim.subjectType == "CONCEPT",
            Concept.craftId.is_not(None),
            Claim.status.in_(SHOWN_CLAIM_STATUSES),
            Claim.sensitivity == VISIBLE_SENSITIVITY,
            Claim.tsv.op("@@")(query),
        )
    )
    named = func.to_tsvector(TEXT_SEARCH, Concept.name)
    concepts = select(Concept.craftId.label("craft_id"), named.label("tsv")).where(
        Concept.craftId.is_not(None), Concept.sensitivity == VISIBLE_SENSITIVITY, named.op("@@")(query)
    )
    words = func.to_tsvector(
        TEXT_SEARCH,
        func.concat_ws(literal(" "), KnowledgePiece.title, KnowledgePiece.label, KnowledgePiece.topicKey),
    )
    pieces = select(KnowledgePiece.craftId.label("craft_id"), words.label("tsv")).where(
        KnowledgePiece.craftId.is_not(None),
        KnowledgePiece.hiddenAt.is_(None),
        KnowledgePiece.supersededById.is_(None),
        words.op("@@")(query),
    )
    return claims, concepts, pieces


async def _standing(session: AsyncSession, signals: Sequence[CraftSignals]) -> list[CraftSignals]:
    if not signals:
        return []
    slugs = [item.craft.slug for item in signals]
    rows = await session.execute(_standing_query(slugs))
    standing = {
        slug: (bool(curated), int(claims), int(fields)) for slug, curated, claims, fields in rows.all()
    }
    found = []
    for item in signals:
        curated, claims, fields = standing.get(item.craft.slug, (False, 0, 0))
        found.append(replace(item, curated=curated, claims=claims, fields=fields))
    return found


def _standing_query(slugs: Sequence[str]) -> Select[Any]:
    claims = (
        select(Concept.craftId.label("craft_id"), Claim.id.label("claim_id"), Claim.field.label("field"))
        .join(Concept, Concept.id == Claim.subjectId)
        .where(
            Claim.subjectType == "CONCEPT",
            Concept.craftId.in_(select(Craft.id).where(Craft.slug.in_(list(slugs)))),
            Claim.status.in_(SHOWN_CLAIM_STATUSES),
            Claim.sensitivity == VISIBLE_SENSITIVITY,
        )
        .subquery("held")
    )
    return (
        select(
            Craft.slug,
            func.bool_or(CuratedCraft.craftId.is_not(None)),
            func.count(func.distinct(claims.c.claim_id)),
            func.count(func.distinct(claims.c.field)),
        )
        .outerjoin(CuratedCraft, CuratedCraft.craftId == Craft.id)
        .outerjoin(claims, claims.c.craft_id == Craft.id)
        .where(Craft.slug.in_(list(slugs)))
        .group_by(Craft.slug)
    )


def _signals(
    index: CraftIndex,
    craft_id: uuid.UUID,
    named: Mapping[uuid.UUID, tuple[float, frozenset[str]]],
    held: Mapping[uuid.UUID, _Held],
) -> CraftSignals:
    lexical, named_words = named.get(craft_id, (0.0, frozenset()))
    knowledge = held.get(craft_id, _Held(words=frozenset(), hits=0))
    return CraftSignals(
        craft=index.refs[craft_id],
        lexical=lexical,
        named_words=named_words,
        held_words=knowledge.words,
        held_hits=knowledge.hits,
    )


def _tokens(labels: Iterable[str]) -> frozenset[str]:
    return frozenset(token for label in labels for token in core_key(label).split())
