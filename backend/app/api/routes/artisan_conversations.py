from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, status
from fastapi.responses import JSONResponse, Response, StreamingResponse
from pydantic import ValidationError

from app.api.artisan_deps import artisan_store, artisan_voice_settings, require_artisan_conversation
from app.api.multipart_form import BodyTooLarge, limited_body, read_form
from app.api.voice_deps import voice_runtime, voice_store
from app.core.db import sessionmaker
from app.core.deps import get_current_user
from app.core.errors import AppError, InvalidInput, NotConfigured, Refused
from app.core.rate_limit import (
    voice_session_attempt,
    voice_speech_attempt,
    voice_turn_attempt,
)
from app.core.throttle_refusal import refuse_when_throttled
from app.models import User
from app.research.testimony import RECORDING_NOTICE_VERSION
from app.schemas.artisan import ConversationStartRequest
from app.schemas.voice import RELAY_AUDIO_TYPES, RELAY_MAX_AUDIO_BYTES, RELAY_MAX_WAV_BYTES
from app.schemas.voice_llm import CONVERSATION_HEADER, LlmChatRequest
from app.services.object_store import media_bucket
from app.voice.agent_turn import AgentCall
from app.voice.artisan_agent import artisan_agent_reply, authorised_artisan_session, heard_message
from app.voice.artisan_records import ConversationRecord
from app.voice.artisan_relay import ArtisanUpload, RelayTurnDeps, artisan_turn_events, conversation_speech
from app.voice.artisan_reply import ArtisanTools
from app.voice.artisan_session import (
    ARTISAN_MESSAGES,
    RECORDING_CONSENT_HEADER,
    ArtisanRefused,
    ConversationDeps,
    StartConversation,
    end_conversation,
    start_conversation,
)
from app.voice.artisan_store import SqlArtisanStore
from app.voice.artisan_wiring import artisan_tools, schedule_extraction
from app.voice.llm import UNAUTHORIZED_MESSAGE, error_body, reply_stream
from app.voice.runtime import VoiceRuntime, VoiceSettings
from app.voice.store import SqlVoiceStore

__all__ = ["router"]

logger = logging.getLogger(__name__)


router = APIRouter(
    prefix="/artisan", tags=["artisan conversations"], dependencies=[Depends(require_artisan_conversation)]
)

LLM_BODY_LIMIT = 512 * 1024
FORM_OVERHEAD_BYTES = 64 * 1024
UPLOAD_LIMIT = max(RELAY_MAX_AUDIO_BYTES, RELAY_MAX_WAV_BYTES)
AUDIO_FIELD = "audio"
CONTINUED_FIELD = "continued"
SSE_HEADERS = {"Cache-Control": "no-store", "X-Accel-Buffering": "no"}
THROTTLED = {
    "start": "You have started many conversations in a few minutes. Wait a little and try again.",
    "turn": "That is many turns in a few minutes. Wait a little and try again.",
    "speech": "That is many replays in a few minutes. Wait a little and try again.",
}
REFUSAL_STATUS = {
    "capability": status.HTTP_403_FORBIDDEN,
    "unverified_email": status.HTTP_403_FORBIDDEN,
    "consent": status.HTTP_403_FORBIDDEN,
    "language": status.HTTP_400_BAD_REQUEST,
    "craft": status.HTTP_422_UNPROCESSABLE_CONTENT,
    "not_configured": status.HTTP_503_SERVICE_UNAVAILABLE,
    "live_session": status.HTTP_409_CONFLICT,
    "quota": status.HTTP_429_TOO_MANY_REQUESTS,
    "busy": status.HTTP_503_SERVICE_UNAVAILABLE,
    "not_found": status.HTTP_404_NOT_FOUND,
    "speech_gone": status.HTTP_410_GONE,
}
AUDIO_DETAILS = {
    status.HTTP_413_CONTENT_TOO_LARGE: "That recording is too long.",
    status.HTTP_415_UNSUPPORTED_MEDIA_TYPE: "That recording format is not supported.",
    status.HTTP_400_BAD_REQUEST: "Couldn't hear that. Try again.",
}
ENDED_DETAIL = "This conversation has ended."


def utc_now() -> datetime:
    return datetime.now(UTC)


def refusal(error: ArtisanRefused) -> HTTPException:
    headers: dict[str, str] = {}
    if error.reason == "consent":
        headers[RECORDING_CONSENT_HEADER] = RECORDING_NOTICE_VERSION
    if error.retry_after:
        headers["Retry-After"] = str(error.retry_after)
    return HTTPException(REFUSAL_STATUS[error.reason], error.message, headers or None)


@router.post("/conversations", status_code=status.HTTP_201_CREATED)
async def start(
    payload: ConversationStartRequest,
    *,
    user: User = Depends(get_current_user),
    store: SqlVoiceStore = Depends(voice_store),
    runtime: VoiceRuntime = Depends(voice_runtime),
    voice: VoiceSettings = Depends(artisan_voice_settings),
    artisans: SqlArtisanStore = Depends(artisan_store),
) -> dict[str, Any]:
    refuse_when_throttled(voice_session_attempt(str(user.id)), THROTTLED["start"])
    ask = StartConversation(user, payload.craft_slug, payload.language, payload.notice_version)
    try:
        return await start_conversation(ask, _deps(store, artisans, runtime, voice))
    except ArtisanRefused as error:
        raise refusal(error) from None
    except AppError as error:
        logger.warning("an artisan conversation could not start: %s", error)
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, ARTISAN_MESSAGES["not_configured"]) from None


@router.post("/conversations/{conversation_id}/turns")
async def relay_turn(
    conversation_id: uuid.UUID,
    request: Request,
    *,
    user: User = Depends(get_current_user),
    store: SqlVoiceStore = Depends(voice_store),
    runtime: VoiceRuntime = Depends(voice_runtime),
    voice: VoiceSettings = Depends(artisan_voice_settings),
    artisans: SqlArtisanStore = Depends(artisan_store),
) -> StreamingResponse:
    conversation = await _owned(artisans, user, conversation_id)
    record = await store.by_id(conversation.voice_session_id) if conversation.voice_session_id else None
    if record is None or conversation.transport != "RELAY":
        raise refusal(ArtisanRefused("not_found"))
    if conversation.ended_at is not None or not record.live_at(utc_now()):
        raise HTTPException(status.HTTP_409_CONFLICT, ENDED_DETAIL)
    refuse_when_throttled(voice_turn_attempt(str(user.id)), THROTTLED["turn"])
    deps = _deps(store, artisans, runtime, voice)
    upload = await _upload(request, runtime)
    turn_deps = RelayTurnDeps(
        conversation=deps,
        tools=_tools(request, runtime, store, user.id, user.role),
        elevenlabs=runtime.elevenlabs(voice),
        bucket=media_bucket(),
        on_end=schedule_extraction(
            request.app.state.shielded_work, artisans=artisans, cipher=deps.cipher, role=user.role
        ),
        shield=request.app.state.shielded_work,
    )
    events = artisan_turn_events(conversation, upload, turn_deps)
    return StreamingResponse(events, media_type="text/event-stream", headers=SSE_HEADERS)


@router.get("/conversations/{conversation_id}/turns/{turn_id}/speech")
async def speech(
    conversation_id: uuid.UUID,
    turn_id: uuid.UUID,
    *,
    user: User = Depends(get_current_user),
    store: SqlVoiceStore = Depends(voice_store),
    runtime: VoiceRuntime = Depends(voice_runtime),
    voice: VoiceSettings = Depends(artisan_voice_settings),
    artisans: SqlArtisanStore = Depends(artisan_store),
) -> Response:
    conversation = await _owned(artisans, user, conversation_id)
    record = await store.by_id(conversation.voice_session_id) if conversation.voice_session_id else None
    if record is None or conversation.transport != "RELAY":
        raise refusal(ArtisanRefused("not_found"))
    refuse_when_throttled(voice_speech_attempt(str(user.id)), THROTTLED["speech"])
    try:
        audio = await conversation_speech(
            conversation, record, turn_id, _deps(store, artisans, runtime, voice)
        )
    except ArtisanRefused as error:
        raise refusal(error) from None
    except AppError as error:
        logger.warning("artisan reply speech failed: %s", error)
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, ARTISAN_MESSAGES["not_configured"]) from None
    return Response(content=audio, media_type="audio/mpeg", headers={"Cache-Control": "private, no-store"})


@router.post("/conversations/{conversation_id}/end")
async def end(
    conversation_id: uuid.UUID,
    request: Request,
    background: BackgroundTasks,
    *,
    user: User = Depends(get_current_user),
    store: SqlVoiceStore = Depends(voice_store),
    runtime: VoiceRuntime = Depends(voice_runtime),
    voice: VoiceSettings = Depends(artisan_voice_settings),
    artisans: SqlArtisanStore = Depends(artisan_store),
) -> dict[str, Any]:
    conversation = await _owned(artisans, user, conversation_id)
    deps = _deps(store, artisans, runtime, voice)
    payload, finished = await end_conversation(conversation, deps, now=utc_now())
    scheduled = schedule_extraction(
        request.app.state.shielded_work, artisans=artisans, cipher=deps.cipher, role=user.role
    )
    background.add_task(scheduled, finished)
    return payload


@router.post("/llm/v1/chat/completions", response_model=None)
async def custom_llm(
    request: Request,
    store: SqlVoiceStore = Depends(voice_store),
    runtime: VoiceRuntime = Depends(voice_runtime),
    voice: VoiceSettings = Depends(artisan_voice_settings),
    artisans: SqlArtisanStore = Depends(artisan_store),
) -> Response:
    now = utc_now()
    if voice.cipher is None:
        return _llm_error(
            status.HTTP_503_SERVICE_UNAVAILABLE, "unavailable", ARTISAN_MESSAGES["not_configured"]
        )
    deps = _deps(store, artisans, runtime, voice)
    call = AgentCall(request.headers.get("authorization"), request.headers.get(CONVERSATION_HEADER))
    try:
        record, conversation = await authorised_artisan_session(deps, call, now=now)
    except ArtisanRefused:
        return _llm_error(status.HTTP_401_UNAUTHORIZED, "unauthorized", UNAUTHORIZED_MESSAGE)
    try:
        chat = LlmChatRequest.model_validate_json(await limited_body(request, LLM_BODY_LIMIT))
    except ValidationError, BodyTooLarge:
        return _llm_error(
            status.HTTP_400_BAD_REQUEST, "bad_request", "The request is not a streamed chat turn."
        )
    on_end = schedule_extraction(
        request.app.state.shielded_work, artisans=artisans, cipher=deps.cipher, role=record.role
    )
    tools = _tools(request, runtime, store, record.user_id, record.role)
    reply = artisan_agent_reply(
        record, conversation, heard_message(chat), deps=deps, tools=tools, on_end=on_end
    )
    stream = reply_stream(reply, turn_id=uuid.uuid4(), created=int(now.timestamp()), language=record.language)
    return StreamingResponse(stream, media_type="text/event-stream", headers=SSE_HEADERS)


def _deps(
    store: SqlVoiceStore, artisans: SqlArtisanStore, runtime: VoiceRuntime, voice: VoiceSettings
) -> ConversationDeps:
    if voice.cipher is None:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, ARTISAN_MESSAGES["not_configured"])
    return ConversationDeps(
        store=store,
        artisans=artisans,
        runtime=runtime,
        voice=voice,
        cipher=voice.cipher,
        speech=runtime.replies(),
        clock=utc_now,
    )


def _tools(
    request: Request, runtime: VoiceRuntime, store: SqlVoiceStore, user_id: uuid.UUID, role: str
) -> ArtisanTools:
    return artisan_tools(
        runtime=runtime,
        store=store,
        sessions=sessionmaker(),
        index=request.app.state.craft_index,
        user_id=user_id,
        role=role,
    )


async def _owned(artisans: SqlArtisanStore, user: User, conversation_id: uuid.UUID) -> ConversationRecord:
    conversation = await artisans.by_id(conversation_id)
    if conversation is None or conversation.user_id != user.id or conversation.deleted_at is not None:
        raise refusal(ArtisanRefused("not_found"))
    return conversation


async def _upload(request: Request, runtime: VoiceRuntime) -> ArtisanUpload:
    limit = UPLOAD_LIMIT + FORM_OVERHEAD_BYTES
    try:
        form = await read_form(request, limit, files=[AUDIO_FIELD], texts=[CONTINUED_FIELD])
    except BodyTooLarge:
        raise _audio_refusal(status.HTTP_413_CONTENT_TOO_LARGE) from None
    except InvalidInput:
        raise _audio_refusal(status.HTTP_400_BAD_REQUEST) from None
    audio = form.file(AUDIO_FIELD)
    if audio.content_type not in RELAY_AUDIO_TYPES:
        raise _audio_refusal(status.HTTP_415_UNSUPPORTED_MEDIA_TYPE)
    if not audio.content:
        raise _audio_refusal(status.HTTP_400_BAD_REQUEST)
    continued = (form.text(CONTINUED_FIELD) or "").strip() == "true"
    try:
        return await ArtisanUpload.measured(
            audio.content, audio.content_type, runtime.measure, continued=continued
        )
    except Refused:
        raise _audio_refusal(status.HTTP_413_CONTENT_TOO_LARGE) from None
    except InvalidInput:
        raise _audio_refusal(status.HTTP_400_BAD_REQUEST) from None
    except NotConfigured:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, ARTISAN_MESSAGES["not_configured"]) from None


def _audio_refusal(code: int) -> HTTPException:
    return HTTPException(code, AUDIO_DETAILS[code])


def _llm_error(code: int, error_code: str, message: str) -> JSONResponse:
    return JSONResponse(status_code=code, content=error_body(error_code, message).model_dump(mode="json"))
