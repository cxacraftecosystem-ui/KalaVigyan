from __future__ import annotations

import uuid
from collections.abc import Sequence

from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.errors import InvalidInput
from app.models import Concept
from app.research.composition import ComposedAnswer, ComposeRequest
from app.research.embedding import TextEmbedder
from app.research.planning import Facet
from app.services import knowledge_view
from app.services.answer_events import cited_claims
from app.services.craft_resolver import CraftIndexStore
from app.services.off_question import screened_request
from app.services.research_write_back import sentence_claim_ids, store_live_research
from app.services.write_back_names import filing_names

from .passages import VOICE_FOUND_BY, PassageTurn, WrittenTurn, turn_pack

__all__ = ["SqlTurnPassages", "concept_facet"]


class SqlTurnPassages:
    def __init__(
        self,
        sessions: async_sessionmaker[AsyncSession],
        *,
        index: CraftIndexStore,
        embed: TextEmbedder,
        acls: Sequence[str],
    ) -> None:
        self._sessions = sessions
        self._index = index
        self._embed = embed
        self._acls = tuple(acls)

    async def screened(self, request: ComposeRequest) -> ComposeRequest:
        async with self._sessions() as session:
            names = await filing_names(session, self._index, request.craft, ())
        return screened_request(request, names, comparison=False)

    async def written(self, turn: PassageTurn, composed: ComposedAnswer) -> WrittenTurn:
        async with self._sessions() as session:
            facet = await concept_facet(session, turn.concept_id)
            stored = await store_live_research(
                session,
                turn_pack(turn, facet),
                composed,
                embed=self._embed,
                found_by=VOICE_FOUND_BY,
                index=self._index,
            )
            written = [result.claim_id for result in stored.results]
            views, sources = await knowledge_view.claims_by_id(session, written, acls=self._acls)
        return WrittenTurn(
            claims_of=sentence_claim_ids(composed, stored), cited=cited_claims(list(views.values()), sources)
        )


async def concept_facet(session: AsyncSession, concept_id: uuid.UUID) -> Facet:
    concept = await session.get(Concept, concept_id)
    if concept is None:
        raise InvalidInput(f"No concept has the id {concept_id}")
    try:
        return Facet(type=concept.type, target=concept.name)
    except ValidationError as error:
        raise InvalidInput(f"The concept {concept_id} cannot name a voice turn's facts: {error}") from error
