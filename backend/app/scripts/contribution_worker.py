from __future__ import annotations

import argparse
import asyncio
import logging
import signal

from app.core.config import get_settings
from app.core.db import dispose_engine, sessionmaker
from app.core.logging import configure_logging
from app.models import User
from app.providers.embedding import router_embedder
from app.providers.router import Principal, RouteTuning
from app.providers.structured import router_structured_model
from app.research.fetcher import Fetcher
from app.research.gate_thrift import GateThrift
from app.services.candidate_judge_routes import JUDGE_TASK, cheapest_judge_models
from app.services.candidate_sources import proposal_fetcher
from app.services.contribution_queue_worker import ContributionWorker, WorkerSettings, drain
from app.services.fact_proposals import ProposalAdapters

__all__ = ["main", "serve", "thrifty_adapters"]

logger = logging.getLogger("kalavigyan.contributions")


def thrifty_adapters(user: User, fetcher: Fetcher) -> ProposalAdapters:
    principal = Principal(user_id=user.id, role=user.role)
    cheapest = RouteTuning(models=dict(cheapest_judge_models()))
    return ProposalAdapters(
        fetcher=fetcher,
        embed=router_embedder(principal),
        judge=router_structured_model(JUDGE_TASK, principal, tuning=cheapest),
        escalate=(router_structured_model(JUDGE_TASK, principal),),
        thrift=GateThrift(),
    )


async def serve(settings: WorkerSettings, *, once: bool) -> int:
    configure_logging(get_settings().log_level)
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for stop_signal in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(stop_signal, stop.set)
    try:
        async with proposal_fetcher() as fetcher:

            def adapters(user: User) -> ProposalAdapters:
                return thrifty_adapters(user, fetcher)

            if once:
                worked = await drain(sessionmaker(), adapters)
                logger.info("the contribution queue checked %s proposals", worked)
                return worked
            await ContributionWorker(sessionmaker(), adapters, settings).run(stop)
    finally:
        await dispose_engine()
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run the gates of queued knowledge proposals off the request."
    )
    parser.add_argument("--concurrency", type=int, default=WorkerSettings.concurrency)
    parser.add_argument("--once", action="store_true", help="check what is queued now, then stop")
    arguments = parser.parse_args()
    asyncio.run(serve(WorkerSettings(concurrency=max(1, arguments.concurrency)), once=arguments.once))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
