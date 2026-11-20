import argparse
import asyncio
import json
from datetime import UTC, datetime
from typing import Any

from app.core.db import dispose_engine, session_scope
from app.services.write_back_report import REPORT_DAYS_DEFAULT, write_back_report


async def run(days: int) -> dict[str, Any]:
    try:
        async with session_scope() as session:
            return await write_back_report(session, now=datetime.now(UTC), days=days)
    finally:
        await dispose_engine()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="write_back_report")
    parser.add_argument(
        "--days", type=int, default=REPORT_DAYS_DEFAULT, help="how many days back the report reads"
    )
    args = parser.parse_args(argv)
    report = asyncio.run(run(args.days))
    print(json.dumps(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
