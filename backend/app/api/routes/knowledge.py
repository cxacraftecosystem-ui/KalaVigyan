import hashlib
import logging
from collections.abc import Callable
from dataclasses import replace
from datetime import UTC, datetime
from functools import lru_cache, partial
from pathlib import Path
from typing import Any, Self

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import StreamingResponse
from pydantic import Field, model_validator
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.artisan_deps import offered_conversation
from app.api.film_deps import offered_film
from app.api.listen_deps import offered_listen
from app.api.public_deps import cached_read, public_reader
from app.api.reading_deps import asker_style
from app.api.voice_deps import current_voice, voice_call_enabled, voice_runtime, voice_store
from app.core.config import get_settings
from app.core.db import get_session, sessionmaker
from app.core.deps import get_current_user, refusal_for
from app.core.errors import AppError
from app.core.rate_limit import ask_attempt
from app.core.roles import Capability, can, is_uncapped, role_value
from app.core.throttle_refusal import refuse_when_throttled
from app.models import User
from app.providers.answer_routes import answer_models
from app.providers.budget import AnswerSpend
from app.providers.embedding import router_embedder
from app.providers.router import Principal
from app.research.depth import DEPTH_LABELS, default_depth, selectable_depths
from app.research.explainer_versions import BuildsOn
from app.research.planning import withheld_name
from app.research.reading_style import ReadingStyle
from app.research.stream import event_stream
from app.research.vocabulary import ANSWER_LANGUAGES, AnswerLanguage, Depth, language_option
from app.schemas.common import APIModel
from app.services import knowledge_view
from app.services.answer_quiz import answer_offers_quiz, with_quiz_offer
from app.services.answer_store import build_answer_pipeline
from app.services.answering import AnswerAsk, AnswerPipeline, answer_question
from app.services.explainer_history import (
    STALE_VERSION_DETAIL,
    UNKNOWN_EXPLAINER_DETAIL,
    StaleVersion,
    UnknownExplainer,
    follow_up_of,
)
from app.services.follow_ups import FollowUp
from app.voice.availability import HIDDEN_VOICE, voice_availability
from app.voice.runtime import VoiceRuntime, VoiceSettings
from app.voice.store import SqlVoiceStore

router = APIRouter(tags=["knowledge"])
logger = logging.getLogger(__name__)

NOTICE_PATH = Path(__file__).resolve().parents[2] / "data" / "privacy_notice.md"
NOTICE_VERSION = "2026-11-18"
NOTICE_PUBLISHED_AT = "2026-11-18T00:00:00+05:30"
NOTICE_TITLE = "Privacy notice"

THROTTLED_DETAIL = "You have asked a lot in the last few minutes. Wait a little and ask again."


@lru_cache
def privacy_notice_text() -> str:
    return NOTICE_PATH.read_text(encoding="utf-8")


def notice_sha256() -> str:
    return hashlib.sha256(privacy_notice_text().encode("utf-8")).hexdigest()


@router.get("/privacy/notice")
async def privacy_notice() -> dict[str, Any]:
    settings = get_settings()
    address = (settings.mail_reply_to or "").strip()
    contact = f", or write to {address}" if address else ""
    return {
        "version": NOTICE_VERSION,
        "title": NOTICE_TITLE,
        "body": privacy_notice_text().replace("{contact}", contact),
        "publishedAt": NOTICE_PUBLISHED_AT,
    }


@router.get("/map/crafts")
async def map_crafts(
    request: Request,
    response: Response,
    reader: User | None = Depends(public_reader),
    session: AsyncSession = Depends(get_session),
) -> Any:
    return cached_read(request, response, reader, await knowledge_view.map_points(session))


async def offered_voice(
    user: User = Depends(get_current_user),
    store: SqlVoiceStore = Depends(voice_store),
    runtime: VoiceRuntime = Depends(voice_runtime),
    voice: VoiceSettings = Depends(current_voice),
    enabled: bool = Depends(voice_call_enabled),
) -> dict[str, Any]:
    if not enabled:
        return dict(HIDDEN_VOICE)
    try:
        return await voice_availability(
            user, store=store, runtime=runtime, voice=voice, now=datetime.now(UTC)
        )
    except AppError as error:
        logger.warning("voice availability could not be read, voice hidden: %s", error)
        return dict(HIDDEN_VOICE)


@router.get("/answers/config")
async def answers_config(
    user: User = Depends(get_current_user),
    voice: dict[str, Any] = Depends(offered_voice),
    listen: dict[str, Any] = Depends(offered_listen),
    film: dict[str, Any] = Depends(offered_film),
    conversation: dict[str, Any] = Depends(offered_conversation),
) -> dict[str, Any]:
    depths = selectable_depths(user)
    return {
        "depths": [{"depth": depth, "label": DEPTH_LABELS[depth]} for depth in depths],
        "defaultDepth": default_depth(user) if depths else None,
        "voice": voice,
        "listen": listen,
        "film": film,
        "conversation": conversation,
        "languages": answer_languages(),
    }


class AskRequest(APIModel):
    question: str = Field(min_length=2, max_length=1000)
    depth: Depth | None = None
    craftSlug: str | None = Field(default=None, min_length=1, max_length=200)
    anyCraft: bool = False
    language: AnswerLanguage | None = None
    fresh: bool = False
    conversationId: str | None = Field(default=None, max_length=64)
    buildsOn: BuildsOn | None = None

    @model_validator(mode="after")
    def _one_craft_or_any(self) -> Self:
        if self.anyCraft and self.craftSlug is not None:
            raise ValueError("Ask about one craft or any craft, not both.")
        if self.buildsOn is not None and (self.anyCraft or self.craftSlug or self.depth or self.language):
            raise ValueError("A follow-up keeps the explainer's craft, depth and language.")
        return self


def answer_languages() -> list[dict[str, str]]:
    return [language_option(code) for code in ANSWER_LANGUAGES]


def withheld_terms(user: User) -> tuple[str, ...]:
    return withheld_name(user.name)


PipelineFor = Callable[[str], AnswerPipeline]


def answer_pipelines(request: Request, user: User = Depends(get_current_user)) -> PipelineFor:
    def build(depth: str) -> AnswerPipeline:
        spend = AnswerSpend(depth=depth)
        principal = Principal(user_id=user.id, role=user.role, answer=spend)
        optional = Principal(user_id=user.id, role=user.role, answer=spend.headroom())
        return build_answer_pipeline(
            sessions=sessionmaker(),
            index=request.app.state.craft_index,
            live=request.app.state.live_sources,
            models=answer_models(depth, principal=principal, optional=optional),
            embed=router_embedder(principal),
            shield=request.app.state.shielded_work,
        )

    return build


async def follow_up_for(builds_on: BuildsOn | None, user: User) -> FollowUp | None:
    if builds_on is None:
        return None
    try:
        async with sessionmaker()() as session:
            return await follow_up_of(session, user.id, builds_on)
    except UnknownExplainer:
        raise HTTPException(status.HTTP_404_NOT_FOUND, UNKNOWN_EXPLAINER_DETAIL) from None
    except StaleVersion:
        raise HTTPException(status.HTTP_409_CONFLICT, STALE_VERSION_DETAIL) from None


def asked(payload: AskRequest, user: User, follow_up: FollowUp | None) -> AnswerAsk:
    ask = AnswerAsk(
        question=payload.question,
        depth=payload.depth or default_depth(user),
        craft_slug=payload.craftSlug,
        any_craft=payload.anyCraft,
        language=payload.language,
        user_id=user.id,
        role=role_value(user),
        withheld_terms=withheld_terms(user),
        fresh=payload.fresh,
    )
    if follow_up is None:
        return ask
    return replace(
        ask,
        depth=follow_up.understood.depth,
        craft_slug=follow_up.craft_slug,
        any_craft=follow_up.craft_slug is None,
        language=follow_up.understood.language,
        builds_on=follow_up,
    )


@router.post("/answers/stream")
async def answers_stream(
    payload: AskRequest,
    user: User = Depends(get_current_user),
    pipelines: PipelineFor = Depends(answer_pipelines),
    style: ReadingStyle | None = Depends(asker_style),
) -> StreamingResponse:
    ask = replace(asked(payload, user, await follow_up_for(payload.buildsOn, user)), reading_style=style)
    if not can(user, Capability.ASK_STANDARD) or ask.depth not in selectable_depths(user):
        raise HTTPException(status.HTTP_403_FORBIDDEN, refusal_for(Capability.ASK_STANDARD))
    if not is_uncapped(user):
        refuse_when_throttled(ask_attempt(str(user.id)), THROTTLED_DETAIL)
    pipeline = pipelines(ask.depth)
    offers = partial(answer_offers_quiz, sessionmaker(), user_id=user.id)
    return StreamingResponse(
        event_stream(lambda emit: answer_question(ask, pipeline, with_quiz_offer(emit, offers))),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"},
    )
