from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import JSONResponse, Response, StreamingResponse
from pydantic import ValidationError

from app.api.multipart_form import BodyTooLarge, limited_body, read_form
from app.api.voice_deps import current_voice, require_voice_call, voice_runtime, voice_store
from app.core.config import get_settings
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
from app.schemas.voice import (
    RELAY_AUDIO_TYPES,
    RELAY_MAX_AUDIO_BYTES,
    RELAY_MAX_WAV_BYTES,
    VoiceSessionRequest,
)
from app.schemas.voice_llm import CONVERSATION_HEADER, LlmChatRequest
from app.voice.agent_turn import AgentCall, agent_reply, authorised_session, last_question
from app.voice.llm import UNAUTHORIZED_MESSAGE, error_body, reply_stream
from app.voice.notice import VOICE_NOTICE_VERSION, voice_notice
from app.voice.records import SessionRecord
from app.voice.relay import RelayAudio, RelayDeps, relay_turn_events, turn_speech
from app.voice.runtime import VoiceRuntime, VoiceSettings
from app.voice.sessions import (
    MESSAGES,
    VOICE_CONSENT_HEADER,
    StartAsk,
    VoiceRefused,
    end_session,
    owned_session,
    start_session,
)
from app.voice.store import SqlVoiceStore
from app.voice.transcript import stored_transcript, transcript_view
from app.voice.turns import TurnTools
from app.voice.wiring import turn_tools

router = APIRouter(prefix="/voice", tags=["voice"], dependencies=[Depends(require_voice_call)])
logger = logging.getLogger(__name__)

LLM_BODY_LIMIT = 512 * 1024
FORM_OVERHEAD_BYTES = 64 * 1024
SSE_HEADERS = {"Cache-Control": "no-store", "X-Accel-Buffering": "no"}
THROTTLED_DETAIL = "You have started many calls in a few minutes. Wait a little and try again."
TURNS_THROTTLED_DETAIL = "That is many turns in a few minutes. Wait a little and try again."
SPEECH_THROTTLED_DETAIL = "That is many replays in a few minutes. Wait a little and try again."
UPLOAD_LIMIT = max(RELAY_MAX_AUDIO_BYTES, RELAY_MAX_WAV_BYTES)
AUDIO_FIELD = "audio"
REFUSAL_STATUS = {
    "capability": status.HTTP_403_FORBIDDEN,
    "unverified_email": status.HTTP_403_FORBIDDEN,
    "consent": status.HTTP_403_FORBIDDEN,
    "language": status.HTTP_400_BAD_REQUEST,
    "craft": status.HTTP_404_NOT_FOUND,
    "not_configured": status.HTTP_503_SERVICE_UNAVAILABLE,
    "live_session": status.HTTP_409_CONFLICT,
    "quota": status.HTTP_429_TOO_MANY_REQUESTS,
    "busy": status.HTTP_503_SERVICE_UNAVAILABLE,
    "not_found": status.HTTP_404_NOT_FOUND,
    "ended": status.HTTP_409_CONFLICT,
    "speech_gone": status.HTTP_410_GONE,
}
ENDED_DETAIL = "This call has ended."
AUDIO_DETAILS = {
    status.HTTP_413_CONTENT_TOO_LARGE: "That recording is too long.",
    status.HTTP_415_UNSUPPORTED_MEDIA_TYPE: "That recording format is not supported.",
    status.HTTP_400_BAD_REQUEST: "Couldn't hear that. Try again.",
}


def utc_now() -> datetime:
    return datetime.now(UTC)


def refusal(error: VoiceRefused) -> HTTPException:
    headers: dict[str, str] = {}
    if error.reason == "consent":
        headers[VOICE_CONSENT_HEADER] = VOICE_NOTICE_VERSION
    if error.retry_after:
        headers["Retry-After"] = str(error.retry_after)
    return HTTPException(REFUSAL_STATUS[error.reason], error.message, headers or None)


@router.get("/notice")
async def notice(_: User = Depends(get_current_user)) -> dict[str, Any]:
    return voice_notice(get_settings().mail_reply_to)


@router.post("/session", status_code=status.HTTP_201_CREATED)
async def start(
    payload: VoiceSessionRequest,
    user: User = Depends(get_current_user),
    store: SqlVoiceStore = Depends(voice_store),
    runtime: VoiceRuntime = Depends(voice_runtime),
    voice: VoiceSettings = Depends(current_voice),
) -> dict[str, Any]:
    refuse_when_throttled(voice_session_attempt(str(user.id)), THROTTLED_DETAIL)
    ask = StartAsk(user=user, craft_slug=payload.craft_slug, mode=payload.mode, language=payload.language)
    try:
        return await start_session(ask, store=store, runtime=runtime, voice=voice, now=utc_now())
    except VoiceRefused as error:
        raise refusal(error) from None
    except AppError as error:
        logger.warning("voice session could not start: %s", error)
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, MESSAGES["not_configured"]) from None


@router.post("/session/{session_id}/end")
async def end(
    session_id: uuid.UUID, user: User = Depends(get_current_user), store: SqlVoiceStore = Depends(voice_store)
) -> dict[str, Any]:
    try:
        return await end_session(store, user, session_id, now=utc_now())
    except VoiceRefused as error:
        raise refusal(error) from None


@router.get("/session/{session_id}/transcript")
async def transcript(
    session_id: uuid.UUID,
    user: User = Depends(get_current_user),
    store: SqlVoiceStore = Depends(voice_store),
    voice: VoiceSettings = Depends(current_voice),
) -> dict[str, Any]:
    record = await _owned(store, user, session_id)
    if record.retention_until is not None and record.retention_until <= utc_now():
        raise refusal(VoiceRefused("not_found"))
    if voice.cipher is None:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, MESSAGES["not_configured"])
    return transcript_view(record, stored_transcript(voice.cipher, record.transcript))


@router.post("/llm/v1/chat/completions", response_model=None)
async def custom_llm(
    request: Request,
    store: SqlVoiceStore = Depends(voice_store),
    runtime: VoiceRuntime = Depends(voice_runtime),
    voice: VoiceSettings = Depends(current_voice),
) -> Response:
    now = utc_now()
    call = AgentCall(request.headers.get("authorization"), request.headers.get(CONVERSATION_HEADER))
    try:
        record = await authorised_session(store, voice, call, now=now)
    except VoiceRefused:
        return _llm_error(status.HTTP_401_UNAUTHORIZED, "unauthorized", UNAUTHORIZED_MESSAGE)
    try:
        chat = LlmChatRequest.model_validate_json(await limited_body(request, LLM_BODY_LIMIT))
    except ValidationError, BodyTooLarge:
        return _llm_error(
            status.HTTP_400_BAD_REQUEST, "bad_request", "The request is not a streamed chat turn."
        )
    if voice.cipher is None:
        return _llm_error(status.HTTP_503_SERVICE_UNAVAILABLE, "unavailable", MESSAGES["not_configured"])
    tools = _tools(request, runtime, store, record)
    reply = agent_reply(
        record, last_question(chat), store=store, tools=tools, cipher=voice.cipher, clock=utc_now
    )
    stream = reply_stream(reply, turn_id=uuid.uuid4(), created=int(now.timestamp()), language=record.language)
    return StreamingResponse(stream, media_type="text/event-stream", headers=SSE_HEADERS)


@router.post("/session/{session_id}/turns")
async def relay_turn(
    session_id: uuid.UUID,
    request: Request,
    *,
    user: User = Depends(get_current_user),
    store: SqlVoiceStore = Depends(voice_store),
    runtime: VoiceRuntime = Depends(voice_runtime),
    voice: VoiceSettings = Depends(current_voice),
) -> StreamingResponse:
    record = await _relay_session(store, user, session_id)
    if not record.live_at(utc_now()):
        raise HTTPException(status.HTTP_409_CONFLICT, ENDED_DETAIL)
    refuse_when_throttled(voice_turn_attempt(str(user.id)), TURNS_THROTTLED_DETAIL)
    if voice.missing() or voice.cipher is None:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, MESSAGES["not_configured"])
    audio = await _recording(request, runtime)
    deps = _relay_deps(request, runtime, store, voice, record)
    return StreamingResponse(
        relay_turn_events(record, audio, deps), media_type="text/event-stream", headers=SSE_HEADERS
    )


@router.get("/session/{session_id}/turns/{turn_id}/speech")
async def speech(
    session_id: uuid.UUID,
    turn_id: uuid.UUID,
    request: Request,
    *,
    user: User = Depends(get_current_user),
    store: SqlVoiceStore = Depends(voice_store),
    runtime: VoiceRuntime = Depends(voice_runtime),
    voice: VoiceSettings = Depends(current_voice),
) -> Response:
    record = await _relay_session(store, user, session_id)
    if voice.missing() or voice.cipher is None:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, MESSAGES["not_configured"])
    refuse_when_throttled(voice_speech_attempt(str(user.id)), SPEECH_THROTTLED_DETAIL)
    try:
        audio = await turn_speech(record, turn_id, _relay_deps(request, runtime, store, voice, record))
    except VoiceRefused as error:
        raise refusal(error) from None
    except AppError as error:
        logger.warning("relay speech failed: %s", error)
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, MESSAGES["not_configured"]) from None
    return Response(content=audio, media_type="audio/mpeg", headers={"Cache-Control": "private, no-store"})


async def _owned(store: SqlVoiceStore, user: User, session_id: uuid.UUID) -> SessionRecord:
    try:
        return await owned_session(store, user, session_id)
    except VoiceRefused as error:
        raise refusal(error) from None


async def _relay_session(store: SqlVoiceStore, user: User, session_id: uuid.UUID) -> SessionRecord:
    record = await _owned(store, user, session_id)
    if record.transport != "RELAY":
        raise refusal(VoiceRefused("not_found"))
    return record


async def _recording(request: Request, runtime: VoiceRuntime) -> RelayAudio:
    limit = UPLOAD_LIMIT + FORM_OVERHEAD_BYTES
    try:
        upload = (await read_form(request, limit, files=[AUDIO_FIELD])).file(AUDIO_FIELD)
    except BodyTooLarge:
        raise _audio_refusal(status.HTTP_413_CONTENT_TOO_LARGE) from None
    except InvalidInput:
        raise _audio_refusal(status.HTTP_400_BAD_REQUEST) from None
    if upload.content_type not in RELAY_AUDIO_TYPES:
        raise _audio_refusal(status.HTTP_415_UNSUPPORTED_MEDIA_TYPE)
    if not upload.content:
        raise _audio_refusal(status.HTTP_400_BAD_REQUEST)
    try:
        return await RelayAudio.measured(upload.content, upload.content_type, runtime.measure)
    except Refused:
        raise _audio_refusal(status.HTTP_413_CONTENT_TOO_LARGE) from None
    except InvalidInput:
        raise _audio_refusal(status.HTTP_400_BAD_REQUEST) from None
    except NotConfigured:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, MESSAGES["not_configured"]) from None


def _audio_refusal(code: int) -> HTTPException:
    return HTTPException(code, AUDIO_DETAILS[code])


def _tools(request: Request, runtime: VoiceRuntime, store: SqlVoiceStore, record: SessionRecord) -> TurnTools:
    return turn_tools(
        runtime=runtime,
        store=store,
        sessions=sessionmaker(),
        index=request.app.state.craft_index,
        user_id=record.user_id,
        role=record.role,
    )


def _relay_deps(
    request: Request, runtime: VoiceRuntime, store: SqlVoiceStore, voice: VoiceSettings, record: SessionRecord
) -> RelayDeps:
    if voice.cipher is None:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, MESSAGES["not_configured"])
    return RelayDeps(
        store=store,
        tools=_tools(request, runtime, store, record),
        elevenlabs=runtime.elevenlabs(voice),
        cipher=voice.cipher,
        speech=runtime.replies(),
        voice_id=voice.voice_id,
        clock=utc_now,
        shield=request.app.state.shielded_work,
    )


def _llm_error(code: int, error_code: str, message: str) -> JSONResponse:
    return JSONResponse(status_code=code, content=error_body(error_code, message).model_dump(mode="json"))
