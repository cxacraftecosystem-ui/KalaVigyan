import argparse
import asyncio
import json
from typing import Any

from app.core.db import dispose_engine, sessionmaker
from app.services.live_sources import LiveSourcesStore
from app.services.source_journals import crossref_journals, journal_reads, store_journals, unjournaled


async def run(*, write: bool, limit: int | None) -> dict[str, Any]:
    sessions = sessionmaker()
    live = LiveSourcesStore()
    try:
        async with sessions() as session:
            stored = await unjournaled(session, limit=limit)
        reads = await journal_reads(stored, await crossref_journals(sessions, live))
        written = 0
        if write:
            async with sessions() as session:
                written = await store_journals(session, reads)
                await session.commit()
    finally:
        await live.aclose()
        await dispose_engine()
    found = [read for read in reads if read.journal]
    return {
        "read": len(reads),
        "found": len(found),
        "written": written,
        "sources": [r.as_dict() for r in reads],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="source_journals")
    parser.add_argument("--write", action="store_true", help="store each journal found; a dry run without it")
    parser.add_argument("--limit", type=int, default=None, help="read at most this many stored sources")
    args = parser.parse_args(argv)
    print(json.dumps(asyncio.run(run(write=args.write, limit=args.limit))))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
