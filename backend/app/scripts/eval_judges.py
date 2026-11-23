from __future__ import annotations

import argparse
import asyncio
import json
from typing import Any

from app.core.db import dispose_engine
from app.providers.judge_routes import thrifty_judges
from app.providers.router import Principal
from app.services.judge_eval import judge_cases, judge_report

__all__ = ["BELOW_FLOOR_EXIT", "FAILED_EXIT", "main"]

BELOW_FLOOR_EXIT = 3
FAILED_EXIT = 1


async def run() -> dict[str, Any]:
    try:
        return await judge_report(judge_cases(), thrifty_judges(Principal()).models)
    finally:
        await dispose_engine()


def main(argv: list[str] | None = None) -> int:
    argparse.ArgumentParser(prog="eval_judges").parse_args(argv)
    report = asyncio.run(run())
    print(json.dumps(report))
    if not report["ok"]:
        return FAILED_EXIT
    return BELOW_FLOOR_EXIT if report["belowFloor"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
