import asyncio
import json
from datetime import datetime
from decimal import Decimal
from typing import Any

from app.composer.candidates import compose_request
from app.composer.composer import ModelComposer
from app.core.db import dispose_engine, session_scope, sessionmaker
from app.planner.orchestrator import ResearchPlanner
from app.providers import budget, router
from app.providers.embedding import router_embedder
from app.providers.structured import router_structured_model
from app.research.composition import ComposedAnswer
from app.research.evidence_pack import EvidencePack
from app.retrieval.hybrid import StoredKnowledgeSearch
from app.services.ai_providers import AiTask
from app.services.coverage_enrichment import EnrichmentPipeline, run_coverage_enrichment
from app.services.craft_resolver import CraftIndexStore
from app.services.live_sources import live_source_client, live_sources


async def spent_since(request_id_prefix: str, since: datetime) -> Decimal:
    async with session_scope() as session:
        return await router.tagged_spend(session, request_id_prefix=request_id_prefix, since=since)


async def run() -> dict[str, Any]:
    embed = router_embedder()
    composer = ModelComposer(model=router_structured_model(AiTask.COMPOSE))

    async def compose(pack: EvidencePack, question: str) -> ComposedAnswer:
        return await composer.compose(compose_request(pack, question))

    try:
        async with live_source_client() as client, sessionmaker()() as reader, sessionmaker()() as writer:
            planner = ResearchPlanner(
                model=router_structured_model(AiTask.PLAN),
                retriever=StoredKnowledgeSearch(reader, embed=embed),
                sources=await live_sources(reader, client),
            )
            pipeline = EnrichmentPipeline(
                research=planner.research,
                compose=compose,
                embed=embed,
                spent=spent_since,
                index=CraftIndexStore(),
                judge=router_structured_model(AiTask.EVAL_JUDGE),
            )
            report = await run_coverage_enrichment(writer, pipeline, day_started_at=budget.day_start())
    finally:
        await dispose_engine()
    return report.as_dict()


def main() -> int:
    report = asyncio.run(run())
    print(json.dumps(report))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
