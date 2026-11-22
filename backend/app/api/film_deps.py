from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from fastapi import Depends, HTTPException, status

from app.core.db import sessionmaker
from app.core.deps import get_current_user
from app.core.errors import AppError
from app.core.roles import Capability, can
from app.models import User
from app.providers.catalogue import AiTask
from app.providers.media_router import MediaAsk, MediaRouter
from app.providers.router import Principal
from app.schemas.film import FilmOffer
from app.services.object_store import media_bucket
from app.voice.film_scenes import BED_SECONDS_MIN
from app.voice.film_score import ScoreMaker
from app.voice.film_store import SqlFilmStore
from app.voice.narration_cache import NarrationObjects
from app.voice.score_prompts import SCORE_MUSIC_PROMPT

__all__ = ["NO_SCORE", "UNAVAILABLE_DETAIL", "FilmTools", "film_store", "film_tools", "offered_film"]

logger = logging.getLogger(__name__)

UNAVAILABLE_DETAIL = "Music for this film isn't available right now. Try again later."
NO_SCORE: dict[str, Any] = {"score": False}


@dataclass(frozen=True)
class FilmTools:
    objects: NarrationObjects
    maker: ScoreMaker


def film_store() -> SqlFilmStore:
    return SqlFilmStore(sessionmaker())


def film_tools() -> FilmTools:
    objects = media_bucket()
    if objects is None:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, UNAVAILABLE_DETAIL)
    return FilmTools(objects=objects, maker=MediaRouter(session_factory=sessionmaker()))


async def offered_film(user: User = Depends(get_current_user)) -> dict[str, Any]:
    if not can(user, Capability.VOICE) or media_bucket() is None:
        return dict(NO_SCORE)
    ask = MediaAsk(
        task=AiTask.MUSIC,
        prompt=SCORE_MUSIC_PROMPT,
        output={"seconds": str(BED_SECONDS_MIN)},
        units=float(BED_SECONDS_MIN),
        principal=Principal(user_id=user.id, role=user.role),
    )
    try:
        score = await MediaRouter(session_factory=sessionmaker()).available(ask)
    except AppError as error:
        logger.warning("the film score could not be checked, its control is hidden: %s", error)
        return dict(NO_SCORE)
    return FilmOffer(score=score).model_dump(mode="json", by_alias=True)
