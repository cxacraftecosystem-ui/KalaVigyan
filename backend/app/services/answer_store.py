from __future__ import annotations

import uuid
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, literal, update
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.composer.composer import ModelComposer
from app.composer.translation import ModelTranslator
from app.composer.translation_meaning import ReadBackTranslator
from app.core.errors import InvalidInput
from app.core.logging import current_request_id
from app.core.shielded import ShieldedWork
from app.models import Answer
from app.planner.orchestrator import ResearchPlanner
from app.planner.reading import ReadCache
from app.planner.understanding import ModelUnderstander
from app.research.answer_models import AnswerModels
from app.research.blocks import ImagesBlock
from app.research.composition import ComposedAnswer
from app.research.crafts import CraftQuery, CraftRef, CraftResolution
from app.research.depth import depth_policy
from app.research.embedding import TextEmbedder
from app.research.evidence_pack import EvidencePack, ResearchTrail
from app.research.explainer import Explainer
from app.research.explainer_versions import ExplainerVersionDocument, VersionMark
from app.research.judge_ladder import JudgeLadder
from app.research.planning import PlanRequest
from app.research.retrieval import EVERY_CHUNK_ACLS
from app.research.sections import AnswerPlans
from app.research.stream import ResearchProgress
from app.research.structured import StructuredModel
from app.research.term_marking import GlossaryEntry
from app.research.understanding import Understanding
from app.retrieval.answer_embeddings import AnswerEmbeddings
from app.retrieval.hybrid import SessionScopedSearch
from app.retrieval.stamps import stamp_reader
from app.science.records import ProcessRecords

from . import knowledge_view
from .answer_catalogue import catalogue_lookup
from .answer_cost import answer_measures
from .answer_events import CitedClaims, cited_claims
from .answer_gaps import FieldReading, record_verdict
from .answer_lede import LedeTools
from .answer_rows import write_answer_rows
from .answer_steps import TracedStep
from .answer_translation import AnswerTranslation, english_question
from .answering import AnswerAsk, AnswerPipeline, NameLookup
from .block_builders import BlockBuilders
from .builder_interface import BuilderTools
from .builder_record import answer_build_record
from .citation_contexts import with_contexts
from .coverage import held_field_lookup
from .craft_process import process_records
from .craft_resolver import CraftIndexStore, DatabaseCraftResolver
from .explainer_history import StaleVersion, UnknownExplainer, latest_stored
from .explainer_payload import EXPLAINER_PAYLOAD_KEY, FIRST_VERSION, stored_payload
from .live_sources import LiveSourcesStore
from .piece_store import SqlPieceStore
from .research_write_back import sentence_claim_ids, store_live_research, writes_back
from .section_context import ClaimsOf
from .section_enrichment import EnrichmentTools
from .section_images import SectionImagesAsk, section_images
from .signature_blocks import signature_figures
from .term_glossary import glossary_entries
from .translation_cache import SqlTranslationCache
from .write_back_names import CraftNames, filing_names

__all__ = [
    "EXPLAINER_PAYLOAD_KEY",
    "READING_STYLE_KEY",
    "SqlAnswerStore",
    "answer_names",
    "answer_understander",
    "build_answer_enrichment",
    "build_answer_pipeline",
    "build_answer_translation",
]

READING_STYLE_KEY = "readingStyle"


class SqlAnswerStore:
    def __init__(
        self,
        sessions: async_sessionmaker[AsyncSession],
        *,
        embed: TextEmbedder,
        shield: ShieldedWork,
        index: CraftIndexStore,
        judge: JudgeLadder | None = None,
    ) -> None:
        self._sessions = sessions
        self._embed = embed
        self._shield = shield
        self._index = index
        self._judge = judge

    async def stored_claims(self, craft_slug: str, question: str, mode: str) -> CitedClaims:
        async with self._sessions() as session:
            craft = await knowledge_view.resolve_craft(session, craft_slug)
            if craft is None:
                raise InvalidInput(f"No craft has the slug {craft_slug!r}")
            views, sources = await knowledge_view.claims_for(
                session, craft, mode=mode, question=question, acls=EVERY_CHUNK_ACLS
            )
            return await with_contexts(session, cited_claims(views, sources))

    async def begin(self, ask: AnswerAsk, understanding: Understanding) -> uuid.UUID:
        return await self._shield.run(self._begun(ask, understanding), name="answer record")

    async def keep(self, answer_id: uuid.UUID, pack: EvidencePack, composed: ComposedAnswer) -> ClaimsOf:
        return await self._shield.run(self._kept(answer_id, pack, composed), name="answer write-back")

    async def finish(
        self,
        answer_id: uuid.UUID,
        *,
        asked_at: datetime,
        plans: AnswerPlans,
        claim_ids: Sequence[uuid.UUID],
        explainer: Explainer | None,
        version: VersionMark | None = None,
        readings: Sequence[FieldReading] = (),
        steps: Sequence[TracedStep] = (),
    ) -> None:
        stored = _StoredExplainer(explainer, version) if explainer is not None else None
        kept = _Kept(plans, claim_ids, readings, steps)
        await self._shield.run(
            self._finished(answer_id, kept, stored, asked_at=asked_at), name="answer record"
        )

    async def stop(self, request_id: str) -> None:
        await self._shield.run(self._stopped(request_id), name="answer record")

    async def process(self, craft_slug: str) -> ProcessRecords | None:
        async with self._sessions() as session:
            craft = await knowledge_view.resolve_craft(session, craft_slug)
            return await process_records(session, craft, acls=EVERY_CHUNK_ACLS) if craft is not None else None

    async def latest(self, explainer_id: uuid.UUID, user_id: uuid.UUID | None) -> ExplainerVersionDocument:
        if user_id is None:
            raise UnknownExplainer(explainer_id)
        async with self._sessions() as session:
            return await latest_stored(session, explainer_id, user_id)

    async def _begun(self, ask: AnswerAsk, understanding: Understanding) -> uuid.UUID:
        answer_id = uuid.uuid4()
        async with self._sessions() as session:
            craft = understanding.craft
            row = await knowledge_view.resolve_craft(session, craft.slug) if craft else None
            session.add(
                Answer(
                    id=answer_id,
                    userId=ask.user_id,
                    question=ask.question,
                    language=understanding.language,
                    mode=depth_policy(understanding.depth).mode,
                    craftId=row.id if row else None,
                    understanding=understanding.model_dump(mode="json", by_alias=True),
                    plan={READING_STYLE_KEY: ask.reading_style},
                    requestId=current_request_id(),
                )
            )
            await session.commit()
        return answer_id

    async def _kept(self, answer_id: uuid.UUID, pack: EvidencePack, composed: ComposedAnswer) -> ClaimsOf:
        async with self._sessions() as session:
            stored = None
            if writes_back(pack):
                stored = await store_live_research(
                    session,
                    pack,
                    composed,
                    embed=self._embed,
                    found_by="ANSWER",
                    index=self._index,
                    answer_id=answer_id,
                    judge=self._judge,
                )
            await session.commit()
        return sentence_claim_ids(composed, stored)

    async def _finished(
        self, answer_id: uuid.UUID, kept: _Kept, stored: _StoredExplainer | None, *, asked_at: datetime
    ) -> None:
        values = kept.values()
        if stored is not None:
            values |= stored.values(answer_id)
        try:
            async with self._sessions() as session:
                values |= await answer_measures(session, asked_at=asked_at, finished_at=datetime.now(UTC))
                await session.execute(update(Answer).where(Answer.id == answer_id).values(**values))
                await record_verdict(session, answer_id, kept.readings)
                await write_answer_rows(session, answer_id, stored.explainer if stored else None, kept.steps)
                await session.commit()
        except IntegrityError as error:
            if stored is None or stored.version is None:
                raise
            mark = stored.version
            raise StaleVersion(mark.explainer_id, mark.version - 1, mark.version) from error

    async def _stopped(self, request_id: str) -> None:
        async with self._sessions() as session:
            await session.execute(
                update(Answer)
                .where(Answer.requestId == request_id, Answer.latencyMs.is_(None), Answer.stoppedAt.is_(None))
                .values(stoppedAt=datetime.now(UTC))
            )
            await session.commit()

    async def cited(self, claim_ids: Iterable[uuid.UUID]) -> CitedClaims:
        async with self._sessions() as session:
            views, sources = await knowledge_view.claims_by_id(session, claim_ids, acls=EVERY_CHUNK_ACLS)
            return await with_contexts(session, cited_claims(list(views.values()), sources))


@dataclass(frozen=True)
class _Kept:
    plans: AnswerPlans
    claim_ids: Sequence[uuid.UUID]
    readings: Sequence[FieldReading]
    steps: Sequence[TracedStep]

    def values(self) -> dict[str, Any]:
        plans = self.plans
        tiers = dict.fromkeys(tier for section in plans.sections for tier in section.plan.tiers)
        values: dict[str, Any] = {
            "plan": func.coalesce(Answer.plan, literal({}, JSONB)).op("||")(
                literal(plans.model_dump(mode="json", by_alias=True), JSONB)
            ),
            "claimIds": list(self.claim_ids),
            "tiersUsed": list(tiers),
            "stoppedAt": None,
        }
        if plans.sections:
            values["mode"] = plans.sections[0].plan.mode
        return values


@dataclass(frozen=True)
class _StoredExplainer:
    explainer: Explainer
    version: VersionMark | None

    def values(self, answer_id: uuid.UUID) -> dict[str, Any]:
        mark = self.version
        return {
            "payload": stored_payload(self.explainer, mark),
            "explainerId": mark.explainer_id if mark is not None else answer_id,
            "explainerVersion": mark.version if mark is not None else FIRST_VERSION,
        }


def build_answer_pipeline(
    *,
    sessions: async_sessionmaker[AsyncSession],
    index: CraftIndexStore,
    live: LiveSourcesStore,
    models: AnswerModels,
    embed: TextEmbedder,
    shield: ShieldedWork,
) -> AnswerPipeline:
    embed = AnswerEmbeddings(embed, stamp=stamp_reader(sessions))
    translation = build_answer_translation(sessions, model=models.translate)
    retriever = SessionScopedSearch(
        sessions, embed=embed, english=lambda text: english_question(text, translation), rerank=models.rerank
    )

    async def research(
        request: PlanRequest, progress: ResearchProgress, trail: ResearchTrail, reads: ReadCache | None = None
    ) -> EvidencePack:
        planner = ResearchPlanner(model=models.plan, retriever=retriever, sources=await live.get(sessions))
        return await planner.research(request, progress=progress, trail=trail, reads=reads)

    tools = BuilderTools(
        sessions, live, models.builder_plan, models.builder_compose, models.explainer, retriever=retriever
    )
    composer = ModelComposer(model=models.compose, translator=ModelTranslator(model=models.translate))
    return AnswerPipeline(
        understand=answer_understander(sessions, index, embed=embed, model=models.understand).understand,
        research=research,
        compose=composer.compose,
        store=SqlAnswerStore(sessions, embed=embed, shield=shield, index=index, judge=models.judge),
        translation=translation,
        pieces=SqlPieceStore(sessions, embed=embed, shield=shield),
        enrichment=build_answer_enrichment(sessions, live),
        builders=BlockBuilders.from_registry(tools, record=answer_build_record(sessions)),
        lede=LedeTools(compose=composer.lede, figures=signature_figures(sessions), retriever=retriever),
        catalogue=catalogue_lookup(sessions),
        names=answer_names(sessions, index),
        follow_depth=models.follow_depth,
    )


def answer_names(sessions: async_sessionmaker[AsyncSession], index: CraftIndexStore) -> NameLookup:
    async def names(lead: CraftRef | None, compared: Sequence[CraftRef]) -> CraftNames:
        async with sessions() as session:
            return await filing_names(session, index, lead, compared)

    return names


def answer_understander(
    sessions: async_sessionmaker[AsyncSession],
    index: CraftIndexStore,
    *,
    embed: TextEmbedder,
    model: StructuredModel,
) -> ModelUnderstander:
    async def resolve(query: CraftQuery) -> CraftResolution:
        async with sessions() as session:
            return await DatabaseCraftResolver(session, store=index, embed=embed).resolve(query)

    return ModelUnderstander(model=model, resolve=resolve, held=held_field_lookup(sessions))


def build_answer_enrichment(
    sessions: async_sessionmaker[AsyncSession], live: LiveSourcesStore
) -> EnrichmentTools:
    async def glossary(craft: CraftRef) -> list[GlossaryEntry]:
        async with sessions() as session:
            found = await knowledge_view.resolve_craft(session, craft.slug)
            return await glossary_entries(session, [found.id] if found is not None else [])

    async def pictures(ask: SectionImagesAsk) -> ImagesBlock | None:
        return await (await section_images(sessions, live)).block(ask)

    return EnrichmentTools(glossary=glossary, pictures=pictures)


def build_answer_translation(
    sessions: async_sessionmaker[AsyncSession], *, model: StructuredModel
) -> AnswerTranslation:
    translator = ReadBackTranslator(translator=ModelTranslator(model=model), model=model)
    return AnswerTranslation(translator=translator, cache=SqlTranslationCache(sessions))
