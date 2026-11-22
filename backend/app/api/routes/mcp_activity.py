from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.core.deps import require_master_admin
from app.models import User
from app.models.oauth import CLIENT_NAME_CHARS
from app.research.mcp_activity import DEFAULT_PERIOD_DAYS, PERIOD_DAYS
from app.services.mcp_activity import ActivityAsk, read_activity

router = APIRouter(prefix="/settings", tags=["settings"])

NOT_A_PERIOD = "Choose a period of 7, 30 or 180 days."
ONE_SCOPE = "Show one client or one connection, not both."


@router.get("/mcp-activity")
async def mcp_activity(
    days: int = DEFAULT_PERIOD_DAYS,
    client: Annotated[str | None, Query(min_length=1, max_length=CLIENT_NAME_CHARS)] = None,
    connection: uuid.UUID | None = None,
    _: User = Depends(require_master_admin),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    if days not in PERIOD_DAYS:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, NOT_A_PERIOD)
    if client is not None and connection is not None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, ONE_SCOPE)
    ask = ActivityAsk(days=days, client=client, connection=connection)
    activity = await read_activity(session, ask, now=datetime.now(UTC))
    return activity.model_dump(mode="json", by_alias=True)
