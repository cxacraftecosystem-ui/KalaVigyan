from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable, Collection, Mapping
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import TermConcept

from .builder_interface import BuilderTools

__all__ = ["SubjectLookup", "Subjects", "linked_subjects", "stored_subjects"]

NO_TERMS: frozenset[uuid.UUID] = frozenset()


@dataclass(frozen=True)
class Subjects:
    terms: Mapping[uuid.UUID, frozenset[uuid.UUID]] = field(default_factory=dict)

    def same(self, one: uuid.UUID | None, other: uuid.UUID | None) -> bool:
        if one is None or other is None:
            return False
        return one == other or bool(self.terms.get(one, NO_TERMS) & self.terms.get(other, NO_TERMS))


SubjectLookup = Callable[[Collection[uuid.UUID]], Awaitable[Subjects]]


def stored_subjects(tools: BuilderTools) -> SubjectLookup:
    async def lookup(concepts: Collection[uuid.UUID]) -> Subjects:
        wanted = sorted(set(concepts))
        if tools.sessions is None or len(wanted) < 2:
            return Subjects()
        async with tools.sessions() as session:
            return await linked_subjects(session, wanted)

    return lookup


async def linked_subjects(session: AsyncSession, concepts: Collection[uuid.UUID]) -> Subjects:
    rows = await session.execute(
        select(TermConcept.conceptId, TermConcept.termId).where(TermConcept.conceptId.in_(list(concepts)))
    )
    terms: dict[uuid.UUID, set[uuid.UUID]] = {}
    for concept_id, term_id in rows.tuples():
        terms.setdefault(concept_id, set()).add(term_id)
    return Subjects({concept_id: frozenset(found) for concept_id, found in terms.items()})
