from __future__ import annotations

from dataclasses import asdict
from datetime import datetime
from typing import Any

import httpx

from app.core.config import get_settings
from app.core.db import session_scope, sessionmaker
from app.providers.elevenlabs import ElevenLabs
from app.services.object_store import media_bucket

from .artisan_store import SqlArtisanStore
from .artisan_upkeep import ArtisanUpkeep, run_artisan_upkeep
from .artisan_wiring import extraction_model
from .privacy import TranscriptCipher
from .runtime import voice_settings
from .store import SqlVoiceStore
from .upkeep import run_upkeep

__all__ = ["daily_voice_upkeep"]


async def daily_voice_upkeep(*, now: datetime) -> dict[str, Any]:
    async with session_scope() as session:
        voice = await voice_settings(session, get_settings())
    async with httpx.AsyncClient(follow_redirects=False) as client:
        elevenlabs = ElevenLabs(api_key=voice.api_key, client=client) if voice.api_key else None
        report = await run_upkeep(SqlVoiceStore(sessionmaker()), elevenlabs, now=now)
    artisans = await run_artisan_upkeep(_artisan_upkeep(voice.cipher), now=now)
    return {
        **asdict(report),
        "artisan": asdict(artisans),
        "reconciling": elevenlabs is not None,
        "ok": not [*report.failures, *artisans.failures],
    }


def _artisan_upkeep(cipher: TranscriptCipher | None) -> ArtisanUpkeep:
    return ArtisanUpkeep(
        artisans=SqlArtisanStore(sessionmaker()),
        sessions=sessionmaker(),
        objects=media_bucket(),
        cipher=cipher,
        model_for=extraction_model,
    )
