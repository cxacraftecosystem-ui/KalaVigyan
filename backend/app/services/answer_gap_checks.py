from __future__ import annotations

import uuid
from collections import defaultdict
from collections.abc import Sequence
from datetime import datetime

from sqlalchemy import String, cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Answer, AnswerGap, AnswerVerdict, Craft, TaskReservation
from app.research.crafts import QUESTION_MAX_CHARS
from app.research.embedding import checked_vectors
from app.research.open_work_gap_keys import GAP_TASK, gap_id
from app.research.open_work_gaps import Asked, accepted, found_facts, gap_count, gap_priority
from app.research.retrieval import KnowledgeQuery
from app.retrieval.hybrid import StoredKnowledgeSearch
from app.retrieval.stamps import made_by_current_model

from .answer_translation import needs_english_rendering
from .open_work_gaps import OPEN_GAP

__all__ = [
    "ACCEPTANCE_MODE",
    "ANSWERED_GAP",
    "LAPSED_GAP",
    "answered_gaps",
    "end_closed_reservations",
    "recount_gaps",
]

ANSWERED_GAP = "ANSWERED"
LAPSED_GAP = "LAPSED"
ACCEPTANCE_MODE = "HYBRID"
COMPLETED = "COMPLETED"
EXPIRED = "EXPIRED"
KEY_SEPARATOR = ":"


async def recount_gaps(session: AsyncSession, *, now: datetime) -> list[uuid.UUID]:
    gaps = (await session.scalars(select(AnswerGap).where(AnswerGap.state == OPEN_GAP))).all()
    members = await _members(session, [gap.id for gap in gaps])
    lapsed = []
    for gap in gaps:
        count = gap_count(members.get(gap.id, ()), now=now)
        if count.last_asked is None:
            gap.askers, gap.state, gap.closedAt = 0, LAPSED_GAP, now
            lapsed.append(gap.id)
            continue
        gap.askers, gap.lastAskedAt = count.askers, count.last_asked
        gap.fields, gap.lacks = list(count.fields), list(count.lacks)
        gap.priority = gap_priority(count.askers, count.last_asked, now=now)
    await session.flush()
    return lapsed


async def answered_gaps(session: AsyncSession, *, now: datetime) -> list[uuid.UUID]:
    rows = await session.execute(
        select(AnswerGap, Craft.slug)
        .join(Craft, Craft.id == AnswerGap.craftId)
        .where(AnswerGap.state == OPEN_GAP, made_by_current_model(AnswerGap.embeddingModel))
        .order_by(AnswerGap.id)
    )
    answered = []
    for gap, slug in rows.all():
        if await _accepted(session, gap, slug):
            gap.state, gap.closedAt = ANSWERED_GAP, now
            answered.append(gap.id)
    await session.flush()
    return answered


async def end_closed_reservations(session: AsyncSession, *, now: datetime) -> list[str]:
    live = (
        await session.scalars(
            select(TaskReservation).where(
                TaskReservation.endedAt.is_(None),
                TaskReservation.taskKey.startswith(f"{GAP_TASK}{KEY_SEPARATOR}", autoescape=True),
            )
        )
    ).all()
    held = {row.taskKey: gap_id(row.taskKey.rsplit(KEY_SEPARATOR, 1)[-1]) for row in live}
    states = await _states(session, [gap for gap in held.values() if gap is not None])
    ended = []
    for reservation in live:
        gap = held[reservation.taskKey]
        state = states.get(gap) if gap is not None else None
        if state == OPEN_GAP:
            continue
        reservation.endedAt = now
        reservation.ending = COMPLETED if state == ANSWERED_GAP else EXPIRED
        ended.append(reservation.taskKey)
    await session.flush()
    return ended


async def _members(session: AsyncSession, gap_ids: Sequence[uuid.UUID]) -> dict[uuid.UUID, list[Asked]]:
    if not gap_ids:
        return {}
    asker = func.coalesce(cast(Answer.userId, String), cast(Answer.id, String))
    rows = await session.execute(
        select(AnswerVerdict.gapId, asker, Answer.createdAt, AnswerVerdict.lacking, AnswerVerdict.lacks)
        .join(Answer, Answer.id == AnswerVerdict.answerId)
        .where(AnswerVerdict.gapId.in_(list(gap_ids)))
    )
    found: dict[uuid.UUID, list[Asked]] = defaultdict(list)
    for gap, who, asked_at, lacking, lacks in rows.all():
        found[gap].append(
            Asked(asker=str(who), asked_at=asked_at, lacking=tuple(lacking), lacks=tuple(lacks))
        )
    return dict(found)


async def _accepted(session: AsyncSession, gap: AnswerGap, slug: str) -> bool:
    if gap.embedding is None:
        return False
    vector = [float(value) for value in gap.embedding]

    async def stored_vector(texts: list[str]) -> list[list[float]]:
        return checked_vectors([vector for _ in texts], expected=len(texts))

    search = StoredKnowledgeSearch(session, embed=stored_vector)
    by_meaning = needs_english_rendering(gap.question)
    question = gap.question[:QUESTION_MAX_CHARS]
    found: dict[str, int] = {}
    for field in gap.fields:
        hits = await search.search(
            KnowledgeQuery(craft_slug=slug, text=question, mode=ACCEPTANCE_MODE, fields=(field,))
        )
        found[field] = found_facts(hits, by_meaning=by_meaning)
    return accepted(found)


async def _states(session: AsyncSession, gap_ids: Sequence[uuid.UUID]) -> dict[uuid.UUID, str]:
    if not gap_ids:
        return {}
    rows = await session.execute(select(AnswerGap.id, AnswerGap.state).where(AnswerGap.id.in_(list(gap_ids))))
    return {gap: str(state) for gap, state in rows.all()}
