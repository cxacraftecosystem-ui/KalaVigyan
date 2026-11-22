from __future__ import annotations

import uuid
from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import datetime

from sqlalchemy import and_, exists, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    Answer,
    CandidateCheck,
    Chunk,
    Claim,
    ClaimSource,
    Concept,
    Craft,
    CraftCategory,
    ReviewEvent,
    Source,
)
from app.research.crafts import CraftRef
from app.research.write_back import FOUND_BY

from .claim_writer import HELD_WRITE_BACK_ACTOR
from .craft_resolver import CraftIndexStore
from .knowledge_view import craft_ref
from .research_write_back import compared_crafts
from .write_back_filing import (
    SHARED_PLACE,
    FilingRow,
    StoredCitation,
    StoredFiling,
    craft_place,
    family_place,
    filing_row,
    held_place,
)
from .write_back_names import CraftNames, filing_names

__all__ = ["FILING_REPORT_MAX", "filing_report"]

FILING_REPORT_MAX = 500
CONCEPT_SUBJECT = "CONCEPT"


@dataclass(frozen=True)
class _Researched:
    lead: CraftRef | None
    compared: tuple[CraftRef, ...] = ()


@dataclass
class _Names:
    session: AsyncSession
    store: CraftIndexStore
    made: dict[tuple[str | None, tuple[str, ...]], CraftNames] = field(default_factory=dict)

    async def __call__(self, researched: _Researched | None) -> CraftNames | None:
        if researched is None:
            return None
        key = (researched.lead.slug if researched.lead else None, tuple(c.slug for c in researched.compared))
        if key not in self.made:
            self.made[key] = await filing_names(
                self.session, self.store, researched.lead, researched.compared
            )
        return self.made[key]


async def filing_report(
    session: AsyncSession,
    store: CraftIndexStore,
    *,
    answer_id: uuid.UUID | None = None,
    since: datetime | None = None,
) -> list[FilingRow]:
    claims = await _claims(session, answer_id=answer_id, since=since)
    ids = [claim.id for claim in claims]
    places, crafts = await _places(session, ids)
    held = await _held(session, ids)
    places |= {claim_id: held_place(crafts[claim_id].slug) for claim_id in held & set(crafts)}
    citations = await _citations(session, ids)
    checked = await _checked(session, ids)
    researched = await _researched(session, ids, crafts)
    names = _Names(session, store)
    rows = []
    for claim in claims:
        stored = StoredFiling(
            claim_id=claim.id,
            text=claim.text,
            status=claim.status,
            field=claim.field,
            place=places.get(claim.id, SHARED_PLACE),
            checked=claim.id in checked,
            citations=tuple(citations.get(claim.id, ())),
        )
        rows.append(filing_row(stored, await names(researched.get(claim.id))))
    return rows


async def _claims(
    session: AsyncSession, *, answer_id: uuid.UUID | None, since: datetime | None
) -> list[Claim]:
    cited = select(ClaimSource.claimId).where(ClaimSource.foundBy.in_(FOUND_BY))
    if answer_id is not None:
        cited = cited.where(ClaimSource.answerId == answer_id)
    query = select(Claim).where(Claim.id.in_(cited))
    if since is not None:
        query = query.where(Claim.createdAt >= since)
    return list(await session.scalars(query.order_by(Claim.createdAt, Claim.id).limit(FILING_REPORT_MAX)))


async def _places(
    session: AsyncSession, ids: Sequence[uuid.UUID]
) -> tuple[dict[uuid.UUID, str], dict[uuid.UUID, CraftRef]]:
    shared = and_(Concept.craftId.is_(None), Concept.subCategoryId.is_(None))
    named = and_(shared, func.lower(CraftCategory.name) == func.lower(Concept.name))
    rows = await session.execute(
        select(Claim.id, Craft, CraftCategory.slug.label("category"))
        .select_from(Claim)
        .outerjoin(Concept, and_(Claim.subjectType == CONCEPT_SUBJECT, Concept.id == Claim.subjectId))
        .outerjoin(Craft, Craft.id == Concept.craftId)
        .outerjoin(CraftCategory, named)
        .where(Claim.id.in_(list(ids)))
    )
    places: dict[uuid.UUID, str] = {}
    crafts: dict[uuid.UUID, CraftRef] = {}
    for claim_id, craft, category in rows.tuples().all():
        if craft is not None:
            crafts[claim_id] = CraftRef.model_validate(craft_ref(craft))
            places[claim_id] = craft_place(craft.slug)
        elif category is not None:
            places.setdefault(claim_id, family_place(category))
    return places, crafts


async def _citations(
    session: AsyncSession, ids: Sequence[uuid.UUID]
) -> dict[uuid.UUID, list[StoredCitation]]:
    rows = await session.execute(
        select(
            ClaimSource.claimId,
            ClaimSource.quote,
            ClaimSource.quoteCheck,
            Source.title,
            Source.kind,
            Chunk.text,
        )
        .join(Source, Source.id == ClaimSource.sourceId)
        .outerjoin(Chunk, Chunk.id == ClaimSource.chunkId)
        .where(ClaimSource.claimId.in_(list(ids)))
        .order_by(ClaimSource.claimId, ClaimSource.createdAt, ClaimSource.id)
    )
    found: dict[uuid.UUID, list[StoredCitation]] = defaultdict(list)
    for claim_id, quote, check, title, kind, passage in rows.tuples().all():
        found[claim_id].append(StoredCitation(quote, check, title, kind, passage))
    return found


async def _checked(session: AsyncSession, ids: Sequence[uuid.UUID]) -> set[uuid.UUID]:
    if not ids:
        return set()
    checked = select(CandidateCheck.claimId).where(CandidateCheck.claimId.in_(list(ids))).distinct()
    return set((await session.scalars(checked)).all())


async def _held(session: AsyncSession, ids: Sequence[uuid.UUID]) -> set[uuid.UUID]:
    if not ids:
        return set()
    held = exists().where(ReviewEvent.claimId == Claim.id, ReviewEvent.systemActor == HELD_WRITE_BACK_ACTOR)
    return set((await session.scalars(select(Claim.id).where(Claim.id.in_(list(ids)), held))).all())


async def _researched(
    session: AsyncSession, ids: Sequence[uuid.UUID], crafts: dict[uuid.UUID, CraftRef]
) -> dict[uuid.UUID, _Researched]:
    answers = await _first_answers(session, ids)
    leads = await _answer_crafts(session, set(answers.values()))
    asked = {
        answer_id: _Researched(leads.get(answer_id), await compared_crafts(session, answer_id))
        for answer_id in set(answers.values())
    }
    found = {claim_id: asked[answer_id] for claim_id, answer_id in answers.items()}
    return found | {
        claim_id: _Researched(craft) for claim_id, craft in crafts.items() if claim_id not in found
    }


async def _first_answers(session: AsyncSession, ids: Sequence[uuid.UUID]) -> dict[uuid.UUID, uuid.UUID]:
    rows = await session.execute(
        select(ClaimSource.claimId, ClaimSource.answerId)
        .where(
            ClaimSource.claimId.in_(list(ids)),
            ClaimSource.foundBy.in_(FOUND_BY),
            ClaimSource.answerId.is_not(None),
        )
        .order_by(ClaimSource.createdAt, ClaimSource.id)
    )
    found: dict[uuid.UUID, uuid.UUID] = {}
    for claim_id, answer_id in rows.tuples().all():
        found.setdefault(claim_id, answer_id)
    return found


async def _answer_crafts(session: AsyncSession, answer_ids: set[uuid.UUID]) -> dict[uuid.UUID, CraftRef]:
    if not answer_ids:
        return {}
    rows = await session.execute(
        select(Answer.id, Craft)
        .join(Craft, Craft.id == Answer.craftId)
        .where(Answer.id.in_(list(answer_ids)))
    )
    return {answer_id: CraftRef.model_validate(craft_ref(craft)) for answer_id, craft in rows.tuples().all()}
