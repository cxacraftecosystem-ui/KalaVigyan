import argparse
import asyncio
import json
import sys
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from app.core.db import dispose_engine, session_scope
from app.services.page_revalidation import refresh_in_batches
from app.services.served_pages import (
    BUILD_READ_SECONDS,
    ServedPages,
    changed_owners,
    kept_digests,
    measure_served,
    parsed_record,
    record_text,
    refresh_report,
)

DEFAULT_SECONDS = 300.0
MISSING, READ = "missing", "read"


async def run(state: Path, seconds: float) -> dict[str, Any]:
    before, record = read_record(state)
    served = ServedPages()
    finished = await measured(served, seconds)
    changed = changed_owners(before, served.digests, served.unmeasured)
    sent = await refresh_in_batches(changed)
    write_record(state, kept_digests(before, served.digests, unsettled=sent.unrefreshed))
    return {"record": record, "finished": finished, **refresh_report(served, changed, sent)}


async def measured(served: ServedPages, seconds: float) -> bool:
    finished = True
    try:
        async with session_scope() as session:
            try:
                async with asyncio.timeout(seconds):
                    await measure_served(session, served)
            except TimeoutError:
                finished = False
            await session.rollback()
    finally:
        await dispose_engine()
    return finished


def read_record(state: Path) -> tuple[dict[str, str], str]:
    if not state.exists():
        return {}, MISSING
    try:
        return parsed_record(state.read_text(encoding="utf-8")), READ
    except (OSError, UnicodeDecodeError, ValidationError) as error:
        return {}, f"unreadable ({type(error).__name__}), so every page is refreshed"


def write_record(state: Path, digests: dict[str, str]) -> None:
    written = state.with_name(f"{state.name}.tmp")
    written.write_text(record_text(digests), encoding="utf-8", newline="\n")
    written.replace(state)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="refresh_served_pages")
    parser.add_argument("--state", type=Path, required=True, help="the record of what the web last served")
    parser.add_argument(
        "--seconds",
        type=float,
        default=DEFAULT_SECONDS,
        help="stop reading documents after this many seconds; what was not read is refreshed anyway",
    )
    args = parser.parse_args(argv)
    report = asyncio.run(run(args.state, args.seconds))
    for page in report["slowerThanBuildReads"]:
        print(
            f"::warning::the document of {page} took longer than the web build waits ({BUILD_READ_SECONDS}s)",
            file=sys.stderr,
        )
    print(json.dumps(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
