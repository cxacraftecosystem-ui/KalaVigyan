from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from fastapi import Depends, HTTPException, status

from app.api.voice_deps import current_voice
from app.core.db import sessionmaker
from app.core.deps import get_current_user
from app.core.errors import AppError
from app.core.rate_limit import film_score_attempt
from app.core.roles import Capability, can, is_uncapped
from app.core.shielded import ShieldedWork
from app.core.throttle_refusal import refuse_when_throttled
from app.models import User
from app.providers.catalogue import AiTask
from app.providers.media_router import MediaAsk, MediaRouter
from app.providers.router import Principal
from app.schemas.film import SCORE_POLL_SECONDS, FilmOffer, FilmScore, FilmScoreMaking
from app.services.object_store import media_bucket
from app.voice.film_scenes import BED_SECONDS_MIN
from app.voice.film_score import (
    ScoreAsk,
    ScoreBeingMade,
    ScoreDeps,
    ScoreMaker,
    current_score,
    made_score,
    planned_score,
    score_in_making,
)
from app.voice.film_store import SqlFilmStore
from app.voice.object_lease import LeasedObjects
from app.voice.score_prompts import SCORE_MUSIC_PROMPT

__all__ = [
    "NO_SCORE",
    "SCORE_WAIT_SECONDS",
    "THROTTLED_DETAIL",
    "UNAVAILABLE_DETAIL",
    "FilmTools",
    "answered_score",
    "film_store",
    "film_tools",
    "offered_film",
]

logger = logging.getLogger(__name__)

UNAVAILABLE_DETAIL = "Music for this film isn't available right now. Try again later."
THROTTLED_DETAIL = "You have asked for film music many times in a few minutes. Wait a little and try again."
NO_SCORE: dict[str, Any] = {"score": False}
SCORE_WAIT_SECONDS = 45.0


@dataclass(frozen=True)
class FilmTools:
    objects: LeasedObjects
    maker: ScoreMaker
    voice_id: str | None = None


def film_store() -> SqlFilmStore:
    return SqlFilmStore(sessionmaker())


async def film_tools() -> FilmTools:
    objects = media_bucket()
    if objects is None:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, UNAVAILABLE_DETAIL)
    voice = await current_voice()
    return FilmTools(
        objects=objects, maker=MediaRouter(session_factory=sessionmaker()), voice_id=voice.voice_id or None
    )


async def answered_score(
    ask: ScoreAsk, deps: ScoreDeps, shield: ShieldedWork, user: User
) -> FilmScore | FilmScoreMaking:
    plan = await planned_score(ask, deps)
    found = await current_score(ask, deps, plan)
    if found is not None:
        return found
    if await score_in_making(ask, deps):
        return _making(ask)
    if not is_uncapped(user):
        refuse_when_throttled(await film_score_attempt(str(user.id)), THROTTLED_DETAIL)
    name = f"film score of answer {ask.explainer.answer_id}"
    try:
        return await shield.run_within(made_score(ask, deps, plan), name=name, seconds=SCORE_WAIT_SECONDS)
    except TimeoutError, ScoreBeingMade:
        return _making(ask)


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


def _making(ask: ScoreAsk) -> FilmScoreMaking:
    explainer = ask.explainer
    return FilmScoreMaking(
        answer_id=explainer.answer_id,
        language=explainer.understood.language,
        poll_after_seconds=SCORE_POLL_SECONDS,
    )
