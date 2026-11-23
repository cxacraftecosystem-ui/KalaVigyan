from __future__ import annotations

import argparse
import asyncio
import json
from typing import Any

from app.core.db import dispose_engine, session_scope
from app.providers.judge_routes import thrifty_judges
from app.providers.router import Principal
from app.services.differ_rejudge import flagged_pairs, rejudged_pairs

__all__ = ["main"]


async def run() -> list[dict[str, Any]]:
    try:
        async with session_scope() as session:
            pairs = await flagged_pairs(session)
            await session.rollback()
        return await rejudged_pairs(pairs, thrifty_judges(Principal()).models)
    finally:
        await dispose_engine()


def main(argv: list[str] | None = None) -> int:
    argparse.ArgumentParser(
        prog="rejudge_differing",
        description="Re-judge every live fact flagged sources differ with the structural comparison; writes nothing",
    ).parse_args(argv)
    print(json.dumps(asyncio.run(run())))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
