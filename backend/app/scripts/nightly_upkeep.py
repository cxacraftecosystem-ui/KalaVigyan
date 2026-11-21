import argparse
import asyncio
import json
from datetime import UTC, datetime
from typing import Any

from app.core.config import get_settings
from app.core.db import dispose_engine, session_scope
from app.providers.embedding import router_embedder
from app.scripts.build_monograph import SERVED_FOLDERS, monograph_content
from app.services.live_sources import live_source_client
from app.services.nightly_upkeep import plan_nightly_upkeep, run_nightly_upkeep, upkeep_tools
from app.services.site_build import deploy_hook, nightly_site_build


async def plan() -> dict[str, Any]:
    try:
        async with session_scope() as session:
            return await plan_nightly_upkeep(session, sorted(SERVED_FOLDERS), now=datetime.now(UTC))
    finally:
        await dispose_engine()


async def run(*, build: bool) -> dict[str, Any]:
    settings = get_settings()
    try:
        async with live_source_client() as client, session_scope() as session:
            tools = upkeep_tools(
                client,
                fetcher_url=settings.fetcher_url,
                monographs=sorted(SERVED_FOLDERS),
                load=monograph_content,
                embed=router_embedder(),
            )
            report = (await run_nightly_upkeep(session, tools, now=datetime.now(UTC))).as_dict()
            if build:
                report["build"] = await nightly_site_build(
                    session, deploy_hook(settings.vercel_deploy_hook_url, client)
                )
                report["ok"] = report["ok"] and report["build"]["ok"]
    finally:
        await dispose_engine()
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="nightly_upkeep")
    parser.add_argument(
        "--dry-run", action="store_true", help="report what tonight's upkeep would do; write nothing"
    )
    parser.add_argument(
        "--no-build", action="store_true", help="run the upkeep without triggering the site build"
    )
    args = parser.parse_args(argv)
    report = asyncio.run(plan() if args.dry_run else run(build=not args.no_build))
    print(json.dumps(report))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
