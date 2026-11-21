import asyncio
import json

from app.core.db import dispose_engine, session_scope
from app.services.dataset_registry import sync_registry


async def run() -> list[str]:
    try:
        async with session_scope() as session:
            synced = await sync_registry(session)
    finally:
        await dispose_engine()
    return synced


def main() -> int:
    print(json.dumps({"synced": asyncio.run(run())}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
