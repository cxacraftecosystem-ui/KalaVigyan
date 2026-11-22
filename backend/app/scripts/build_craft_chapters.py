import argparse
import asyncio
import json
from datetime import UTC, datetime
from typing import Any

from app.core.db import dispose_engine, session_scope
from app.services.craft_chapters_job import build_craft_chapters, chapter_crafts, chapter_lookups
from app.services.live_sources import live_source_client
from app.services.object_store import media_bucket


async def run(slug: str | None) -> dict[str, Any]:
    try:
        async with live_source_client() as client, session_scope() as session:
            lookups = chapter_lookups(client)
            crafts = await chapter_crafts(session, slug)
            report = await build_craft_chapters(
                session, crafts, lookups=lookups, now=datetime.now(UTC), media=media_bucket()
            )
    finally:
        await dispose_engine()
    return report.as_dict() | {"conformersChecked": lookups[0] is not None}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="build_craft_chapters")
    parser.add_argument("--craft", metavar="CRAFT_SLUG", help="build one craft's chapters, not every page")
    args = parser.parse_args(argv)
    report = asyncio.run(run(args.craft))
    print(json.dumps(report))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
