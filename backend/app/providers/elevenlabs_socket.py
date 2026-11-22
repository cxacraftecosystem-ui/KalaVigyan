from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import AbstractAsyncContextManager
from dataclasses import dataclass, field
from typing import Any, Protocol
from urllib.parse import urlsplit

import httpx
from websockets.asyncio.client import connect

from app.core.errors import ExternalFailure

from .elevenlabs import ELEVENLABS_API, KEY_HEADER, REQUEST_TIMEOUT
from .elevenlabs_shapes import ELEVENLABS_SERVICE

__all__ = [
    "SIGNED_URL_PATH",
    "SOCKET_HOST",
    "SocketTurn",
    "TurnSocket",
    "one_turn",
    "signed_conversation_url",
]

SIGNED_URL_PATH = "/v1/convai/conversation/get-signed-url"
SOCKET_HOST = "api.elevenlabs.io"
TURN_SECONDS = 90.0
QUIET_SECONDS = 20.0
STARTED = "conversation_initiation_metadata"
REPLY = "agent_response"
PING = "ping"
AUDIO = "audio"


class TurnSocket(Protocol):
    async def send(self, message: str) -> None: ...

    async def recv(self) -> str | bytes: ...


Opener = Callable[[str], AbstractAsyncContextManager[TurnSocket]]


@dataclass
class SocketTurn:
    conversation_id: str | None = None
    events: list[dict[str, Any]] = field(default_factory=list)
    replies: list[str] = field(default_factory=list)


async def signed_conversation_url(client: httpx.AsyncClient, *, api_key: str, agent_id: str) -> str:
    answer = await client.get(
        f"{ELEVENLABS_API}{SIGNED_URL_PATH}",
        params={"agent_id": agent_id},
        headers={KEY_HEADER: api_key},
        timeout=REQUEST_TIMEOUT,
    )
    url = answer.json().get("signed_url") if answer.is_success else None
    if not isinstance(url, str) or urlsplit(url).scheme != "wss" or urlsplit(url).hostname != SOCKET_HOST:
        raise ExternalFailure(
            f"ElevenLabs gave no signed conversation link ({answer.status_code})",
            kind="error",
            status=answer.status_code,
            service=ELEVENLABS_SERVICE,
        )
    return url


async def one_turn(
    url: str,
    question: str,
    *,
    bind: Callable[[str], Awaitable[None]],
    opener: Opener = connect,
    seconds: float = TURN_SECONDS,
) -> SocketTurn:
    turn = SocketTurn()
    async with opener(url) as socket:
        async for event in _events(socket, turn, seconds):
            if event.get("type") == STARTED and turn.conversation_id is None:
                turn.conversation_id = str(event[f"{STARTED}_event"]["conversation_id"])
                await bind(turn.conversation_id)
                await socket.send(json.dumps({"type": "user_message", "text": question}))
    return turn


async def _events(socket: TurnSocket, turn: SocketTurn, seconds: float) -> AsyncIterator[dict[str, Any]]:
    loop = asyncio.get_running_loop()
    deadline = loop.time() + seconds
    while (left := deadline - loop.time()) > 0:
        try:
            raw = await asyncio.wait_for(
                socket.recv(), timeout=min(left, QUIET_SECONDS) if turn.replies else left
            )
        except TimeoutError:
            return
        event = json.loads(raw)
        if event.get("type") == PING:
            await socket.send(json.dumps({"type": "pong", "event_id": event[f"{PING}_event"]["event_id"]}))
        if event.get("type") == REPLY:
            turn.replies.append(str(event[f"{REPLY}_event"]["agent_response"]))
        turn.events.append(_kept(event))
        yield event


def _kept(event: dict[str, Any]) -> dict[str, Any]:
    if event.get("type") != AUDIO:
        return event
    audio = event.get(f"{AUDIO}_event") or {}
    return {
        "type": AUDIO,
        f"{AUDIO}_event": {
            "event_id": audio.get("event_id"),
            "base64Length": len(audio.get("audio_base_64", "")),
        },
    }
