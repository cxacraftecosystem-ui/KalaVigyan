import asyncio
import json
from typing import Any

from app.core.db import dispose_engine, session_scope
from app.services.image_screens_backfill import fingerprint_stored
from app.services.object_store import media_bucket

NO_BUCKET = {"ok": False, "error": "S3_BUCKET is not configured"}


async def run() -> dict[str, Any]:
    objects = media_bucket()
    if objects is None:
        return NO_BUCKET
    try:
        async with session_scope() as session:
            report = await fingerprint_stored(session, objects)
    finally:
        await dispose_engine()
    return report.as_dict()


def main() -> int:
    report = asyncio.run(run())
    print(json.dumps(report))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
