from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status

from app.api.film_deps import UNAVAILABLE_DETAIL, FilmTools, answered_score, film_store, film_tools
from app.core.deps import require
from app.core.errors import AppError
from app.core.roles import Capability
from app.models import User
from app.providers.router import Principal
from app.research.vocabulary import AnswerLanguage
from app.schemas.film import FilmScoreMaking
from app.voice.film_score import NOTHING_MESSAGE, ScoreAsk, ScoreDeps, ScoreRefused
from app.voice.film_store import SqlFilmStore

router = APIRouter(prefix="/answers", tags=["film"])
logger = logging.getLogger(__name__)


def utc_now() -> datetime:
    return datetime.now(UTC)


@router.get("/{answer_id}/film-score")
async def film_score_of(
    answer_id: uuid.UUID,
    language: AnswerLanguage,
    request: Request,
    response: Response,
    *,
    user: User = Depends(require(Capability.VOICE)),
    store: SqlFilmStore = Depends(film_store),
    tools: FilmTools = Depends(film_tools),
) -> dict[str, Any]:
    explainer = await store.explainer(answer_id, user.id)
    if explainer is None or explainer.understood.language != language:
        raise HTTPException(status.HTTP_404_NOT_FOUND, NOTHING_MESSAGE)
    ask = ScoreAsk(principal=Principal(user_id=user.id, role=user.role), explainer=explainer)
    deps = ScoreDeps(objects=tools.objects, maker=tools.maker, clock=utc_now, voice_id=tools.voice_id)
    try:
        answer = await answered_score(ask, deps, request.app.state.shielded_work, user)
    except ScoreRefused as error:
        raise HTTPException(status.HTTP_404_NOT_FOUND, error.message) from None
    except AppError as error:
        logger.warning("the film score of answer %s failed: %s", answer_id, error)
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, UNAVAILABLE_DETAIL) from None
    if isinstance(answer, FilmScoreMaking):
        response.status_code = status.HTTP_202_ACCEPTED
    return answer.model_dump(mode="json", by_alias=True)
