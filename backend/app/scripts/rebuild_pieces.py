import asyncio
import json
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.db import dispose_engine, sessionmaker
from app.core.shielded import ShieldedWork
from app.providers import budget
from app.providers.answer_routes import answer_models
from app.providers.budget import AnswerSpend, Ceilings
from app.providers.embedding import router_embedder
from app.providers.router import Principal
from app.scripts.enrich_coverage import spent_since
from app.services.answer_store import build_answer_pipeline
from app.services.answering import AnswerPipeline
from app.services.coverage_enrichment import ENRICHMENT_DAILY_BUDGET_USD, ENRICHMENT_TAG
from app.services.craft_resolver import CraftIndexStore
from app.services.live_sources import LiveSourcesStore
from app.services.piece_rebuild import (
    StaleGroup,
    mark_rebuild_tried,
    rebuild_group,
    run_piece_rebuild,
    stale_groups,
)
from app.services.section_enrichment import without_pictures


@dataclass(eq=False)
class DayHeldSpend(AnswerSpend):
    day_left_usd: Decimal = Decimal(0)

    def left(self, ceilings: Ceilings) -> Decimal | None:
        own = super().left(ceilings)
        day = self.day_left_usd - self.held_usd - self.spent_usd
        return day if own is None else min(own, day)


def rebuild_pipeline(
    depth: str,
    *,
    day_left_usd: Decimal,
    sessions: async_sessionmaker[AsyncSession],
    index: CraftIndexStore,
    live: LiveSourcesStore,
    shield: ShieldedWork,
) -> AnswerPipeline:
    spend = DayHeldSpend(depth=depth, day_left_usd=day_left_usd)
    principal = Principal(answer=spend)
    optional = Principal(answer=spend.headroom())
    pipeline = build_answer_pipeline(
        sessions=sessions,
        index=index,
        live=live,
        models=answer_models(depth, principal=principal, optional=optional),
        embed=router_embedder(principal),
        shield=shield,
    )
    return replace(pipeline, enrichment=without_pictures(pipeline.enrichment))


async def run() -> dict[str, Any]:
    day_started_at = budget.day_start()
    sessions = sessionmaker()
    live = LiveSourcesStore()
    shield = ShieldedWork()
    index = CraftIndexStore()

    async def remaining() -> Decimal:
        return ENRICHMENT_DAILY_BUDGET_USD - await spent_since(ENRICHMENT_TAG, day_started_at)

    async def rebuild(group: StaleGroup) -> str:
        day_left = await remaining()
        pipeline = rebuild_pipeline(
            group.depth, day_left_usd=day_left, sessions=sessions, index=index, live=live, shield=shield
        )
        return await rebuild_group(group, pipeline)

    async def tried(group: StaleGroup) -> None:
        async with sessions() as session:
            await mark_rebuild_tried(session, group, now=datetime.now(UTC))
            await session.commit()

    try:
        async with sessions() as session:
            groups = await stale_groups(session, now=datetime.now(UTC))
        report = await run_piece_rebuild(
            groups, rebuild=rebuild, remaining=remaining, budget_usd=ENRICHMENT_DAILY_BUDGET_USD, tried=tried
        )
        await shield.drain()
    finally:
        await live.aclose()
        await dispose_engine()
    return report.as_dict()


def main() -> int:
    report = asyncio.run(run())
    print(json.dumps(report))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
