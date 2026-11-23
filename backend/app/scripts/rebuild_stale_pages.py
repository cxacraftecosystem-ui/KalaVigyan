import argparse
import asyncio
import json
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import dispose_engine, session_scope
from app.scripts.build_monograph import SERVED_FOLDERS, monograph_content
from app.services.page_code import page_code_fingerprint
from app.services.upkeep_pages import PagesReport, rebuild_documents, rebuild_monographs, rebuild_stale_pages

EVERY_STALE_PAGE = 100_000
DEFAULT_SECONDS = 480.0
DEFAULT_DOCUMENT_SECONDS = 420.0

Step = Callable[[AsyncSession], Awaitable[None]]


async def run(seconds: float, document_seconds: float) -> dict[str, Any]:
    report = PagesReport()

    async def pages(session: AsyncSession) -> None:
        authored = sorted(SERVED_FOLDERS)
        await rebuild_monographs(session, authored, monograph_content, now=datetime.now(UTC), report=report)
        await rebuild_stale_pages(session, skip=(), report=report, limit=EVERY_STALE_PAGE)

    async def documents(session: AsyncSession) -> None:
        await rebuild_documents(session, report=report, limit=EVERY_STALE_PAGE)

    try:
        finished = await within(pages, seconds)
        documents_finished = await within(documents, document_seconds)
    finally:
        await dispose_engine()
    return {
        **report.as_dict(),
        "finished": finished,
        "documentsFinished": documents_finished,
        "pageCode": page_code_fingerprint(),
    }


async def within(step: Step, seconds: float) -> bool:
    async with session_scope() as session:
        try:
            async with asyncio.timeout(seconds):
                await step(session)
        except TimeoutError:
            await session.rollback()
            return False
    return True


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="rebuild_stale_pages")
    parser.add_argument(
        "--seconds",
        type=float,
        default=DEFAULT_SECONDS,
        help="store the authored monographs' documents, then stop rebuilding page snapshots after this many "
        "seconds in all; the nightly upkeep rebuilds what is left",
    )
    parser.add_argument(
        "--document-seconds",
        type=float,
        default=DEFAULT_DOCUMENT_SECONDS,
        help="then stop rebuilding stored documents after this many seconds; reads serve the last good copy",
    )
    args = parser.parse_args(argv)
    print(json.dumps(asyncio.run(run(args.seconds, args.document_seconds))))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
