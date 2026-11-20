from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass
from math import ceil
from types import MappingProxyType
from typing import Any

from fastapi import Depends, HTTPException, status

from app.core.errors import InvalidInput
from app.core.rate_limit import (
    COMPONENT_PROPOSALS,
    FACT_PROPOSALS,
    IMAGE_UPLOADS,
    LAYOUT_PROPOSALS,
    PROPOSAL_LIMITS,
    STRUCTURE_PROPOSALS,
    proposal_attempt,
    retry_after_value,
)
from app.models import User

__all__ = [
    "LIMIT_NOUNS",
    "Spent",
    "proposal_limit",
    "refuse_tool_when_spent",
    "refuse_when_spent",
    "spent_limit",
    "wait_words",
]

LIMIT_NOUNS: Mapping[str, str] = MappingProxyType(
    {
        FACT_PROPOSALS: "fact proposals",
        COMPONENT_PROPOSALS: "component proposals",
        LAYOUT_PROPOSALS: "layout proposals",
        IMAGE_UPLOADS: "picture uploads",
        STRUCTURE_PROPOSALS: "structure proposals",
    }
)
SPENT = "This account made {limit} {noun} in the last hour, the most one account may. Try again in {wait}."
MINUTE = 60

Proposer = Callable[..., Awaitable[User]]


@dataclass(frozen=True)
class Spent:
    message: str
    wait_seconds: float


def wait_words(seconds: float) -> str:
    if seconds >= MINUTE:
        minutes = ceil(seconds / MINUTE)
        return f"{minutes} minute" if minutes == 1 else f"{minutes} minutes"
    whole = max(1, ceil(seconds))
    return f"{whole} second" if whole == 1 else f"{whole} seconds"


def spent_limit(kind: str, user: Any) -> Spent | None:
    allowed, wait = proposal_attempt(kind, user)
    if allowed:
        return None
    message = SPENT.format(limit=PROPOSAL_LIMITS[kind], noun=LIMIT_NOUNS[kind], wait=wait_words(wait))
    return Spent(message=message, wait_seconds=wait)


def refuse_when_spent(kind: str, user: Any) -> None:
    spent = spent_limit(kind, user)
    if spent is not None:
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            spent.message,
            {"Retry-After": retry_after_value(spent.wait_seconds)},
        )


def refuse_tool_when_spent(kind: str, user: Any) -> None:
    spent = spent_limit(kind, user)
    if spent is not None:
        raise InvalidInput(spent.message)


def proposal_limit(kind: str, proposer: Proposer) -> Callable[..., Awaitable[None]]:
    async def limited(user: User = Depends(proposer)) -> None:
        refuse_when_spent(kind, user)

    limited.__name__ = f"limit_{kind}"
    return limited
