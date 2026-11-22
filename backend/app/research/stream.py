from __future__ import annotations

import asyncio
import contextlib
import json
from collections.abc import AsyncIterator, Awaitable, Callable, Mapping
from types import MappingProxyType
from typing import Any, Literal

from pydantic import BaseModel, Field, TypeAdapter, ValidationError

from app.core.errors import InvalidInput

from .base import ContractModel, absent
from .citations import AnswerSentence, Citation, SourceRef
from .explainer import EXPLAINER_EVENTS
from .explainer_versions import VERSION_EVENTS
from .vocabulary import ShownLevel

__all__ = [
    "HEARTBEAT_FRAME",
    "HEARTBEAT_SECONDS",
    "STATUS_STEPS",
    "STREAM_EVENTS",
    "DoneEvent",
    "Emit",
    "ErrorEvent",
    "FollowUpsEvent",
    "NotEnoughEvidenceEvent",
    "OpenQuestionEvent",
    "ReactionEvent",
    "ResearchProgress",
    "StatusEvent",
    "StatusStep",
    "event_frame",
    "event_stream",
    "parse_event",
    "sse_frame",
]

HEARTBEAT_SECONDS = 60
HEARTBEAT_FRAME = ": keep-alive\n\n"
STATUS_STEPS = (
    "PLANNING",
    "SEARCHING_STORED",
    "RESEARCHING",
    "READING",
    "COMPOSING",
    "WRITING_BACK",
    "TRANSLATING",
)

StatusStep = Literal[*STATUS_STEPS]
ResearchProgress = Callable[[StatusStep, int], Awaitable[None]]
Emit = Callable[[str, Any], Awaitable[None]]


class StatusEvent(ContractModel):
    step: StatusStep
    message: str = Field(min_length=1, max_length=300)


class OpenQuestionEvent(ContractModel):
    section_id: str = Field(min_length=1)
    heading: str | None = None
    sentence: AnswerSentence


class ReactionEvent(ContractModel):
    id: str = Field(min_length=1)
    label: str = Field(min_length=1)
    equation: str = Field(min_length=1)
    balanced: bool
    level: ShownLevel
    conditions: str | None
    citations: list[Citation] = Field(min_length=1)


class FollowUpsEvent(ContractModel):
    items: list[str]


class DoneEvent(ContractModel):
    answer_id: str | None
    quiz_available: bool | None = Field(default=None, exclude_if=absent)


class ErrorEvent(ContractModel):
    message: str = Field(min_length=1)


class NotEnoughEvidenceEvent(ContractModel):
    message: str = Field(min_length=1)


STREAM_EVENTS: Mapping[str, TypeAdapter[Any]] = MappingProxyType(
    {
        "status": TypeAdapter(StatusEvent),
        "source": TypeAdapter(SourceRef),
        "open_question": TypeAdapter(OpenQuestionEvent),
        "reaction": TypeAdapter(ReactionEvent),
        "follow_ups": TypeAdapter(FollowUpsEvent),
        "not_enough_evidence": TypeAdapter(NotEnoughEvidenceEvent),
        "done": TypeAdapter(DoneEvent),
        "error": TypeAdapter(ErrorEvent),
        **EXPLAINER_EVENTS,
        **VERSION_EVENTS,
    }
)


def parse_event(name: str, data: Any) -> BaseModel:
    adapter = STREAM_EVENTS.get(name)
    if adapter is None:
        raise InvalidInput(f"Unknown answer stream event {name!r}")
    if isinstance(data, BaseModel):
        data = data.model_dump(mode="json", by_alias=True, exclude_unset=True)
    try:
        return adapter.validate_python(data)
    except ValidationError as exc:
        raise InvalidInput(f"The {name} event breaks the stream contract: {exc}") from exc


def event_frame(name: str, data: Any) -> str:
    payload = parse_event(name, data)
    return sse_frame(name, payload.model_dump(mode="json", by_alias=True, exclude_unset=True))


def sse_frame(event: str, data: Any) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False, separators=(',', ':'))}\n\n"


async def event_stream(
    produce: Callable[[Emit], Awaitable[None]], *, heartbeat_seconds: float = HEARTBEAT_SECONDS
) -> AsyncIterator[str]:
    queue: asyncio.Queue[str | None] = asyncio.Queue()

    async def emit(name: str, data: Any) -> None:
        await queue.put(event_frame(name, data))

    async def run() -> None:
        try:
            await produce(emit)
        finally:
            await queue.put(None)

    task = asyncio.create_task(run())
    try:
        while True:
            try:
                frame = await asyncio.wait_for(queue.get(), heartbeat_seconds)
            except TimeoutError:
                yield HEARTBEAT_FRAME
                continue
            if frame is None:
                break
            yield frame
        await task
    finally:
        if not task.done():
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task
