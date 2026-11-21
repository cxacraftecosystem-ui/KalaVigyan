from __future__ import annotations

import uuid
from collections import defaultdict
from collections.abc import AsyncIterator, Mapping, Sequence
from dataclasses import dataclass

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.orm import aliased

from app.models import Claim, Concept, Craft, CraftAlias
from app.research.candidate_gates import HeldFact, statement_key
from app.research.gate_thrift import VECTOR_TWIN_SIMILARITY, vector_twin
from app.research.vocabulary import CONCEPT_TYPE_DISCIPLINES

from .evaluation import EVAL_MODE
from .question_writing import CraftFacts, EvalFact, sampled_facts, second_language_of
from .stamps import made_by_current_model
from .statements import CONCEPT_SUBJECT, CraftScope, claim_conditions

__all__ = ["ACTIVE_STATUS", "EvalCraft", "FactSampling", "craft_fact_sets", "craft_facts", "eval_crafts"]

ACTIVE_STATUS = "ACTIVE"


@dataclass(frozen=True)
class EvalCraft:
    id: uuid.UUID
    slug: str
    names: tuple[str, ...]
    states: tuple[str, ...]


@dataclass(frozen=True)
class FactSampling:
    seed: int
    per_craft: int
    state_languages: Mapping[str, Sequence[str]]

    def second_language(self, states: Sequence[str]) -> str:
        return second_language_of([code for state in states for code in self.state_languages.get(state, ())])


async def eval_crafts(session: AsyncSession) -> list[EvalCraft]:
    rows = (
        await session.execute(
            select(Craft.id, Craft.slug, Craft.name, Craft.localName, Craft.stateOfOrigin)
            .where(Craft.status == ACTIVE_STATUS, Craft.isCatchAll.is_(False))
            .order_by(Craft.slug)
        )
    ).all()
    aliases: dict[uuid.UUID, list[str]] = defaultdict(list)
    for craft_id, alias in await session.execute(
        select(CraftAlias.craftId, CraftAlias.alias)
        .where(CraftAlias.status == ACTIVE_STATUS)
        .order_by(CraftAlias.craftId, CraftAlias.alias)
    ):
        aliases[craft_id].append(alias)
    return [
        EvalCraft(
            id=row.id,
            slug=row.slug,
            names=tuple(
                dict.fromkeys([row.name, *([row.localName] if row.localName else []), *aliases[row.id]])
            ),
            states=tuple(row.stateOfOrigin or ()),
        )
        for row in rows
    ]


async def craft_facts(session: AsyncSession, craft: EvalCraft, sampling: FactSampling) -> CraftFacts:
    facts = await _published(session, craft.id)
    sampled = sampled_facts(facts, seed=sampling.seed, per_craft=sampling.per_craft)
    twins = await _vector_twins(session, sampled, [fact.id for fact in facts])
    same_text: dict[str, list[uuid.UUID]] = defaultdict(list)
    for fact in facts:
        same_text[statement_key(fact.text)].append(fact.id)
    return CraftFacts(
        slug=craft.slug,
        names=craft.names,
        second_language=sampling.second_language(craft.states),
        facts=tuple(facts),
        sampled=tuple(
            _restated(fact, [*same_text[statement_key(fact.text)], *twins[fact.id]]) for fact in sampled
        ),
    )


def _restated(fact: EvalFact, same: Sequence[uuid.UUID]) -> EvalFact:
    restatements = tuple(dict.fromkeys(other for other in same if other != fact.id))
    return EvalFact(id=fact.id, text=fact.text, field=fact.field, restatements=restatements)


async def craft_fact_sets(
    sessions: async_sessionmaker[AsyncSession], crafts: Sequence[EvalCraft], sampling: FactSampling
) -> AsyncIterator[CraftFacts]:
    for craft in crafts:
        async with sessions() as session:
            found = await craft_facts(session, craft, sampling)
        if found.facts:
            yield found


async def _published(session: AsyncSession, craft_id: uuid.UUID) -> list[EvalFact]:
    scope = CraftScope(craft_id=craft_id, sub_category_id=None)
    subject = aliased(Concept)
    rows = await session.execute(
        select(Claim.id, Claim.text, Claim.field, subject.type)
        .outerjoin(subject, and_(Claim.subjectType == CONCEPT_SUBJECT, subject.id == Claim.subjectId))
        .where(*claim_conditions(scope, mode=EVAL_MODE))
        .order_by(Claim.id)
    )
    return [
        EvalFact(id=row.id, text=row.text, field=row.field or CONCEPT_TYPE_DISCIPLINES.get(row.type or ""))
        for row in rows
    ]


async def _vector_twins(
    session: AsyncSession, sampled: Sequence[EvalFact], own: Sequence[uuid.UUID]
) -> dict[uuid.UUID, list[uuid.UUID]]:
    twins: dict[uuid.UUID, list[uuid.UUID]] = defaultdict(list)
    if not sampled:
        return twins
    other = aliased(Claim)
    distance = Claim.embedding.cosine_distance(other.embedding)
    rows = await session.execute(
        select(Claim.id, other.id.label("twin"), other.text, (1 - distance).label("similarity"))
        .where(
            Claim.id.in_([fact.id for fact in sampled]),
            other.id.in_(list(own)),
            other.id != Claim.id,
            made_by_current_model(Claim.embeddingModel),
            made_by_current_model(other.embeddingModel),
            distance <= 1 - VECTOR_TWIN_SIMILARITY,
        )
        .order_by(Claim.id, distance, other.id)
    )
    texts = {fact.id: fact.text for fact in sampled}
    for row in rows:
        held = HeldFact(id=row.twin, text=row.text, similarity=max(-1.0, min(1.0, float(row.similarity))))
        if vector_twin(texts[row.id], [held], at_least=VECTOR_TWIN_SIMILARITY) is not None:
            twins[row.id].append(row.twin)
    return twins
