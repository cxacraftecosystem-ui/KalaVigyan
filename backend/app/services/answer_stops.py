from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable

from app.core.logging import current_request_id

__all__ = ["StopAnswer", "stopped_unless_finished"]

logger = logging.getLogger(__name__)

StopAnswer = Callable[[str], Awaitable[None]]


async def stopped_unless_finished[T](answering: Awaitable[T], stop: StopAnswer) -> T:
    request_id = current_request_id()
    try:
        return await answering
    except BaseException:
        if request_id is None:
            raise
        try:
            await stop(request_id)
        except Exception:
            logger.exception("an answer of request %s that did not finish was not marked stopped", request_id)
        raise
