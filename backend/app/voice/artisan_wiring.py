from __future__ import annotations

import asyncio
import logging
import uuid
from collections.abc import Callable
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.shielded import ShieldedWork
from app.providers.catalogue import AiTask
from app.providers.router import Principal
from app.providers.structured import router_structured_model
from app.research.structured import StructuredModel
from app.services.craft_resolver import CraftIndexStore

from .artisan_extract import extract_contributions
from .artisan_records import ArtisanStore, ConversationRecord
from .artisan_reply import ArtisanTools
from .privacy import TranscriptCipher
from .records import VoiceStore
from .runtime import VoiceRuntime
from .wiring import turn_tools

__all__ = ["artisan_tools", "extraction_model", "run_extraction", "schedule_extraction"]

logger = logging.getLogger(__name__)

RUNNABLE_EXTRACTION = ("PENDING", "WAITING", "FAILED")


def artisan_tools(
    *,
    runtime: VoiceRuntime,
    store: VoiceStore,
    sessions: async_sessionmaker[AsyncSession],
    index: CraftIndexStore,
    user_id: uuid.UUID,
    role: str,
) -> ArtisanTools:
    principal = Principal(user_id=user_id, role=role)
    turns = turn_tools(
        runtime=runtime, store=store, sessions=sessions, index=index, user_id=user_id, role=role
    )
    return ArtisanTools(interview=router_structured_model(AiTask.INTERVIEW, principal), turns=turns)


def extraction_model(user_id: uuid.UUID, role: str) -> StructuredModel:
    return router_structured_model(AiTask.TESTIMONY, Principal(user_id=user_id, role=role))


async def run_extraction(
    conversation_id: uuid.UUID, *, artisans: ArtisanStore, cipher: TranscriptCipher, model: StructuredModel
) -> str | None:
    record = await artisans.by_id(conversation_id)
    if record is None:
        return None
    terms = await artisans.held_back(record.user_id)
    return await extract_contributions(
        conversation_id, artisans=artisans, model=model, cipher=cipher, terms=terms, now=datetime.now(UTC)
    )


def schedule_extraction(
    shield: ShieldedWork, *, artisans: ArtisanStore, cipher: TranscriptCipher, role: str
) -> Callable[[ConversationRecord], None]:
    def scheduled(conversation: ConversationRecord) -> None:
        if conversation.extraction not in RUNNABLE_EXTRACTION:
            return
        model = extraction_model(conversation.user_id, role)
        work = run_extraction(conversation.id, artisans=artisans, cipher=cipher, model=model)
        task = asyncio.ensure_future(shield.run(work, name=f"artisan extraction {conversation.id}"))
        task.add_done_callback(_reported)

    return scheduled


def _reported(task: asyncio.Future[str | None]) -> None:
    if task.cancelled():
        return
    error = task.exception()
    if error is not None:
        logger.error("an artisan extraction failed; the daily upkeep retries it", exc_info=error)
