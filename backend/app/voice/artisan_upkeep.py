from __future__ import annotations

import logging
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.errors import AppError
from app.research.structured import StructuredModel
from app.services.conversation_retention import AudioObjects, purge_due
from app.services.testimony_withdrawal import clear_expired_rejections

from .artisan_extract import EXTRACTION_ATTEMPTS_MAX
from .artisan_records import ArtisanStore
from .artisan_transcript import artisan_turns, open_transcript
from .artisan_wiring import run_extraction
from .privacy import TranscriptCipher

__all__ = ["ARTISAN_UPKEEP_LIMIT", "ArtisanUpkeep", "ArtisanUpkeepReport", "run_artisan_upkeep"]

logger = logging.getLogger(__name__)

ARTISAN_UPKEEP_LIMIT = 200


@dataclass
class ArtisanUpkeepReport:
    closed: int = 0
    extracted: int = 0
    purged: int = 0
    cleared: int = 0
    failures: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class ArtisanUpkeep:
    artisans: ArtisanStore
    sessions: async_sessionmaker[AsyncSession]
    objects: AudioObjects | None
    cipher: TranscriptCipher | None
    model_for: Callable[[uuid.UUID, str], StructuredModel]


async def run_artisan_upkeep(upkeep: ArtisanUpkeep, *, now: datetime) -> ArtisanUpkeepReport:
    report = ArtisanUpkeepReport()
    if upkeep.cipher is not None:
        await _closed(upkeep, upkeep.cipher, report, now)
        await _extracted(upkeep, upkeep.cipher, report)
    async with upkeep.sessions() as session:
        if upkeep.objects is not None:
            report.purged = await purge_due(session, upkeep.objects, now=now)
        report.cleared = await clear_expired_rejections(session, now=now)
        await session.commit()
    return report


async def _closed(
    upkeep: ArtisanUpkeep, cipher: TranscriptCipher, report: ArtisanUpkeepReport, now: datetime
) -> None:
    for conversation_id in await upkeep.artisans.unfinished(now, ARTISAN_UPKEEP_LIMIT):
        record = await upkeep.artisans.by_id(conversation_id)
        if record is None:
            continue
        try:
            spoke = bool(artisan_turns(open_transcript(cipher, record.transcript)))
        except AppError as error:
            report.failures.append(f"{conversation_id}: {error}")
            continue
        await upkeep.artisans.finish(conversation_id, now, spoke=spoke)
        report.closed += 1


async def _extracted(upkeep: ArtisanUpkeep, cipher: TranscriptCipher, report: ArtisanUpkeepReport) -> None:
    due = await upkeep.artisans.due_extractions(ARTISAN_UPKEEP_LIMIT, max_attempts=EXTRACTION_ATTEMPTS_MAX)
    for conversation_id in due:
        record = await upkeep.artisans.by_id(conversation_id)
        if record is None:
            continue
        model = upkeep.model_for(record.user_id, record.role)
        try:
            status = await run_extraction(
                conversation_id, artisans=upkeep.artisans, cipher=cipher, model=model
            )
        except AppError as error:
            report.failures.append(f"{conversation_id}: {error}")
            continue
        if status in ("DONE", "NONE"):
            report.extracted += 1
        elif status is not None:
            report.failures.append(f"{conversation_id}: extraction {status}")
