import argparse
import asyncio
import uuid
from datetime import UTC, date, datetime

from app.core.db import dispose_engine, session_scope
from app.services.craft_resolver import CraftIndexStore
from app.services.write_back_filing import report_lines
from app.services.write_back_filing_store import filing_report


async def run(*, answer_id: uuid.UUID | None, since: date | None) -> list[str]:
    start = datetime(since.year, since.month, since.day, tzinfo=UTC) if since is not None else None
    try:
        async with session_scope() as session:
            rows = await filing_report(session, CraftIndexStore(), answer_id=answer_id, since=start)
            await session.rollback()
            return report_lines(rows)
    finally:
        await dispose_engine()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="write_back_filing",
        description="Where each live-research fact is filed against where today's filing rule would file it.",
    )
    parser.add_argument("--answer", type=uuid.UUID, help="only the facts this answer wrote back")
    parser.add_argument(
        "--since", type=date.fromisoformat, help="only the facts written on or after this day"
    )
    args = parser.parse_args(argv)
    for line in asyncio.run(run(answer_id=args.answer, since=args.since)):
        print(line)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
