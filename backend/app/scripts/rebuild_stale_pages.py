import argparse
import asyncio
import json
from typing import Any

from app.core.db import dispose_engine, session_scope
from app.services.upkeep_pages import PagesReport, rebuild_stale_pages

EVERY_STALE_PAGE = 100_000
DEFAULT_SECONDS = 480.0


async def run(seconds: float) -> dict[str, Any]:
    report = PagesReport()
    finished = True
    try:
        async with session_scope() as session:
            try:
                async with asyncio.timeout(seconds):
                    await rebuild_stale_pages(session, skip=(), report=report, limit=EVERY_STALE_PAGE)
            except TimeoutError:
                finished = False
                await session.rollback()
    finally:
        await dispose_engine()
    return {**report.as_dict(), "finished": finished}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="rebuild_stale_pages")
    parser.add_argument(
        "--seconds",
        type=float,
        default=DEFAULT_SECONDS,
        help="stop after this many seconds; the nightly upkeep rebuilds what is left",
    )
    args = parser.parse_args(argv)
    print(json.dumps(asyncio.run(run(args.seconds))))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
