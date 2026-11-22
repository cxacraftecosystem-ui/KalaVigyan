from __future__ import annotations

import asyncio
import logging
import uuid
from collections.abc import Awaitable, Callable, Mapping, Sequence
from dataclasses import dataclass, replace
from datetime import datetime
from typing import Any

from pydantic import TypeAdapter
from sqlalchemy.exc import SQLAlchemyError

from app.composer.candidates import stored_claim_candidate
from app.core.errors import AppError
from app.research.composition import ComposeRequest, ResearchSummary
from app.research.crafts import QUESTION_MAX_CHARS, CraftRef
from app.research.retrieval import KnowledgeHits, KnowledgeQuery, KnowledgeRetriever
from app.research.structured import StructuredModel
from app.research.vocabulary import CANONICAL_LANGUAGE
from app.schemas.voice import VoiceTurnView
from app.services.answer_events import composed_answer_events
from app.services.answer_translation import AnswerTranslation, english_question, translated_sentences
from app.services.knowledge_view import ClaimView
from app.services.write_back_plan import composed_sentences

from .actions import turn_actions
from .compose import voice_composed
from .pack import PACK_CANDIDATES, VoicePack, ranked_claims, searched_claims
from .phrases import NO_CRAFT_REPLIES, NO_EVIDENCE_REPLIES, UNSAID_REPLIES, phrase
from .records import AnswerRecord, SessionRecord
from .spoken import SpokenReply, spoken_reply

__all__ = ["SpokenTurn", "TurnAsk", "TurnTools", "cited_sources", "spoken_turn"]

logger = logging.getLogger(__name__)

TURN_VIEW = TypeAdapter(VoiceTurnView)
MIN_QUESTION_CHARS = 2


@dataclass(frozen=True)
class TurnAsk:
    session: SessionRecord
    question: str
    ordinal: int
    turn_id: uuid.UUID
    answer_id: uuid.UUID
    seconds_left: float

    @classmethod
    def begun(
        cls, session: SessionRecord, question: str, *, turn_id: uuid.UUID, answer_id: uuid.UUID, now: datetime
    ) -> TurnAsk:
        left = max(0.0, (session.hard_end - now).total_seconds())
        return cls(session, question, session.turn_count, turn_id, answer_id, left)


@dataclass(frozen=True)
class TurnTools:
    pack: Callable[[CraftRef, str], Awaitable[VoicePack]]
    resolve: Callable[[str, str], Awaitable[CraftRef | None]]
    compose: StructuredModel
    translation: AnswerTranslation
    retriever: KnowledgeRetriever | None = None


@dataclass(frozen=True)
class SpokenTurn:
    turn_id: uuid.UUID
    ordinal: int
    heard: str
    craft: CraftRef | None
    answer_id: uuid.UUID | None
    sentences: tuple[dict[str, Any], ...]
    sources: tuple[dict[str, Any], ...]
    parts: tuple[str, ...]
    actions: tuple[dict[str, Any], ...]

    @property
    def spoken(self) -> str:
        return "".join(self.parts)

    @property
    def claim_ids(self) -> tuple[uuid.UUID, ...]:
        found = (c["claimId"] for s in self.sentences for c in s["citations"])
        return tuple(uuid.UUID(claim) for claim in dict.fromkeys(found))

    def view(self) -> dict[str, Any]:
        payload = {
            "turnId": str(self.turn_id),
            "ordinal": self.ordinal,
            "heard": self.heard,
            "answerId": str(self.answer_id) if self.answer_id else None,
            "sentences": list(self.sentences),
            "spoken": self.spoken,
            "actions": list(self.actions),
        }
        return TURN_VIEW.dump_python(TURN_VIEW.validate_python(payload), mode="json", by_alias=True)

    def renumbered(self, ordinal: int) -> SpokenTurn:
        sentences = tuple({**s, "id": f"t{ordinal}.{n}"} for n, s in enumerate(self.sentences, start=1))
        return replace(self, ordinal=ordinal, sentences=sentences)

    def answer(self, latency_ms: int) -> AnswerRecord | None:
        if self.answer_id is None:
            return None
        return AnswerRecord(
            id=self.answer_id,
            craft_slug=self.craft.slug if self.craft else None,
            claim_ids=self.claim_ids,
            sentences=self.sentences,
            latency_ms=latency_ms,
        )


async def spoken_turn(ask: TurnAsk, tools: TurnTools) -> SpokenTurn:
    deadline = asyncio.get_running_loop().time() + ask.seconds_left
    language = ask.session.language
    craft = ask.session.craft or await tools.resolve(ask.question, language)
    if craft is None:
        return _unanswered(ask, None, phrase(NO_CRAFT_REPLIES, language))
    pack = await tools.pack(craft, ask.session.mode)
    sentences = await _sentences(ask, pack, tools, deadline)
    reply = await _said(ask, pack, sentences, tools.translation, deadline)
    if reply is None:
        return _unanswered(ask, craft, phrase(UNSAID_REPLIES, language))
    if not reply.sentences:
        return _unanswered(ask, craft, phrase(NO_EVIDENCE_REPLIES, language, craft=craft.name))
    cited = _cited_views(reply.sentences, pack)
    actions = turn_actions(
        answer_id=ask.answer_id,
        session_craft=ask.session.craft,
        turn_craft=craft,
        cited=cited,
        stage_of=pack.stage_of,
    )
    return SpokenTurn(
        turn_id=ask.turn_id,
        ordinal=ask.ordinal,
        heard=ask.question,
        craft=craft,
        answer_id=ask.answer_id,
        sentences=reply.sentences,
        sources=cited_sources(reply.sentences, pack.cited.sources),
        parts=reply.parts,
        actions=actions,
    ).renumbered(ask.ordinal)


def cited_sources(
    sentences: Sequence[dict[str, Any]], sources: Mapping[str, dict[str, Any]]
) -> tuple[dict[str, Any], ...]:
    ordered = dict.fromkeys(c["sourceId"] for s in sentences for c in s["citations"])
    return tuple(sources[source_id] for source_id in ordered)


async def _sentences(
    ask: TurnAsk, pack: VoicePack, tools: TurnTools, deadline: float
) -> list[dict[str, Any]]:
    if len(ask.question) < MIN_QUESTION_CHARS:
        return []
    english = await _ranking_question(ask, tools.translation, deadline)
    found = await _stored_search(ask, pack, english, tools.retriever, deadline)
    ranked = searched_claims(pack, found, ranked_claims(pack, english))
    if not ranked:
        return []
    if ask.session.mode == "VERIFIED":
        return [view.payload() for view in ranked]
    request = _compose_request(ask, pack, ranked)
    composed = await voice_composed(tools.compose, request)
    if composed.not_enough_evidence is not None:
        return []
    claims_of = [tuple(sentence.claim_ids) for sentence, _ in composed_sentences(composed)]
    events = composed_answer_events(composed, claims_of, pack.cited)
    return [payload["sentence"] for name, payload in events if name == "sentence"]


async def _ranking_question(ask: TurnAsk, translation: AnswerTranslation, deadline: float) -> str:
    try:
        async with asyncio.timeout_at(deadline):
            return await english_question(ask.question, translation)
    except TimeoutError:
        logger.warning(
            "voice turn %s: the question was not rendered in English before the call ends", ask.turn_id
        )
        return ask.question


async def _stored_search(
    ask: TurnAsk, pack: VoicePack, english: str, retriever: KnowledgeRetriever | None, deadline: float
) -> KnowledgeHits | None:
    if retriever is None:
        return None
    query = KnowledgeQuery(
        craft_slug=pack.craft.slug,
        text=english[:QUESTION_MAX_CHARS],
        mode=ask.session.mode,
        passages=False,
        limit=PACK_CANDIDATES,
    )
    try:
        async with asyncio.timeout_at(deadline):
            return await retriever.search(query)
    except (AppError, SQLAlchemyError, TimeoutError) as error:
        logger.warning("voice turn %s ranks the pack by its words alone: %s", ask.turn_id, error)
        return None


async def _said(
    ask: TurnAsk,
    pack: VoicePack,
    sentences: Sequence[dict[str, Any]],
    translation: AnswerTranslation,
    deadline: float,
) -> SpokenReply | None:
    language = ask.session.language
    english = spoken_reply(sentences, pack.cited.sources, language=CANONICAL_LANGUAGE)
    if language == CANONICAL_LANGUAGE or not english.sentences:
        return english
    claim_texts = {view.id: view.text for view in pack.cited.views.values()}
    try:
        async with asyncio.timeout_at(deadline):
            rendered = await translated_sentences(
                english.sentences, language=language, translation=translation, claim_texts=claim_texts
            )
    except TimeoutError:
        logger.warning("voice turn %s: the reply was not translated before the call ends", ask.turn_id)
        return None
    said = [sentence for sentence in rendered if sentence.get("translated")]
    if not said:
        return None
    return spoken_reply(said, pack.cited.sources, language=language)


def _compose_request(ask: TurnAsk, pack: VoicePack, ranked: Sequence[ClaimView]) -> ComposeRequest:
    summary = ResearchSummary(
        craft=pack.craft,
        mode=ask.session.mode,
        stored_claims=len(pack.cited.views),
        stored_passages=0,
        evidence_found=0,
        documents_read=0,
        failures=0,
    )
    return ComposeRequest(
        question=ask.question[:QUESTION_MAX_CHARS],
        craft=pack.craft,
        candidates=[stored_claim_candidate(view.id, view.text, view.level) for view in ranked],
        searched=summary,
    )


def _cited_views(sentences: Sequence[dict[str, Any]], pack: VoicePack) -> list[ClaimView]:
    claim_ids = dict.fromkeys(uuid.UUID(c["claimId"]) for s in sentences for c in s["citations"])
    return [pack.cited.views[claim_id] for claim_id in claim_ids if claim_id in pack.cited.views]


def _unanswered(ask: TurnAsk, craft: CraftRef | None, reply: str) -> SpokenTurn:
    return SpokenTurn(
        turn_id=ask.turn_id,
        ordinal=ask.ordinal,
        heard=ask.question,
        craft=craft,
        answer_id=None,
        sentences=(),
        sources=(),
        parts=(reply,),
        actions=(),
    )
