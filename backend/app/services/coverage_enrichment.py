from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import SPEND_REFUSAL_KIND, AppError, NotConfigured
from app.core.logging import redact_secrets, request_id_scope
from app.models import EnrichmentJob
from app.research.composition import ComposedAnswer
from app.research.embedding import TextEmbedder
from app.research.evidence_pack import EvidencePack
from app.research.planning import PlanRequest
from app.research.structured import StructuredModel

from .coverage_selection import CraftToEnrich, least_covered_crafts, open_questions
from .craft_resolver import CraftIndexStore
from .research_write_back import store_live_research

__all__ = [
    "ENRICHMENT_CRAFTS_PER_RUN",
    "ENRICHMENT_DAILY_BUDGET_USD",
    "ENRICHMENT_JOB_MAX_USD",
    "ENRICHMENT_MODE",
    "ENRICHMENT_QUESTION_RESERVE_USD",
    "ENRICHMENT_TAG",
    "STOP_RUN_KINDS",
    "CraftOutcome",
    "EnrichmentPipeline",
    "EnrichmentReport",
    "run_coverage_enrichment",
]

ENRICHMENT_DAILY_BUDGET_USD = Decimal("2.50")
ENRICHMENT_QUESTION_RESERVE_USD = Decimal("0.25")
ENRICHMENT_JOB_MAX_USD = Decimal("10")
ENRICHMENT_CRAFTS_PER_RUN = 25
ENRICHMENT_MODE = "HYBRID"
ENRICHMENT_TAG = "enrichment-"
STOP_RUN_KINDS = frozenset({SPEND_REFUSAL_KIND, "no_route"})
BUDGET_STOP = "BUDGET"
ERROR_MAX_CHARS = 1000

SpentSince = Callable[[str, datetime], Awaitable[Decimal]]


@dataclass(frozen=True)
class EnrichmentPipeline:
    research: Callable[[PlanRequest], Awaitable[EvidencePack]]
    compose: Callable[[EvidencePack, str], Awaitable[ComposedAnswer]]
    embed: TextEmbedder
    spent: SpentSince
    index: CraftIndexStore
    judge: StructuredModel | None = None


@dataclass
class CraftOutcome:
    slug: str
    job_id: str
    status: str = "RUNNING"
    questions: int = 0
    documents: int = 0
    claims_created: int = 0
    claims_matched: int = 0
    sentences_skipped: int = 0
    spent_usd: str = "0"
    error: str | None = None


@dataclass
class EnrichmentReport:
    day_started_at: str
    budget_usd: str
    crafts: list[CraftOutcome] = field(default_factory=list)
    stopped: str | None = None
    spent_usd: str = "0"

    @property
    def ok(self) -> bool:
        return all(craft.status == "SUCCEEDED" for craft in self.crafts)

    def as_dict(self) -> dict[str, Any]:
        return {**asdict(self), "ok": self.ok}


@dataclass(frozen=True)
class _Run:
    session: AsyncSession
    pipeline: EnrichmentPipeline
    day_started_at: datetime
    budget_usd: Decimal

    async def remaining(self) -> Decimal:
        return self.budget_usd - await self.pipeline.spent(ENRICHMENT_TAG, self.day_started_at)


async def run_coverage_enrichment(
    session: AsyncSession,
    pipeline: EnrichmentPipeline,
    *,
    day_started_at: datetime,
    budget_usd: Decimal = ENRICHMENT_DAILY_BUDGET_USD,
    limit: int = ENRICHMENT_CRAFTS_PER_RUN,
) -> EnrichmentReport:
    run = _Run(session=session, pipeline=pipeline, day_started_at=day_started_at, budget_usd=budget_usd)
    report = EnrichmentReport(day_started_at=day_started_at.isoformat(), budget_usd=str(budget_usd))
    for craft in await least_covered_crafts(session, now=datetime.now(UTC), limit=limit):
        if await run.remaining() < ENRICHMENT_QUESTION_RESERVE_USD:
            report.stopped = BUDGET_STOP
            break
        outcome, stop = await _enrich_craft(run, craft)
        report.crafts.append(outcome)
        if stop is not None:
            report.stopped = stop
            break
    report.spent_usd = str(await pipeline.spent(ENRICHMENT_TAG, day_started_at))
    return report


async def _enrich_craft(run: _Run, craft: CraftToEnrich) -> tuple[CraftOutcome, str | None]:
    questions = open_questions(craft)
    job_id = await _start_job(run, craft, [question.facet for question in questions])
    tag = f"{ENRICHMENT_TAG}{job_id.hex}"
    outcome = CraftOutcome(slug=craft.slug, job_id=str(job_id))
    stop: str | None = None
    try:
        with request_id_scope(tag):
            for question in questions:
                if await run.remaining() < ENRICHMENT_QUESTION_RESERVE_USD:
                    stop = BUDGET_STOP
                    break
                await _ask(run, craft, question.text_for(craft.name), outcome)
        outcome.status = "SUCCEEDED"
    except Exception as error:
        await run.session.rollback()
        outcome.status = "FAILED"
        outcome.error = redact_secrets(str(error))[:ERROR_MAX_CHARS]
        if not isinstance(error, AppError):
            await _finish_job(run.session, job_id, outcome)
            raise
        stop = _stop_reason(error)
    outcome.spent_usd = str(await run.pipeline.spent(tag, run.day_started_at))
    await _finish_job(run.session, job_id, outcome)
    return outcome, stop


async def _ask(run: _Run, craft: CraftToEnrich, question: str, outcome: CraftOutcome) -> None:
    pack = await run.pipeline.research(PlanRequest(question=question, mode=ENRICHMENT_MODE, craft=craft.ref))
    outcome.questions += 1
    if not pack.documents:
        return
    answer = await run.pipeline.compose(pack, question)
    stored = await store_live_research(
        run.session,
        pack,
        answer,
        embed=run.pipeline.embed,
        found_by="BACKGROUND",
        index=run.pipeline.index,
        judge=run.pipeline.judge,
    )
    outcome.documents += len(stored.source_ids)
    outcome.claims_created += stored.created
    outcome.claims_matched += len(stored.results) - stored.created
    outcome.sentences_skipped += len(stored.skipped)


async def _start_job(run: _Run, craft: CraftToEnrich, facets: list[str]) -> uuid.UUID:
    budget = min(max(await run.remaining(), Decimal(0)), ENRICHMENT_JOB_MAX_USD)
    job_id = uuid.uuid4()
    job = EnrichmentJob(
        id=job_id,
        craftId=craft.craft_id,
        mode=ENRICHMENT_MODE,
        facets=facets,
        budgetUsd=budget,
        status="RUNNING",
        startedAt=datetime.now(UTC),
    )
    run.session.add(job)
    await run.session.commit()
    return job_id


async def _finish_job(session: AsyncSession, job_id: uuid.UUID, outcome: CraftOutcome) -> None:
    await session.execute(
        update(EnrichmentJob)
        .where(EnrichmentJob.id == job_id)
        .values(
            status=outcome.status,
            error=outcome.error,
            spentUsd=Decimal(outcome.spent_usd),
            finishedAt=datetime.now(UTC),
        )
    )
    await session.commit()


def _stop_reason(error: AppError) -> str | None:
    if isinstance(error, NotConfigured):
        return f"not_configured:{error.name}"
    kind = getattr(error, "kind", None)
    return kind if kind in STOP_RUN_KINDS else None
