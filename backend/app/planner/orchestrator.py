from __future__ import annotations

from dataclasses import dataclass

from app.research.crafts import CraftRef
from app.research.evidence import SourceDocument
from app.research.evidence_pack import EvidencePack, PackedEvidence, ResearchTrail
from app.research.planning import FacetCoverage, PlanRequest, RetrievalPlan
from app.research.retrieval import KnowledgeRetriever, searched_fields
from app.research.stream import ResearchProgress
from app.research.structured import StructuredModel

from .coverage import facet_coverage, stored_knowledge
from .drafting import draft_plan
from .failures import FailureLog
from .live_search import asked_searchers, merged_evidence, run_searches
from .plans import effective_mode, retrieval_plan, search_question
from .policy import LIVE_BUDGETS, reference_reserve, seat_reading_kinds, stored_pack_limit
from .reading import DocumentReader, LiveSources, ReadCache, reading_order
from .references import cited_dois, follow_references

__all__ = ["PlannedQuestion", "ResearchPlanner"]


@dataclass(frozen=True)
class PlannedQuestion:
    plan: RetrievalPlan
    coverage: tuple[FacetCoverage, ...]
    degraded: bool
    search_question: str


@dataclass(frozen=True)
class LiveFindings:
    evidence: tuple[PackedEvidence, ...] = ()
    documents: tuple[SourceDocument, ...] = ()


@dataclass(frozen=True)
class _Reading:
    log: FailureLog
    report: ResearchProgress
    trail: ResearchTrail | None
    seat_kinds: tuple[tuple[str, ...], ...]
    reads: ReadCache | None


class ResearchPlanner:
    def __init__(
        self, *, model: StructuredModel, retriever: KnowledgeRetriever, sources: LiveSources
    ) -> None:
        self._model = model
        self._retriever = retriever
        self._sources = sources

    async def plan(self, request: PlanRequest) -> RetrievalPlan:
        return (await self.planned(request)).plan

    async def planned(self, request: PlanRequest) -> PlannedQuestion:
        draft = await draft_plan(self._model, request)
        mode = effective_mode(request.mode, degraded=draft.degraded)
        coverage = await facet_coverage(
            self._retriever, craft_slug=_slug(request.craft), mode=mode, facets=draft.facets
        )
        plan = retrieval_plan(request, draft, coverage, mode=mode)
        return PlannedQuestion(
            plan=plan,
            coverage=coverage,
            degraded=draft.degraded,
            search_question=search_question(request, draft),
        )

    async def research(
        self,
        request: PlanRequest,
        *,
        progress: ResearchProgress | None = None,
        trail: ResearchTrail | None = None,
        reads: ReadCache | None = None,
    ) -> EvidencePack:
        report = progress or _silent
        planned = await self.planned(request)
        plan = planned.plan
        await report("SEARCHING_STORED", len(plan.facets))
        stored = await stored_knowledge(
            self._retriever,
            craft_slug=_slug(plan.craft),
            mode=plan.mode,
            question=planned.search_question,
            fields=searched_fields(request.focus),
            limit=stored_pack_limit(request.depth),
        )
        log = FailureLog()
        reading = _Reading(log, report, trail, seat_reading_kinds(request), reads)
        findings = await self._live(plan, reading) if plan.queries else LiveFindings()
        return EvidencePack(
            plan=plan,
            degraded=planned.degraded,
            stored=stored,
            coverage=planned.coverage,
            evidence=findings.evidence,
            documents=findings.documents,
            failures=log.failures,
            searched=asked_searchers(plan, self._sources.searchers) if plan.queries else (),
        )

    async def _live(self, plan: RetrievalPlan, reading: _Reading) -> LiveFindings:
        log, trail = reading.log, reading.trail
        await reading.report("RESEARCHING", len(plan.queries))
        evidence = merged_evidence(plan, await run_searches(plan, self._sources.searchers, log))
        if evidence:
            await reading.report("READING", len(evidence))
            if trail is not None:
                await trail.found(evidence)
        reader = DocumentReader(
            self._sources, mode=plan.mode, log=log, on_read=trail.read if trail else None, reads=reading.reads
        )
        source = self._sources.doi_source
        follows = any(budget.follows_references for budget in LIVE_BUDGETS[plan.mode].values())
        ordered = reading_order(evidence, len(plan.facets), reading.seat_kinds)
        if source is None or not follows:
            documents = await reader.read_best(ordered, limit=plan.max_fetches)
            return LiveFindings(tuple(evidence), tuple(documents))
        primary_limit = plan.max_fetches - reference_reserve(plan.max_fetches)
        documents = await reader.read_best(ordered, limit=primary_limit)
        cited = cited_dois(evidence, documents, mode=plan.mode, limit=plan.max_fetches - len(documents))
        followed = await follow_references(cited, source=source, reader=reader, log=log)
        known = {entry.item.source_key for entry in evidence} | {entry.item.id for entry in evidence}
        fresh = [ref for ref in followed if not {ref.entry.item.source_key, ref.entry.item.id} & known]
        return LiveFindings(
            (*evidence, *(ref.entry for ref in fresh)),
            (*documents, *(ref.document for ref in fresh)),
        )


async def _silent(step: str, count: int) -> None:
    return None


def _slug(craft: CraftRef | None) -> str | None:
    return craft.slug if craft else None
