import argparse
import asyncio
import json
from datetime import UTC, datetime
from typing import Any

from app.core.db import dispose_engine, session_scope
from app.services.write_back_audit import gate_less_write_backs
from app.services.write_back_report import REPORT_DAYS_DEFAULT, write_back_report

GATE_LESS = "gateLess"


async def run(days: int, *, gate_less: bool = False) -> dict[str, Any]:
    try:
        async with session_scope() as session:
            now = datetime.now(UTC)
            report = await write_back_report(session, now=now, days=days)
            if gate_less:
                report[GATE_LESS] = await gate_less_write_backs(session, now=now, days=days)
            await session.rollback()
            return report
    finally:
        await dispose_engine()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="write_back_report")
    parser.add_argument(
        "--days", type=int, default=REPORT_DAYS_DEFAULT, help="how many days back the report reads"
    )
    parser.add_argument(
        "--gate-less",
        action="store_true",
        help="also re-check, without writing, the write-backs stored with no gate checks",
    )
    args = parser.parse_args(argv)
    report = asyncio.run(run(args.days, gate_less=args.gate_less))
    print(json.dumps(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
