from __future__ import annotations

import httpx

from app.core.key_checks import KeyVerdict, checked_get

from .elevenlabs import ELEVENLABS_API, KEY_HEADER

__all__ = ["check_key"]


async def check_key(client: httpx.AsyncClient, value: str) -> KeyVerdict:
    return await checked_get(client, f"{ELEVENLABS_API}/v1/user", headers={KEY_HEADER: value})
