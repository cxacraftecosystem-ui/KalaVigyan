import asyncio
import json
from datetime import UTC, datetime
from typing import Any

from app.core.config import get_settings
from app.core.db import dispose_engine, sessionmaker
from app.providers.structured import router_structured_model
from app.services import mailer
from app.services.ai_providers import AiTask
from app.services.alert_digest import send_alert_digests
from app.services.answer_store import build_answer_translation

NOT_CONFIGURED = {"enabled": True, "ok": False, "error": "MAIL_FROM_ADDRESS is not set"}


async def run() -> dict[str, Any]:
    settings = get_settings()
    if settings.alert_digest_enabled and not mailer.mail_configured():
        return dict(NOT_CONFIGURED)
    sessions = sessionmaker()
    try:
        report = await send_alert_digests(
            sessions,
            now=datetime.now(UTC),
            enabled=settings.alert_digest_enabled,
            web_url=settings.public_web_url,
            send=mailer.send,
            translation=build_answer_translation(sessions, model=router_structured_model(AiTask.TRANSLATE)),
        )
    finally:
        await dispose_engine()
    return report.as_dict()


def main() -> int:
    report = asyncio.run(run())
    print(json.dumps(report))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
