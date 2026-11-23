from __future__ import annotations

import argparse
import asyncio
import logging
import signal

from app.core.config import get_settings
from app.core.connection_budget import most_runs
from app.core.db import dispose_engine, process_pools, sessionmaker
from app.core.logging import configure_logging
from app.models import User
from app.providers.embedding import router_embedder
from app.providers.router import Principal
from app.research.fetcher import Fetcher
from app.research.gate_thrift import GateThrift
from app.services.candidate_judge_routes import thrifty_judges
from app.services.candidate_sources import proposal_fetcher
from app.services.contribution_queue_worker import ContributionWorker, WorkerSettings, drain
from app.services.fact_proposals import ProposalAdapters

__all__ = ["main", "runs_at_once", "serve", "thrifty_adapters"]

logger = logging.getLogger("kalavigyan.contributions")


def thrifty_adapters(user: User, fetcher: Fetcher) -> ProposalAdapters:
    principal = Principal(user_id=user.id, role=user.role)
    cheap, strong = thrifty_judges(principal)
    return ProposalAdapters(
        fetcher=fetcher,
        embed=router_embedder(principal),
        judge=cheap,
        escalate=(strong,),
        thrift=GateThrift(),
    )


def runs_at_once(asked: int, allowed: int) -> int:
    if asked <= allowed:
        return max(1, asked)
    logger.warning(
        "--concurrency %s needs more connections than this process's budget holds; running %s at once",
        asked,
        allowed,
    )
    return allowed


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
    allowed = most_runs(process_pools(get_settings()).main)
    concurrency = runs_at_once(arguments.concurrency, allowed)
    asyncio.run(serve(WorkerSettings(concurrency=concurrency), once=arguments.once))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
