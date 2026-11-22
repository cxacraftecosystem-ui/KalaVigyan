import asyncio
import json
from datetime import UTC, datetime
from typing import Any

from app.core.db import dispose_engine, session_scope
from app.services.shared_term_crafts import refresh_shared_terms


async def run() -> dict[str, Any]:
    try:
        async with session_scope() as session:
            report = await refresh_shared_terms(session, now=datetime.now(UTC))
    finally:
        await dispose_engine()
    return report.as_dict()


def main() -> int:
    print(json.dumps(asyncio.run(run())))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
