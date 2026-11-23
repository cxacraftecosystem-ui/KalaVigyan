from __future__ import annotations

from zoneinfo import ZoneInfo

from app.models.time_zone import INDIA_TZ_NAME

__all__ = ["INDIA_TZ", "INDIA_TZ_NAME"]

INDIA_TZ = ZoneInfo(INDIA_TZ_NAME)
