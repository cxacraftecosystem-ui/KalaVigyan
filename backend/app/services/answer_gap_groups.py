from __future__ import annotations

import logging
import uuid
from collections.abc import Sequence
from dataclasses import dataclass, replace
from datetime import datetime
from itertools import batched
from typing import Any

from sqlalchemy import select, union_all, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.models import (
    AdminDistrict,
    AdminState,
    Answer,
    AnswerGap,
    AnswerVerdict,
    Craft,
    CraftCategory,
    CraftSubCategory,
)
from app.research.embedding import TextEmbedder, checked_vectors
from app.research.open_work_gap_privacy import anonymised, known_words
from app.research.open_work_gaps import ASKED_WINDOW, GAP_VERDICTS, nearest_gap
from app.research.question_names import AskedQuestion
from app.research.structured import StructuredModel
from app.retrieval.indexing import EMBED_BATCH
from app.retrieval.stamps import current_embedding_model, made_by_current_model, needs_vector
from app.retrieval.text import query_text

from .open_work_gaps import OPEN_GAP
from .question_names import screen_names

__all__ = ["CANDIDATES_PER_NIGHT", "Grouped", "group_questions", "place_names"]

logger = logging.getLogger(__name__)

CANDIDATES_PER_NIGHT = 500


@dataclass(frozen=True)
class _Question:
    verdict_id: uuid.UUID
    craft_id: uuid.UUID
    text: str
    language: str
    asked_at: datetime
    lacking: tuple[str, ...]
    lacks: tuple[str, ...]
    vector: Any


@dataclass
class Grouped:
    candidates: int = 0
    dropped: int = 0
    embedded: int = 0
    joined: int = 0
    opened: int = 0
    held: int = 0
    embedding_error: str | None = None
    names_error: str | None = None


async def group_questions(
    session: AsyncSession,
    embed: TextEmbedder | None,
    *,
    now: datetime,
    names: StructuredModel | None = None,
) -> Grouped:
    rows = await _candidates(session, now=now)
    known = known_words(await place_names(session))
    found = Grouped(candidates=len(rows))
    kept = [(row, text) for row in rows if (text := anonymised(row.question, known)) is not None]
    found.dropped = len(rows) - len(kept)
    questions = await _screened(names, kept, found)
    questions = await _embedded(session, embed, questions, found)
    for question in questions:
        if question.vector is not None:
            await _placed(session, question, found)
    await session.flush()
    return found


async def place_names(session: AsyncSession) -> list[str]:
    names = union_all(
        select(Craft.name),
        select(CraftCategory.name),
        select(CraftSubCategory.name),
        select(AdminState.name),
        select(AdminDistrict.name),
    )
    return [str(name) for name in (await session.scalars(select(names.subquery("names").c.name))).all()]


async def _candidates(session: AsyncSession, *, now: datetime) -> Sequence[Any]:
    rows = await session.execute(
        select(
            AnswerVerdict.id,
            AnswerVerdict.craftId,
            AnswerVerdict.lacking,
            AnswerVerdict.lacks,
            AnswerVerdict.embedding,
            needs_vector(AnswerVerdict.embedding, AnswerVerdict.embeddingModel).label("unembedded"),
            Answer.question,
            Answer.language,
            Answer.createdAt,
        )
        .join(Answer, Answer.id == AnswerVerdict.answerId)
        .where(
            AnswerVerdict.verdict.in_(GAP_VERDICTS),
            AnswerVerdict.craftId.is_not(None),
            AnswerVerdict.gapId.is_(None),
            Answer.createdAt >= now - ASKED_WINDOW,
        )
        .order_by(Answer.createdAt, AnswerVerdict.id)
        .limit(CANDIDATES_PER_NIGHT)
    )
    return rows.all()


async def _screened(
    names: StructuredModel | None, kept: Sequence[tuple[Any, str]], found: Grouped
) -> list[_Question]:
    if names is None:
        return [_question(row, text) for row, text in kept]
    asked = [AskedQuestion(key=str(row.id), asked=row.question, kept=text) for row, text in kept]
    screen = await screen_names(names, asked)
    found.names_error = screen.error
    questions: list[_Question] = []
    for row, _ in kept:
        key = str(row.id)
        if key not in screen.screened:
            found.held += 1
        elif (text := screen.screened[key]) is None:
            found.dropped += 1
        else:
            questions.append(_question(row, text))
    return questions


def _question(row: Any, text: str) -> _Question:
    return _Question(
        verdict_id=row.id,
        craft_id=row.craftId,
        text=text,
        language=row.language,
        asked_at=row.createdAt,
        lacking=tuple(row.lacking),
        lacks=tuple(row.lacks),
        vector=None if row.unembedded else row.embedding,
    )


async def _embedded(
    session: AsyncSession, embed: TextEmbedder | None, questions: list[_Question], found: Grouped
) -> list[_Question]:
    waiting = [(question.verdict_id, question.text) for question in questions if question.vector is None]
    if embed is None:
        return questions
    stale = await _stale_gaps(session)
    vectors: dict[uuid.UUID, list[float]] = {}
    try:
        for group in batched(stale, EMBED_BATCH, strict=False):
            await _stamped(session, embed, AnswerGap, group)
        for group in batched(waiting, EMBED_BATCH, strict=False):
            vectors |= await _stamped(session, embed, AnswerVerdict, group)
    except AppError as error:
        logger.warning("questions kept without vectors; the next night embeds them: %s", error)
        found.embedding_error = str(error)
    found.embedded = len(vectors)
    return [_with_vector(question, vectors.get(question.verdict_id)) for question in questions]


async def _stale_gaps(session: AsyncSession) -> list[tuple[uuid.UUID, str]]:
    rows = await session.execute(
        select(AnswerGap.id, AnswerGap.question).where(
            AnswerGap.state == OPEN_GAP, needs_vector(AnswerGap.embedding, AnswerGap.embeddingModel)
        )
    )
    return [(gap, str(question)) for gap, question in rows.all()]


async def _stamped(
    session: AsyncSession,
    embed: TextEmbedder,
    model: type[AnswerVerdict] | type[AnswerGap],
    group: Sequence[tuple[uuid.UUID, str]],
) -> dict[uuid.UUID, list[float]]:
    texts = [query_text(text) for _, text in group]
    vectors = checked_vectors(await embed(texts), expected=len(texts))
    for (row_id, _), vector in zip(group, vectors, strict=True):
        await session.execute(
            update(model)
            .where(model.id == row_id)
            .values(embedding=vector, embeddingModel=current_embedding_model())
        )
    return {row_id: vector for (row_id, _), vector in zip(group, vectors, strict=True)}


def _with_vector(question: _Question, vector: list[float] | None) -> _Question:
    return question if vector is None else replace(question, vector=vector)


async def _placed(session: AsyncSession, question: _Question, found: Grouped) -> None:
    distance = AnswerGap.embedding.cosine_distance(question.vector)
    rows = await session.execute(
        select(AnswerGap.id, distance)
        .where(
            AnswerGap.craftId == question.craft_id,
            AnswerGap.state == OPEN_GAP,
            made_by_current_model(AnswerGap.embeddingModel),
        )
        .order_by(distance, AnswerGap.id)
        .limit(1)
    )
    gap_id = nearest_gap({gap: float(apart) for gap, apart in rows.all() if apart is not None})
    if gap_id is None:
        gap_id = await _opened(session, question)
        found.opened += 1
    else:
        found.joined += 1
    await session.execute(
        update(AnswerVerdict).where(AnswerVerdict.id == question.verdict_id).values(gapId=gap_id)
    )


async def _opened(session: AsyncSession, question: _Question) -> uuid.UUID:
    gap = AnswerGap(
        id=uuid.uuid4(),
        craftId=question.craft_id,
        question=question.text,
        language=question.language,
        fields=list(question.lacking),
        lacks=list(question.lacks),
        askers=0,
        firstAskedAt=question.asked_at,
        lastAskedAt=question.asked_at,
        embedding=question.vector,
        embeddingModel=current_embedding_model(),
    )
    session.add(gap)
    await session.flush()
    return gap.id
