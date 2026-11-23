from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.listen_deps import (
    UNAVAILABLE_DETAIL,
    ListenTools,
    listen_store,
    listen_tools,
    throttled_voice_user,
)
from app.core.errors import AppError
from app.core.rate_limit import listen_attempt
from app.models import User
from app.research.explainer import SECTION_ID_PATTERN
from app.research.vocabulary import AnswerLanguage
from app.voice.listen import NOTHING_MESSAGE, ListenAsk, ListenDeps, ListenRefused, listen_script
from app.voice.listen_store import SqlListenStore

router = APIRouter(prefix="/answers", tags=["listen"])
logger = logging.getLogger(__name__)

THROTTLED_DETAIL = "You have pressed Listen many times in a few minutes. Wait a little and try again."
REFUSAL_STATUS = {"nothing": status.HTTP_404_NOT_FOUND, "quota": status.HTTP_429_TOO_MANY_REQUESTS}


def utc_now() -> datetime:
    return datetime.now(UTC)


throttle = throttled_voice_user(listen_attempt, THROTTLED_DETAIL)


@router.get("/{answer_id}/listen")
async def listen(
    answer_id: uuid.UUID,
    language: AnswerLanguage | None = None,
    section: str | None = Query(default=None, pattern=SECTION_ID_PATTERN),
    *,
    user: User = Depends(throttle),
    store: SqlListenStore = Depends(listen_store),
    tools: ListenTools = Depends(listen_tools),
) -> dict[str, Any]:
    explainer = await store.explainer(answer_id, user.id)
    if explainer is None or language not in (None, explainer.understood.language):
        raise HTTPException(status.HTTP_404_NOT_FOUND, NOTHING_MESSAGE)
    deps = ListenDeps(ledger=store, objects=tools.objects, voices=tools.voices, clock=utc_now)
    try:
        script = await listen_script(
            ListenAsk(user_id=user.id, explainer=explainer, section_id=section), deps
        )
    except ListenRefused as error:
        headers = {"Retry-After": str(error.retry_after)} if error.retry_after else None
        raise HTTPException(REFUSAL_STATUS[error.reason], error.message, headers) from None
    except AppError as error:
        logger.warning("listening to answer %s failed: %s", answer_id, error)
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, UNAVAILABLE_DETAIL) from None
    return script.model_dump(mode="json", by_alias=True)
