from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.roles import ROLE_RANK
from app.models import AppSetting
from app.models.enums import EXPLAINER_DEPTHS

__all__ = [
    "ANSWER_CAP_USD",
    "DEGRADE_AT_FRACTION",
    "MEDIA_CAP_USD",
    "MODEL_PRICES",
    "MONTHLY_CEILING_USD",
    "ROLE_DAILY_USD",
    "SPEND_DEFAULTS",
    "UNCAPPED_ANSWER_USD",
    "UNCAPPED_ROLE_DAILY_USD",
    "load_spend_settings",
    "spend_defaults",
    "stored_spend_value",
]

MONTHLY_CEILING_USD = "AI_MONTHLY_CEILING_USD"
MEDIA_CAP_USD = "AI_MEDIA_CAP_USD"
ROLE_DAILY_USD = "AI_ROLE_DAILY_USD"
DEGRADE_AT_FRACTION = "AI_DEGRADE_AT_FRACTION"
ANSWER_CAP_USD = "AI_ANSWER_CAP_USD"
MODEL_PRICES = "AI_MODEL_PRICES"

UNCAPPED_ROLE_DAILY_USD: Mapping[str, None] = MappingProxyType(dict.fromkeys(ROLE_RANK))
UNCAPPED_ANSWER_USD: Mapping[str, None] = MappingProxyType(dict.fromkeys(EXPLAINER_DEPTHS))

SPEND_DEFAULTS: Mapping[str, Any] = MappingProxyType(
    {
        MONTHLY_CEILING_USD: None,
        MEDIA_CAP_USD: None,
        ROLE_DAILY_USD: UNCAPPED_ROLE_DAILY_USD,
        DEGRADE_AT_FRACTION: None,
        ANSWER_CAP_USD: UNCAPPED_ANSWER_USD,
        MODEL_PRICES: MappingProxyType({}),
    }
)


def spend_defaults() -> dict[str, Any]:
    return {
        key: dict(value) if isinstance(value, Mapping) else value for key, value in SPEND_DEFAULTS.items()
    }


def stored_spend_value(key: str, stored: Any) -> Any:
    if key == ROLE_DAILY_USD and isinstance(stored, Mapping):
        return {**SPEND_DEFAULTS[key], **stored}
    return stored


async def load_spend_settings(session: AsyncSession) -> dict[str, Any]:
    rows = (
        (await session.execute(select(AppSetting).where(AppSetting.key.in_(SPEND_DEFAULTS)))).scalars().all()
    )
    values = spend_defaults()
    for row in rows:
        values[row.key] = stored_spend_value(row.key, row.value)
    return values
