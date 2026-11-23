import argparse
import asyncio
import json
from datetime import UTC, datetime
from typing import Any

from app.core.config import get_settings
from app.core.db import dispose_engine, session_scope
from app.providers.catalogue import AiTask
from app.providers.embedding import router_embedder
from app.providers.structured import router_structured_model
from app.scripts.build_monograph import SERVED_FOLDERS, monograph_content
from app.services.live_sources import live_source_client
from app.services.nightly_upkeep import plan_nightly_upkeep, run_nightly_upkeep, upkeep_tools
from app.services.page_revalidation import nightly_refresh


async def plan() -> dict[str, Any]:
    try:
        async with session_scope() as session:
            return await plan_nightly_upkeep(session, sorted(SERVED_FOLDERS), now=datetime.now(UTC))
    finally:
        await dispose_engine()


async def run(*, refresh: bool) -> dict[str, Any]:
    settings = get_settings()
    try:
        async with live_source_client() as client, session_scope() as session:
            tools = upkeep_tools(
                client,
                fetcher_url=settings.fetcher_url,
                monographs=sorted(SERVED_FOLDERS),
                load=monograph_content,
                embed=router_embedder(),
                names=router_structured_model(AiTask.UNDERSTAND),
            )
            upkept = await run_nightly_upkeep(session, tools, now=datetime.now(UTC))
            report = upkept.as_dict()
            if refresh:
                report["refresh"] = await nightly_refresh(upkept.pages.changed_owners(), settings=settings)
                report["ok"] = report["ok"] and report["refresh"]["ok"]
    finally:
        await dispose_engine()
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="nightly_upkeep")
    parser.add_argument(
        "--dry-run", action="store_true", help="report what tonight's upkeep would do; write nothing"
    )
    parser.add_argument(
        "--no-refresh", action="store_true", help="run the upkeep without refreshing the pages it changed"
    )
    args = parser.parse_args(argv)
    report = asyncio.run(plan() if args.dry_run else run(refresh=not args.no_refresh))
    print(json.dumps(report))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
