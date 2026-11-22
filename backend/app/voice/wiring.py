from __future__ import annotations

import logging
import uuid

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.errors import AppError
from app.providers.embedding import router_embedder
from app.providers.router import Principal
from app.providers.structured import router_structured_model
from app.research.crafts import QUESTION_MAX_CHARS, CraftQuery, CraftRef
from app.services.ai_providers import AiTask
from app.services.answer_store import build_answer_translation
from app.services.craft_resolver import CraftIndexStore, DatabaseCraftResolver

from .pack import VoicePack
from .records import VoiceStore
from .runtime import VoiceRuntime
from .turns import TurnTools

__all__ = ["turn_tools"]

logger = logging.getLogger(__name__)


def turn_tools(
    *,
    runtime: VoiceRuntime,
    store: VoiceStore,
    sessions: async_sessionmaker[AsyncSession],
    index: CraftIndexStore,
    user_id: uuid.UUID,
    role: str,
) -> TurnTools:
    principal = Principal(user_id=user_id, role=role)
    embed = router_embedder(principal)

    async def pack(craft: CraftRef, mode: str) -> VoicePack:
        return await runtime.packs.get(craft, mode, store.pack)

    async def resolve(question: str, language: str) -> CraftRef | None:
        query = CraftQuery(text=question[:QUESTION_MAX_CHARS], language=language)
        try:
            async with sessions() as session:
                resolution = await DatabaseCraftResolver(session, store=index, embed=embed).resolve(query)
        except AppError as error:
            logger.warning("voice craft resolution failed: %s", error)
            return None
        return resolution.craft if resolution.status == "RESOLVED" else None

    return TurnTools(
        pack=pack,
        resolve=resolve,
        compose=router_structured_model(AiTask.VOICE_TURN, principal),
        translation=build_answer_translation(
            sessions, model=router_structured_model(AiTask.TRANSLATE, principal)
        ),
        retriever=runtime.stored_search(user_id, role),
    )
