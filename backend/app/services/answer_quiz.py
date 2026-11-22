from __future__ import annotations

import logging
import uuid
from collections.abc import Awaitable, Callable, Mapping, Sequence
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.errors import AppError
from app.models import Answer
from app.research.explainer import Explainer
from app.research.quiz import ExplainerQuiz, explainer_quiz
from app.research.stream import Emit

from .explainer_payload import stored_explainer
from .field_voices_readback import current_field_voices
from .simulation_hiding import with_hidden_marks
from .visible_claims import visible_claim_ids

__all__ = [
    "DONE_EVENT",
    "QUIZ_AVAILABLE_FIELD",
    "QuizOffer",
    "answer_offers_quiz",
    "owned_explainer",
    "shown_explainer",
    "shown_quiz",
    "with_quiz_offer",
]

logger = logging.getLogger(__name__)

DONE_EVENT = "done"
QUIZ_AVAILABLE_FIELD = "quizAvailable"

QuizOffer = Callable[[uuid.UUID], Awaitable[bool]]


async def owned_explainer(
    session: AsyncSession, answer_id: uuid.UUID, user_id: uuid.UUID
) -> Explainer | None:
    payload = await session.scalar(
        select(Answer.payload).where(Answer.id == answer_id, Answer.userId == user_id)
    )
    return stored_explainer(answer_id, payload)


async def shown_explainer(session: AsyncSession, explainer: Explainer) -> Explainer | None:
    return await current_field_voices(session, await with_hidden_marks(session, explainer))


async def shown_quiz(
    session: AsyncSession, shown: Explainer, section_ids: Sequence[str] = ()
) -> ExplainerQuiz | None:
    visible = await visible_claim_ids(session, shown)
    return explainer_quiz(shown, visible_claim_ids=visible, section_ids=section_ids)


async def answer_offers_quiz(
    sessions: async_sessionmaker[AsyncSession], answer_id: uuid.UUID, user_id: uuid.UUID
) -> bool:
    async with sessions() as session:
        explainer = await owned_explainer(session, answer_id, user_id)
        shown = await shown_explainer(session, explainer) if explainer is not None else None
        return shown is not None and await shown_quiz(session, shown) is not None


def with_quiz_offer(emit: Emit, offers: QuizOffer) -> Emit:
    async def marked(name: str, data: Any) -> None:
        if name == DONE_EVENT and isinstance(data, Mapping) and data.get("answerId"):
            data = await _offered(data, offers)
        await emit(name, data)

    return marked


async def _offered(done: Mapping[str, Any], offers: QuizOffer) -> Mapping[str, Any]:
    try:
        available = await offers(uuid.UUID(str(done["answerId"])))
    except (AppError, SQLAlchemyError) as error:
        logger.warning("whether answer %s offers a quiz is unknown: %s", done["answerId"], error)
        return done
    return {**done, QUIZ_AVAILABLE_FIELD: available}
