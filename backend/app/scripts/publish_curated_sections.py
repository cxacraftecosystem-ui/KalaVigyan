import argparse
import asyncio
import json
from pathlib import Path
from typing import Any

from app.core.db import dispose_engine, session_scope
from app.services.curation_sections import publish_curated_sections


async def run(directory: Path | None = None) -> dict[str, Any]:
    try:
        async with session_scope() as session:
            report = await publish_curated_sections(session, directory=directory)
            return report.summary()
    finally:
        await dispose_engine()


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="publish_curated_sections",
        description="publish one section per field of every curated craft and category from its stored claims",
    )
    parser.add_argument(
        "--directory", type=Path, help="the curated dossiers to read, by default the stored export"
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    result = asyncio.run(run(args.directory))
    print(json.dumps(result))
    return 2 if result["refused"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
