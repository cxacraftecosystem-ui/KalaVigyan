from __future__ import annotations

import asyncio
import logging
import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

from sqlalchemy.exc import SQLAlchemyError

from app.composer.candidates import offered_passages
from app.core.errors import AppError
from app.research.composition import ComposedAnswer, ComposeRequest
from app.research.crafts import QUESTION_MAX_CHARS, CraftRef
from app.research.evidence_pack import EvidencePack
from app.research.planning import Facet, FacetCoverage, RetrievalPlan
from app.research.retrieval import ChunkHit, KnowledgeHits, KnowledgeQuery, chunk_acls_for
from app.research.vocabulary import CANONICAL_LANGUAGE
from app.research.write_back import FoundBy
from app.services.answer_events import CitedClaims, joined_claims
from app.services.knowledge_view import ClaimView
from app.services.write_back_plan import composed_sentences

from .pack import PACK_CANDIDATES, PACK_PASSAGES

__all__ = [
    "PASSAGE_MODES",
    "TURN_TIERS",
    "VOICE_FOUND_BY",
    "PassageTurn",
    "TurnPassages",
    "WrittenTurn",
    "cites_evidence",
    "offered_request",
    "passage_turn",
    "stored_query",
    "turn_pack",
    "written_turn",
]

logger = logging.getLogger(__name__)

PASSAGE_MODES = ("HYBRID",)
TURN_TIERS = ("T1", "T2")
TURN_INTENT = "OTHER"
VOICE_FOUND_BY: FoundBy = "VOICE"


@dataclass(frozen=True)
class PassageTurn:
    craft: CraftRef
    mode: str
    concept_id: uuid.UUID
    passages: tuple[ChunkHit, ...]


@dataclass(frozen=True)
class WrittenTurn:
    claims_of: tuple[tuple[uuid.UUID, ...], ...]
    cited: CitedClaims


class TurnPassages(Protocol):
    async def screened(self, request: ComposeRequest) -> ComposeRequest: ...

    async def written(self, turn: PassageTurn, composed: ComposedAnswer) -> WrittenTurn: ...


def stored_query(craft: CraftRef, english: str, *, mode: str, role: str) -> KnowledgeQuery:
    return KnowledgeQuery(
        craft_slug=craft.slug,
        text=english[:QUESTION_MAX_CHARS],
        mode=mode,
        passages=mode in PASSAGE_MODES,
        chunk_acls=chunk_acls_for(role),
        limit=PACK_CANDIDATES,
    )


def passage_turn(
    craft: CraftRef, mode: str, found: KnowledgeHits | None, ranked: Sequence[ClaimView]
) -> PassageTurn | None:
    if mode not in PASSAGE_MODES or found is None:
        return None
    passages = tuple(offered_passages(found.chunks)[:PACK_PASSAGES])
    concept = next((view.concept_id for view in ranked if view.concept_id is not None), None)
    if not passages or concept is None:
        return None
    return PassageTurn(craft=craft, mode=mode, concept_id=concept, passages=passages)


def turn_pack(turn: PassageTurn, facet: Facet) -> EvidencePack:
    plan = RetrievalPlan(
        mode=turn.mode,
        craft=turn.craft,
        intent=TURN_INTENT,
        language=CANONICAL_LANGUAGE,
        needs_region=False,
        facets=[facet],
        tiers=list(TURN_TIERS),
        max_fetches=0,
    )
    return EvidencePack(
        plan=plan,
        degraded=False,
        stored=KnowledgeHits(craft_slug=turn.craft.slug, chunks=turn.passages),
        coverage=(FacetCoverage(facet_index=0),),
    )


async def offered_request(
    passages: TurnPassages | None, request: ComposeRequest, *, deadline: float, turn_id: uuid.UUID
) -> ComposeRequest:
    if passages is None or all(candidate.kind == "CLAIM" for candidate in request.candidates):
        return request
    try:
        async with asyncio.timeout_at(deadline):
            return await passages.screened(request)
    except (AppError, SQLAlchemyError, TimeoutError) as error:
        logger.warning("voice turn %s offers no passage, as none could be screened: %s", turn_id, error)
        claims = [candidate for candidate in request.candidates if candidate.kind == "CLAIM"]
        return request.model_copy(update={"candidates": claims})


async def written_turn(
    passages: TurnPassages | None,
    turn: PassageTurn | None,
    composed: ComposedAnswer,
    *,
    cited: CitedClaims,
    deadline: float,
    turn_id: uuid.UUID,
) -> WrittenTurn:
    stored = WrittenTurn(
        claims_of=tuple(tuple(sentence.claim_ids) for sentence, _ in composed_sentences(composed)),
        cited=cited,
    )
    if passages is None or turn is None or not cites_evidence(composed):
        return stored
    try:
        async with asyncio.timeout_at(deadline):
            written = await passages.written(turn, composed)
    except (AppError, SQLAlchemyError, TimeoutError) as error:
        logger.warning(
            "voice turn %s speaks stored claims only, as no passage was written back: %s", turn_id, error
        )
        return stored
    return WrittenTurn(claims_of=written.claims_of, cited=joined_claims(cited, written.cited))


def cites_evidence(composed: ComposedAnswer) -> bool:
    return any(sentence.evidence_ids for sentence, _ in composed_sentences(composed))
