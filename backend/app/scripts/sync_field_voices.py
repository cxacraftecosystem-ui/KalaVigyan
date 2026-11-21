import asyncio
import json
from typing import Any

from app.core.config import get_settings
from app.core.db import dispose_engine, session_scope
from app.providers.embedding import router_embedder
from app.providers.picture_vision import picture_screen_tools
from app.services.field_photo_crops import sweep_withdrawn_reviews
from app.services.field_photo_screens import SCREENS_PER_RUN, screen_held_photos
from app.services.field_voices_run import run_field_voices
from app.services.object_store import media_bucket

NO_BUCKET = {"ok": True, "skipped": "S3_BUCKET is not configured"}


async def run() -> dict[str, Any]:
    try:
        report = await run_field_voices(get_settings(), open_session=session_scope, embed=router_embedder())
        result = report.as_dict()
        if report.enabled:
            result["photoScreens"] = await photo_screens()
    finally:
        await dispose_engine()
    return result


async def photo_screens() -> dict[str, Any]:
    objects = media_bucket()
    if objects is None:
        return NO_BUCKET
    swept = await sweep_withdrawn_reviews(session_scope, objects)
    screens = await screen_held_photos(session_scope, objects, picture_screen_tools(), limit=SCREENS_PER_RUN)
    return screens.as_dict() | {"reviewsSwept": swept}


def main() -> int:
    report = asyncio.run(run())
    print(json.dumps(report))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
