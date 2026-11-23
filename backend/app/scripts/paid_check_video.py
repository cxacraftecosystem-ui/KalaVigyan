from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from app.core.errors import AppError
from app.media.mp4 import video_facts
from app.media.output import checked_output
from app.media.prompt import REQUESTED_OUTPUT, billed_units
from app.providers.base import MediaRequest, MediaResult
from app.providers.budget import unit_cost
from app.providers.catalogue import DEFAULT_ROUTES, AiTask, model_for
from app.providers.gemini_media import GeminiMediaWire
from app.providers.media_router import VIDEO_POLL_SECONDS

from .paid_check_ledger import Recorded, Recorder
from .paid_check_steps import CheckResult, recorded_reply, refused_reply

__all__ = [
    "VIDEO_KIND",
    "VIDEO_MODEL",
    "VIDEO_PROMPT",
    "VIDEO_WAIT_SECONDS",
    "VideoTimes",
    "video_check",
    "video_estimate",
]

VIDEO_KIND = "VIDEO"
VIDEO_PROVIDER, VIDEO_MODEL = DEFAULT_ROUTES[AiTask.VIDEO][0]
VIDEO_WAIT_SECONDS = 900.0
INTERACTIONS = "/interactions"
VIDEO_PROMPT = (
    "Show one stage of an Indian craft process as a calm, neutral documentary video clip with no speech, "
    "music or sound: a length of plain cotton cloth soaking in a shallow metal vat of water. Rules: no text, "
    "letters or numbers; no logos; no faces of real people; no maps, borders or flags."
)


@dataclass(frozen=True)
class VideoTimes:
    wait_seconds: float = VIDEO_WAIT_SECONDS
    poll_seconds: float = VIDEO_POLL_SECONDS
    sleep: Callable[[float], Awaitable[None]] = asyncio.sleep
    clock: Callable[[], float] = time.monotonic


@dataclass
class _Watched:
    result: MediaResult | None = None
    polls: int = 0
    seconds: float = 0.0
    open_reply: Recorded | None = None
    done_reply: Recorded | None = None


def video_estimate() -> Decimal:
    return unit_cost(model_for(VIDEO_PROVIDER, VIDEO_MODEL), billed_units(VIDEO_KIND))


async def video_check(
    gemini: GeminiMediaWire, recorder: Recorder, times: VideoTimes | None = None
) -> CheckResult:
    request = MediaRequest(
        model=VIDEO_MODEL, prompt=VIDEO_PROMPT, kind=VIDEO_KIND, output=dict(REQUESTED_OUTPUT[VIDEO_KIND])
    )
    try:
        ref = await gemini.start_video(request)
    except AppError as error:
        return refused_reply(recorder, INTERACTIONS, "video_refused.json", error)
    files = recorded_reply(recorder, INTERACTIONS, "video_started_recorded.json")
    watched = _Watched()
    try:
        await _watch(gemini, recorder, ref, watched, times or VideoTimes())
    except AppError as error:
        failed = refused_reply(recorder, _path(ref), "video_failed_recorded.json", error)
        deleted, removal = await _deleted(gemini, recorder, ref)
        findings = {**failed.findings, **_watch_findings(watched), **deleted}
        return CheckResult(findings, {**files, **_replies(watched), **failed.fixtures, **removal})
    deleted, removal = await _deleted(gemini, recorder, ref)
    files = {**files, **_replies(watched), **removal}
    findings = {
        "model": VIDEO_MODEL,
        "askedOutput": dict(REQUESTED_OUTPUT[VIDEO_KIND]),
        **_watch_findings(watched),
    }
    if watched.result is None:
        return CheckResult({**findings, **deleted, "timedOut": True}, files)
    clip, kept = _clip(watched.result)
    return CheckResult({**findings, **clip, **deleted}, {**files, **kept})


async def _watch(
    gemini: GeminiMediaWire, recorder: Recorder, ref: str, watched: _Watched, times: VideoTimes
) -> None:
    started = times.clock()
    while times.clock() - started < times.wait_seconds:
        poll = await gemini.poll_video(ref)
        watched.polls += 1
        watched.seconds = times.clock() - started
        if poll.done and poll.result is not None:
            watched.result = poll.result
            watched.done_reply = recorder.last(_path(ref), method="GET")
            return
        if watched.open_reply is None:
            watched.open_reply = recorder.last(_path(ref), method="GET")
        await times.sleep(times.poll_seconds)


async def _deleted(
    gemini: GeminiMediaWire, recorder: Recorder, ref: str
) -> tuple[dict[str, Any], dict[str, bytes]]:
    refused: str | None = None
    try:
        await gemini.forget(ref)
    except AppError as error:
        refused = str(error)[:300]
    reply = recorder.last(_path(ref), method="DELETE")
    found: dict[str, Any] = {
        "deleteStatus": None if reply is None else reply.status,
        "deleteContentType": None if reply is None else reply.content_type,
        "deleteBytes": None if reply is None else len(reply.body),
    }
    if refused is not None:
        found["deleteRefused"] = refused
    kept = {"video_deleted_recorded.json": reply.fixture()} if reply is not None and reply.body else {}
    return found, kept


def _clip(result: MediaResult) -> tuple[dict[str, Any], dict[str, bytes]]:
    found: dict[str, Any] = {
        "servedModel": result.served_model,
        "mime": result.mime,
        "bytes": len(result.data),
        "inputTokens": result.input_tokens,
        "outputTokens": result.output_tokens,
        "videoTokens": result.media_tokens,
    }
    try:
        facts = video_facts(result.data)
    except AppError as error:
        return {**found, "notAnMp4": str(error)[:300]}, {"gemini_video.bin": result.data}
    found.update(
        durationSeconds=facts.duration_seconds,
        width=facts.width,
        height=facts.height,
        silentAsAsked=not facts.has_audio,
        pipelineStores=_pipeline_problem(result) is None,
        pipelineProblem=_pipeline_problem(result),
    )
    return found, {"gemini_video.mp4": result.data}


def _pipeline_problem(result: MediaResult) -> str | None:
    try:
        checked_output(VIDEO_KIND, result)
    except AppError as error:
        return str(error)[:300]
    return None


def _watch_findings(watched: _Watched) -> dict[str, Any]:
    return {"polls": watched.polls, "secondsToFinish": round(watched.seconds, 1)}


def _replies(watched: _Watched) -> dict[str, bytes]:
    named = (
        ("video_polling_recorded.json", watched.open_reply),
        ("video_completed_recorded.json", watched.done_reply),
    )
    return {name: reply.fixture() for name, reply in named if reply is not None}


def _path(ref: str) -> str:
    return f"{INTERACTIONS}/{ref}"
